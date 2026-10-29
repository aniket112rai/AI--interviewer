import asyncio
import json
import logging
import re
import time
from datetime import UTC, datetime
from time import perf_counter

from livekit import rtc
from livekit.agents import Agent, AgentSession, JobContext, JobProcess, WorkerOptions, cli, inference, llm
from livekit.agents.voice import AgentStateChangedEvent, UserInputTranscribedEvent, UserStateChangedEvent
from livekit.agents.metrics import LLMMetrics, STTMetrics, TTSMetrics
from livekit.agents import room_io
from livekit.local_inference import init_eot
from livekit.plugins import deepgram, openai, silero

from agent.directives import full_instructions
from agent.evaluator import apply_evaluation, evaluate_answer, is_repeat_request
from agent.session_io import SessionWriter, finalize_with_retry, load_session, mark_live
from agent.state import InterviewRuntime
from common.config import settings
from common.prompts import interviewer_prompt
from common.schemas.live import LiveState
from common.schemas.evaluation import Evaluation as EvaluationData


logger = logging.getLogger("ai_interviewer.agent")


def prewarm(proc: JobProcess) -> None:
    init_eot()
    proc.userdata["turn_detector"] = inference.TurnDetector(version="v1-mini")
    proc.userdata["vad"] = silero.VAD.load(activation_threshold=0.6)


class Interviewer(Agent):
    def __init__(self, runtime: InterviewRuntime, prior_turns: list[tuple[str, str]]) -> None:
        chat_ctx = llm.ChatContext()
        for role, content in prior_turns:
            chat_ctx.add_message(role=role, content=content)
        self.runtime = runtime
        super().__init__(instructions=full_instructions(runtime), chat_ctx=chat_ctx)

    async def on_user_turn_completed(
        self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage
    ) -> None:
        runtime = self.runtime
        answer = new_message.text_content.strip()
        if not answer:
            runtime.low_confidence = True
            await self.update_instructions(full_instructions(runtime))
            return
        runtime.exchange.append(("user", answer))
        runtime.exchange = runtime.exchange[-6:]
        runtime.repeat_request = is_repeat_request(answer)
        runtime.format_request = bool(re.search(
            r"\b(format|how long|what happens|what should i expect|what is this|what's this|how does this work)\b",
            answer,
            re.I,
        ))
        runtime.low_confidence = (
            _looks_unclear(answer) and not runtime.repeat_request and not runtime.format_request
        )
        runtime.silence_check_sent = False
        thread = runtime.current_thread
        if thread is None:
            await self.update_instructions(full_instructions(runtime))
            return
        turn_idx = await runtime.writer.append_turn("user", answer)
        if runtime.seed_pending and runtime.state.thread_started_at_sec == 0:
            evaluation_task = asyncio.create_task(runtime.writer.save_evaluation(
                EvaluationData(
                    turn_idx=turn_idx,
                    thread_id=thread.id,
                    scored=False,
                    answer_quality="unclear",
                )
            ))
            _track_evaluation(runtime, evaluation_task)
            await runtime.writer.save_state()
            await self.update_instructions(full_instructions(runtime))
            return
        question = runtime.last_question or thread.seed_question
        low_confidence = runtime.low_confidence
        if runtime.format_request:
            evaluation_task = asyncio.create_task(
                runtime.writer.save_evaluation(
                    EvaluationData(
                        turn_idx=turn_idx, thread_id=thread.id, scored=False, answer_quality="unclear"
                    )
                )
            )
        else:
            evaluation_task = asyncio.create_task(
                _evaluate_and_apply(runtime, thread, turn_idx, question, answer, low_confidence)
            )
        _track_evaluation(runtime, evaluation_task)
        if runtime.repeat_request:
            runtime.last_question = question
        await runtime.writer.save_state()
        await self.update_instructions(full_instructions(runtime))


async def _evaluate_and_apply(
    runtime: InterviewRuntime,
    thread,
    turn_idx: int,
    question: str,
    answer: str,
    low_confidence: bool,
) -> None:
    result = await evaluate_answer(
        turn_idx=turn_idx,
        thread=thread,
        question=question,
        answer=answer,
        exchange=runtime.exchange,
        low_confidence=low_confidence,
    )
    await runtime.writer.save_evaluation(result)
    if result.scored:
        covered = runtime.state.goals_covered.setdefault(thread.id, [])
        for goal in result.goals_covered:
            if goal not in covered:
                covered.append(goal)
    if result.scored and runtime.current_thread is not None and runtime.current_thread.id == thread.id:
        apply_evaluation(runtime.state, result)
        runtime.last_missed_points = result.missed_points[-5:]
        if result.answer_quality == "weak" and runtime.state.hints_used_in_thread == 0:
            runtime.allow_hint = True
    await runtime.writer.save_state()
    runtime.agent_ref and await runtime.agent_ref.update_instructions(full_instructions(runtime))


