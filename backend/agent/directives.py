from common.prompts import interviewer_prompt

from agent.state import InterviewRuntime


def build_directive(runtime: InterviewRuntime) -> str:
    if runtime.repeat_request:
        runtime.next_action = "repeat"
        return (
            "INTERVIEW DIRECTIVE: The candidate asked you to repeat or simplify the last question. "
            f"Acknowledge briefly and rephrase this question more simply: {runtime.last_question}. "
            "This is not a follow-up. Do not add another question."
        )
    if runtime.low_confidence:
        runtime.next_action = "repeat"
        return (
            "INTERVIEW DIRECTIVE: The audio or transcript was unclear. Say exactly: Sorry, the audio was a bit unclear. "
            "Could you repeat that? Do not score this turn or count it as a follow-up."
        )
    if runtime.format_request:
        runtime.next_action = "format_answer"
        return (
            "INTERVIEW DIRECTIVE: Briefly explain the interview format: resume-based questions, follow-ups, "
            "and time to think are all expected. Defer unrelated candidate questions until the end, then "
            "return to the current topic without asking a second question."
        )
    if runtime.remaining_sec <= runtime.plan.closing_sec:
        runtime.next_action = "wrap_up"
        return (
            f"INTERVIEW DIRECTIVE: Wrap up now. Say a brief bridge, then the exact closing: "
            f"{runtime.plan.closing.text} Do not ask another question."
        )

    thread = runtime.current_thread
    if thread is None:
        runtime.next_action = "wrap_up"
        return f"INTERVIEW DIRECTIVE: Wrap up with this closing text: {runtime.plan.closing.text}"
    if runtime.seed_pending:
        runtime.next_action = "seed"
        return (
            f"INTERVIEW DIRECTIVE: Acknowledge briefly and ask this main question naturally: "
            f"{thread.seed_question} This is not a follow-up."
        )
    if runtime.thread_should_advance():
        runtime.next_action = "move_on"
        next_index = runtime.state.thread_idx + 1
        if next_index >= len(runtime.plan.threads):
            return f"INTERVIEW DIRECTIVE: No threads remain. Wrap up with: {runtime.plan.closing.text}"
        next_thread = runtime.plan.threads[next_index]
        return (
            "INTERVIEW DIRECTIVE: Move on now. Give a brief transition, then ask the next thread's seed "
            f"question naturally: {next_thread.seed_question} Do not ask a follow-up about the previous topic."
        )

    runtime.next_action = "follow_up"
    actions = ["clarify", "probe", "challenge", "verify_claim", "redirect"]
    if runtime.allow_hint and runtime.state.hints_used_in_thread == 0:
        actions.append("hint")
    return f"""INTERVIEW DIRECTIVE:
Current thread topic: {thread.topic}
Resume context facts: {'; '.join(thread.context)}
Goals still to cover: {'; '.join(runtime.uncovered_goals())}
Follow-ups already used: {runtime.state.followups_used}; follow-ups left: {max(0, thread.max_followups - runtime.state.followups_used)}
Hint used in this thread: {'yes' if runtime.state.hints_used_in_thread else 'no'}
Thread time left: {max(0, int(runtime.thread_remaining_sec()))} seconds; overall time left: {max(0, int(runtime.remaining_sec))} seconds
Current difficulty: {runtime.state.difficulty}
Recent missed points: {'; '.join(runtime.last_missed_points[-5:]) or 'none'}
Questions and angles already asked: {'; '.join(runtime.state.asked_questions[-10:]) or 'none'}
Allowed action for this turn: choose one of {', '.join(actions)}. Do not repeat any listed question or angle.
Ask a concise, single open-ended question and acknowledge the answer briefly. Replies must be 1 to 3 sentences."""


def full_instructions(runtime: InterviewRuntime) -> str:
    return f"{interviewer_prompt()}\n\n{build_directive(runtime)}"
