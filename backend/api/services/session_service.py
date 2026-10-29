import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from api.services.plan_generator import generate_plan
from common.db import SessionLocal
from common.models import InterviewSession
from common.schemas.plan import Plan
from common.schemas.profile import Profile


logger = logging.getLogger(__name__)
_PLAN_ERROR = "We could not prepare this interview. Please try again."


async def prepare_session(session_id: str, profile: Profile, level: str, duration_min: int) -> None:
    try:
        plan = await generate_plan(profile, level, duration_min)
        async with SessionLocal() as db:
            async with db.begin():
                session = await db.get(InterviewSession, session_id)
                if session is None or session.status != "planning":
                    return
                session.plan = plan.model_dump(mode="json")
                session.status = "ready"
                session.error = None
    except Exception as exc:
        logger.warning("Interview plan generation failed (%s).", type(exc).__name__)
        async with SessionLocal() as db:
            async with db.begin():
                session = await db.get(InterviewSession, session_id)
                if session is not None and session.status == "planning":
                    session.status = "failed"
                    session.error = _PLAN_ERROR


async def mark_stuck_sessions_failed() -> int:
    cutoff = datetime.now(UTC) - timedelta(minutes=5)
    async with SessionLocal() as db:
        async with db.begin():
            result = await db.execute(
                update(InterviewSession)
                .where(InterviewSession.status == "planning", InterviewSession.created_at < cutoff)
                .values(status="failed", error="Interview planning stopped before it finished. Please try again.")
            )
            return result.rowcount or 0


def plan_topics(session: InterviewSession) -> list[str]:
    if not session.plan:
        return []
    try:
        plan = Plan.model_validate(session.plan)
    except Exception:
        return []
    return [thread.topic for thread in plan.threads]