def _track_evaluation(runtime: InterviewRuntime, task: asyncio.Task) -> None:
    runtime.tasks.add(task)
    runtime.evaluation_tasks.add(task)
    task.add_done_callback(runtime.tasks.discard)
    task.add_done_callback(runtime.evaluation_tasks.discard)


async def _drain_evaluations(runtime: InterviewRuntime) -> None:
    pending = {task for task in runtime.evaluation_tasks if task is not asyncio.current_task()}
    if not pending:
        return
    _, unfinished = await asyncio.wait(pending, timeout=15)
    for task in unfinished:
        task.cancel()
    if unfinished:
        await asyncio.gather(*unfinished, return_exceptions=True)
        logger.warning("Cancelled %d evaluator task(s) during session finalization.", len(unfinished))


async def entrypoint(ctx: JobContext) -> None:
    try:
        dispatch_metadata = json.loads(ctx.job.metadata)
        session_id = dispatch_metadata.get("session_id")
    except (TypeError, json.JSONDecodeError):
        session_id = None
    if not isinstance(session_id, str) or not session_id:
        raise ValueError("LiveKit dispatch metadata must include a session_id.")

    plan, profile, state, history, started_at, candidate_identity = await load_session(session_id)
    job_id = ctx.job.id
    started_at = await mark_live(session_id, job_id)
    elapsed = max(0.0, (datetime.now(UTC) - started_at).total_seconds())
    runtime = InterviewRuntime(
        plan=plan,
        duration_min=(plan.opening_sec + plan.closing_sec + sum(t.time_budget_sec for t in plan.threads)) // 60,
        state=state,
        started_monotonic=time.monotonic() - elapsed,
    )
    runtime.writer = SessionWriter(session_id, runtime.state)
    runtime.seed_pending = runtime.state.thread_started_at_sec == 0
    if history:
        runtime.opening_pending = False
        last_ai = next((text for role, text in reversed(history) if role == "assistant"), "")
        runtime.last_question = _last_question(last_ai)

    vad = ctx.proc.userdata["vad"]
    turn_detector = ctx.proc.userdata["turn_detector"]
    skills = list(dict.fromkeys(profile.skills + profile.primary_stack))[:80]
    stt = deepgram.STT(
        model=settings.deepgram_stt_model,
        language="en-US",
        interim_results=True,
        keyterms=skills,
        api_key=settings.deepgram_api_key,
    )
    live_llm = openai.LLM(
        model=settings.openai_model_fast,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url or "https://api.openai.com/v1",
        max_completion_tokens=150,
        prompt_cache_key="ai-interviewer-live-v1",
    )
    tts = deepgram.TTS(model=settings.deepgram_tts_model, api_key=settings.deepgram_api_key)
    stt.prewarm()
    live_llm.prewarm()
    tts.prewarm()
    session = AgentSession(
        stt=stt,
        llm=live_llm,
        tts=tts,
        vad=vad,
        turn_handling={
            "turn_detection": turn_detector,
            "endpointing": {"min_delay": 0.5, "max_delay": 2.0},
            "interruption": {
                "enabled": True,
                "min_duration": 0.5,
                "min_words": 2,
                "resume_false_interruption": True,
            },
            "preemptive_generation": {"enabled": True},
        },
    )
    agent = Interviewer(runtime, history)
    runtime.agent_ref = agent
    if runtime.state.difficulty == "medium" and runtime.current_thread:
        runtime.state.difficulty = runtime.current_thread.difficulty_start

    turn_started_at: float | None = None
    user_speech_started_at: float | None = None
    stage_metrics: dict[str, float | None] = {"stt": None, "llm": None, "tts": None}
    response_started_at: float | None = None
    agent_spoke = False
    activity_epoch = 0
    silence_task: asyncio.Task | None = None
    disconnected_task: asyncio.Task | None = None
    finished = False

    def schedule(coro) -> asyncio.Task:
        task = asyncio.create_task(coro)
        runtime.tasks.add(task)
        task.add_done_callback(runtime.tasks.discard)
        return task

    async def finish(reason: str) -> None:
        nonlocal finished
        if finished:
            return
        finished = True
        await _drain_evaluations(runtime)
        await runtime.writer.save_state()
        await finalize_with_retry(session_id, job_id, reason)

    async def hard_stop() -> None:
        await asyncio.sleep(max(0, runtime.duration_min * 60 + 60 - runtime.elapsed_sec))
        if not finished:
            await finish("time_limit")
            await session.shutdown(drain=False)
            ctx.room.disconnect()

    async def monitor_time() -> None:
        while not finished:
            await asyncio.sleep(1)
            if runtime.remaining_sec <= plan.closing_sec and not runtime.closing_started:
                runtime.closing_started = True
                await session.say(plan.closing.text)
                await finish("time_limit")
                await session.shutdown(drain=True)
                ctx.room.disconnect()
                return
            if runtime.remaining_sec <= -60:
                await finish("time_limit")
                await session.shutdown(drain=False)
                ctx.room.disconnect()
                return

    async def check_silence(epoch: int) -> None:
        await asyncio.sleep(23)
        if not finished and epoch == activity_epoch and not runtime.silence_check_sent:
            runtime.silence_check_sent = True
            await session.say("Take your time. Would you like me to rephrase the question?")

    @session.on("conversation_item_added")
    def on_conversation_item(event) -> None:
        item = event.item
        if not isinstance(item, llm.ChatMessage) or item.role not in {"user", "assistant"}:
            return
        content = item.text_content.strip()
        if not content:
            return
        interrupted = bool(getattr(item, "interrupted", False))
        schedule(runtime.writer.append_turn(item.role, content, interrupted))
        if item.role == "assistant":
            runtime.exchange.append(("assistant", content))
            runtime.exchange = runtime.exchange[-6:]
            runtime.last_question = _last_question(content) or runtime.last_question
            runtime.state.asked_questions.append(content)
            runtime.state.asked_questions = runtime.state.asked_questions[-20:]
            if content == plan.opening.text:
                runtime.next_action = "seed"
            elif runtime.next_action == "seed":
                runtime.seed_pending = False
                runtime.state.thread_started_at_sec = runtime.elapsed_sec
            elif runtime.next_action == "move_on":
                if runtime.advance():
                    runtime.seed_pending = False
                    next_thread = runtime.current_thread
                    if next_thread:
                        runtime.state.difficulty = next_thread.difficulty_start
                else:
                    runtime.closing_started = True
            elif runtime.next_action == "follow_up":
                runtime.state.followups_used += 1
                if runtime.allow_hint and runtime.state.hints_used_in_thread == 0:
                    runtime.state.hints_used_in_thread = 1
                runtime.allow_hint = False
            elif runtime.next_action == "repeat":
                runtime.repeat_request = False
                runtime.low_confidence = False
            elif runtime.next_action == "format_answer":
                runtime.format_request = False
            schedule(runtime.writer.save_state())
            schedule(agent.update_instructions(full_instructions(runtime)))

    @session.on("user_state_changed")
    def on_user_state_changed(event: UserStateChangedEvent) -> None:
        nonlocal user_speech_started_at, turn_started_at, silence_task
        if event.new_state == "speaking":
            user_speech_started_at = perf_counter()
            if silence_task:
                silence_task.cancel()
        elif event.new_state == "listening" and user_speech_started_at is not None:
            turn_started_at = perf_counter()

    @session.on("user_input_transcribed")
    def on_user_transcribed(event: UserInputTranscribedEvent) -> None:
        nonlocal turn_started_at
        if event.is_final:
            transcript_at = perf_counter()
            if turn_started_at is None:
                turn_started_at = transcript_at
            stage_metrics["stt"] = max(0.0, transcript_at - turn_started_at)

    @session.on("user_transcription_timeout")
    def on_transcription_timeout(_event) -> None:
        runtime.low_confidence = True

        async def ask_for_repeat() -> None:
            runtime.next_action = "repeat"
            await session.say("Sorry, the audio was a bit unclear. Could you repeat that?")
            runtime.low_confidence = False

        schedule(ask_for_repeat())

    @session.on("agent_state_changed")
    def on_agent_state_changed(event: AgentStateChangedEvent) -> None:
        nonlocal turn_started_at, user_speech_started_at, response_started_at, agent_spoke, stage_metrics, silence_task, activity_epoch
        if event.new_state == "speaking":
            response_started_at = perf_counter()
            agent_spoke = True
        elif event.new_state == "listening" and agent_spoke:
            if turn_started_at is not None:
                e2e = (response_started_at - turn_started_at) if response_started_at else None
                logger.info(
                    "voice_turn session=%s e2e_ms=%s stt_ms=%s llm_ttft_ms=%s tts_ttfb_ms=%s",
                    session_id,
                    _ms(e2e),
                    _ms(stage_metrics["stt"]),
                    _ms(stage_metrics["llm"]),
                    _ms(stage_metrics["tts"]),
                )
            turn_started_at = None
            response_started_at = None
            user_speech_started_at = None
            agent_spoke = False
            stage_metrics = {"stt": None, "llm": None, "tts": None}
            activity_epoch += 1
            if silence_task:
                silence_task.cancel()
            silence_task = schedule(check_silence(activity_epoch))

    @stt.on("metrics_collected")
    def on_stt_metrics(metrics: STTMetrics) -> None:
        if metrics.duration > 0:
            stage_metrics["stt"] = metrics.duration

    @live_llm.on("metrics_collected")
    def on_llm_metrics(metrics: LLMMetrics) -> None:
        stage_metrics["llm"] = metrics.ttft if metrics.ttft >= 0 else None

    @tts.on("metrics_collected")
    def on_tts_metrics(metrics: TTSMetrics) -> None:
        stage_metrics["tts"] = metrics.ttfb if metrics.ttfb >= 0 else None

    @ctx.room.on("participant_connected")
    def on_participant_connected(_participant: rtc.RemoteParticipant) -> None:
        nonlocal disconnected_task
        if disconnected_task:
            disconnected_task.cancel()
            disconnected_task = None

    @ctx.room.on("participant_disconnected")
    def on_participant_disconnected(_participant: rtc.RemoteParticipant) -> None:
        nonlocal disconnected_task

        async def wait_for_reconnect_window() -> None:
            remaining_token_sec = max(0, plan.opening_sec + plan.closing_sec + sum(x.time_budget_sec for x in plan.threads) + 600 - runtime.elapsed_sec)
            await asyncio.sleep(remaining_token_sec)
            await finish("candidate_disconnected")
            await session.shutdown(drain=False)

        if disconnected_task:
            disconnected_task.cancel()
        disconnected_task = schedule(wait_for_reconnect_window())

    @ctx.room.on("data_received")
    def on_data_received(packet: rtc.DataPacket) -> None:
        if packet.participant and packet.participant.identity == candidate_identity:
            if packet.data == b"end_interview":
                async def end_by_candidate() -> None:
                    await finish("candidate_ended")
                    await session.shutdown(drain=True)

                schedule(end_by_candidate())

    async def on_shutdown(_reason: str) -> None:
        nonlocal finished
        was_finished = finished
        finished = True
        if not was_finished:
            await _drain_evaluations(runtime)
        await runtime.writer.save_state()
        if not was_finished:
            await finalize_with_retry(session_id, job_id, "agent_shutdown")

    ctx.add_shutdown_callback(on_shutdown)
    await session.start(
        room=ctx.room,
        agent=agent,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(auto_gain_control=True, pre_connect_audio=True)
        ),
    )
    if not history:
        runtime.next_action = "opening"
        await session.say(plan.opening.text)
        runtime.opening_pending = False
    schedule(monitor_time())
    schedule(hard_stop())


def _looks_unclear(text: str) -> bool:
    words = re.findall(r"[A-Za-z0-9']+", text)
    if len(words) < 4:
        return True
    letters = sum(character.isalpha() for character in text)
    return letters / max(1, len(text)) < 0.35


def _last_question(text: str) -> str:
    questions = [part.strip() for part in re.split(r"(?<=[?])\s+", text) if "?" in part]
    return questions[-1] if questions else ""


def _ms(seconds: float | None) -> int | None:
    return round(seconds * 1000) if seconds is not None else None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
            agent_name=settings.agent_name,
            ws_url=settings.livekit_url,
            api_key=settings.livekit_api_key,
            api_secret=settings.livekit_api_secret,
        )
    )
