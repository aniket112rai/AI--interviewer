import asyncio
import json
import logging
from datetime import UTC, datetime
from urllib.error import URLError
from urllib.request import Request, urlopen

from sqlalchemy import func, select

from common.config import settings
from common.db import SessionLocal
from common.models import Evaluation as EvaluationRow
from common.models import InterviewSession, Turn
from common.schemas.evaluation import Evaluation as EvaluationData
from common.schemas.live import LiveState
from common.schemas.plan import Plan
from common.schemas.profile import Profile


logger = logging.getLogger("ai_interviewer.agent.session_io")


def _state_without_job(state: dict | None) -> LiveState:
    values = dict(state or {})
    values.pop("active_job_id", None)
    return LiveState.model_validate(values)


async def load_session(session_id: str) -> tuple[Plan, Profile, LiveState, list[tuple[str, str]], datetime, str]:
    async with SessionLocal() as db:
        interview = await db.get(InterviewSession, session_id)
        if interview is None or interview.plan is None or interview.profile_snapshot is None:
            raise ValueError("Interview plan or resume snapshot is missing.")
        if interview.status not in {"ready", "live"}:
            raise ValueError("Interview session cannot be resumed in its current state.")
        plan = Plan.model_validate(interview.plan)
        profile = Profile.model_validate(interview.profile_snapshot)
        state = _state_without_job(interview.live_state)
        started_at = interview.started_at or datetime.now(UTC)
        turns = list((await db.scalars(
            select(Turn).where(Turn.session_id == session_id).order_by(Turn.idx.desc()).limit(10)
        )).all())
        history = [("assistant" if turn.role == "ai" else turn.role, turn.text) for turn in reversed(turns)]
        return plan, profile, state, history, started_at, interview.user_id


async def mark_live(session_id: str, job_id: str) -> datetime:
    async with SessionLocal() as db:
        async with db.begin():
            interview = await db.get(InterviewSession, session_id)
            if interview is None or interview.status not in {"ready", "live"}:
                raise ValueError("Interview session is not ready or live.")
            now = datetime.now(UTC)
            if interview.started_at is None:
                interview.started_at = now
            interview.status = "live"
            state = _state_without_job(interview.live_state)
            interview.live_state = {**state.model_dump(mode="json"), "active_job_id": job_id}
            return interview.started_at


class SessionWriter:
    def __init__(self, session_id: str, state: LiveState) -> None:
        self.session_id = session_id
        self.state = state
        self._lock = asyncio.Lock()
        self._recent: list[tuple[str, str, int]] = []

    async def append_turn(self, role: str, text: str, interrupted: bool = False) -> int:
        normalized_role = "ai" if role == "assistant" else role
        async with self._lock:
            for old_role, old_text, old_idx in reversed(self._recent):
                if old_role == normalized_role and old_text == text:
                    return old_idx
            async with SessionLocal() as db:
                async with db.begin():
                    interview = await db.scalar(
                        select(InterviewSession)
                        .where(InterviewSession.id == self.session_id)
                        .with_for_update()
                    )
                    if interview is None:
                        raise ValueError("Interview session no longer exists.")
                    last_idx = await db.scalar(
                        select(func.max(Turn.idx)).where(Turn.session_id == self.session_id)
                    )
                    turn_idx = (last_idx if last_idx is not None else -1) + 1
                    db.add(
                        Turn(
                            session_id=self.session_id,
                            idx=turn_idx,
                            role=normalized_role,
                            text=text,
                            interrupted=interrupted,
                        )
                    )
                    live_state = self.state.model_dump(mode="json")
                    active_job_id = (interview.live_state or {}).get("active_job_id")
                    interview.live_state = {**live_state, "active_job_id": active_job_id}
            self._recent.append((normalized_role, text, turn_idx))
            self._recent = self._recent[-20:]
            return turn_idx

    async def save_state(self) -> None:
        async with SessionLocal() as db:
            async with db.begin():
                interview = await db.get(InterviewSession, self.session_id)
                if interview is not None and interview.status == "live":
                    state_dict = self.state.model_dump(mode="json")
                    active_job_id = (interview.live_state or {}).get("active_job_id")
                    interview.live_state = {**state_dict, "active_job_id": active_job_id}

    async def save_evaluation(self, evaluation: EvaluationData) -> None:
        async with SessionLocal() as db:
            async with db.begin():
                exists = await db.scalar(
                    select(EvaluationRow.id).where(
                        EvaluationRow.session_id == self.session_id,
                        EvaluationRow.turn_idx == evaluation.turn_idx,
                    )
                )
                if exists:
                    return
                db.add(
                    EvaluationRow(
                        session_id=self.session_id,
                        turn_idx=evaluation.turn_idx,
                        thread_id=evaluation.thread_id,
                        scored=evaluation.scored,
                        correctness=evaluation.correctness,
                        depth=evaluation.depth,
                        communication=evaluation.communication,
                        quality=(
                            sum(value for value in (
                                evaluation.correctness,
                                evaluation.depth,
                                evaluation.communication,
                            ) if value is not None) / max(1, sum(
                                value is not None for value in (
                                    evaluation.correctness,
                                    evaluation.depth,
                                    evaluation.communication,
                                )
                            ))
                        ),
                        answer_quality=evaluation.answer_quality,
                        goals_covered=evaluation.goals_covered,
                        missed_points=evaluation.missed_points,
                    )
                )


def _post_finalize(session_id: str, job_id: str, end_reason: str) -> None:
    body = json.dumps({"job_id": job_id, "end_reason": end_reason}).encode()
    request = Request(
        f"{settings.api_base_url.rstrip('/')}/api/internal/sessions/{session_id}/finalize",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Internal-Secret": settings.internal_secret,
        },
        method="POST",
    )
    with urlopen(request, timeout=8) as response:
        if response.status >= 400:
            raise RuntimeError(f"Finalize returned HTTP {response.status}.")


async def finalize_with_retry(session_id: str, job_id: str, end_reason: str) -> None:
    for attempt in range(2):
        try:
            await asyncio.to_thread(_post_finalize, session_id, job_id, end_reason)
            return
        except (URLError, TimeoutError, RuntimeError) as exc:
            if attempt:
                logger.warning("Could not finalize session %s (%s).", session_id, type(exc).__name__)
            else:
                await asyncio.sleep(0.5)
