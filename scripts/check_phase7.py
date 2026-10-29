"""Exercise report creation against a temporary synthetic interview, then remove it."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import delete, select

from api.routers.internal import finalize_session
from api.routers.reports import get_report
from common.db import SessionLocal
from common.models import DailyUsage, Evaluation, InterviewSession, Report, Turn, User
from common.schemas.live import SessionFinalizeRequest
from common.config import settings
from fastapi import BackgroundTasks


def _sample_plan() -> dict:
    return {
        "opening": {"text": "Welcome. Please introduce yourself."},
        "closing": {"text": "Thank you for your time."},
        "opening_sec": 30,
        "closing_sec": 30,
        "threads": [{
            "id": "t1",
            "phase": "project",
            "topic": "Inventory API reliability",
            "weight": 1.0,
            "time_budget_sec": 600,
            "max_followups": 3,
            "difficulty_start": "medium",
            "context": ["Built an inventory API", "Added retry handling"],
            "goals": ["Explain retry behavior", "Describe how failures were measured"],
            "rubric": {
                "strong": "Explains bounded retries and measured failure rates.",
                "average": "Describes retries but gives limited evidence.",
                "weak": "Cannot explain retry behavior or its impact.",
            },
            "seed_question": "How did you make the inventory API resilient to failures?",
        }],
    }


async def main() -> None:
    session_id = uuid4().hex
    user_id = uuid4().hex
    now = datetime.now(UTC)
    try:
        async with SessionLocal() as db:
            db.add(User(
                id=user_id,
                email=f"phase7-check-{user_id}@example.invalid",
                name="Phase 7 Check",
                password_hash="unused-temporary-check-hash",
            ))
            await db.flush()
            db.add(InterviewSession(
                id=session_id,
                user_id=user_id,
                level="mid",
                duration_min=15,
                status="live",
                plan=_sample_plan(),
                profile_snapshot={},
                live_state={"active_job_id": "phase7-check"},
                started_at=now - timedelta(minutes=4),
            ))
            await db.flush()
            for idx, role, text_value in [
                (0, "ai", "Welcome. Please introduce yourself."),
                (1, "user", "I built an inventory API and added bounded retries. We capped attempts at three so a downstream outage would not create a retry storm. We tracked failed requests before and after the change, and the rate dropped from about eight percent to two percent."),
                (2, "ai", "How did you decide on three attempts?"),
                (3, "user", "We tested several limits under load. Three attempts recovered transient errors while keeping tail latency acceptable. We also used backoff and logged exhausted retries for follow-up."),
                (4, "ai", "What would you improve next?"),
                (5, "user", "I would add a dashboard for retry exhaustion and split metrics by dependency. That would help us spot a failing downstream service sooner and decide whether to open a circuit."),
            ]:
                db.add(Turn(
                    session_id=session_id,
                    idx=idx,
                    role=role,
                    text=text_value,
                    interrupted=False,
                ))
            for idx, goals, quality, score in [
                (1, ["Explain retry behavior", "Describe how failures were measured"], "strong", 0.86),
                (3, ["Explain retry behavior"], "strong", 0.82),
                (5, [], "partial", 0.68),
            ]:
                db.add(Evaluation(
                    session_id=session_id,
                    turn_idx=idx,
                    thread_id="t1",
                    scored=True,
                    correctness=score,
                    depth=score,
                    communication=score,
                    quality=score,
                    answer_quality=quality,
                    goals_covered=goals,
                    missed_points=[],
                ))
            await db.commit()

        finalize_tasks = BackgroundTasks()
        async with SessionLocal() as db:
            finalized = await finalize_session(
                session_id,
                SessionFinalizeRequest(job_id="phase7-check", end_reason="candidate_ended"),
                finalize_tasks,
                db,
                settings.internal_secret,
            )
            assert finalized["finalized"]
        await finalize_tasks()
        async with SessionLocal() as db:
            report = await db.get(Report, session_id)
            assert report is not None and report.status == "ready", "report generation did not reach ready"
            data = dict(report.data or {})
            assert len(data.get("strengths", [])) == 3
            assert len(data.get("gaps", [])) == 3
            assert 3 <= len(data.get("next_steps", [])) <= 5
            saved_data = data
            saved_updated_at = report.updated_at
            usage = await db.scalar(select(DailyUsage).where(DailyUsage.user_id == user_id))
            assert usage is not None and usage.minutes >= 4
            saved_usage_minutes = usage.minutes

        repeated_finalize_tasks = BackgroundTasks()
        async with SessionLocal() as db:
            repeated = await finalize_session(
                session_id,
                SessionFinalizeRequest(job_id="phase7-check", end_reason="candidate_ended"),
                repeated_finalize_tasks,
                db,
                settings.internal_secret,
            )
            assert repeated["finalized"]
            current_user = await db.get(User, user_id)
            assert current_user is not None
            response = await get_report(
                session_id,
                BackgroundTasks(),
                current_user,
                db,
            )
            assert response.status == "ready" and response.report is not None
        await repeated_finalize_tasks()
        async with SessionLocal() as db:
            report = await db.get(Report, session_id)
            usage = await db.scalar(select(DailyUsage).where(DailyUsage.user_id == user_id))
            assert report is not None and report.data == saved_data
            assert report.updated_at == saved_updated_at
            assert usage is not None and usage.minutes == saved_usage_minutes
        print("Phase 7 report schema, generation, and idempotent refresh checks: passed")
    finally:
        async with SessionLocal() as db:
            async with db.begin():
                await db.execute(delete(InterviewSession).where(InterviewSession.id == session_id))
                await db.execute(delete(DailyUsage).where(DailyUsage.user_id == user_id))
                await db.execute(delete(User).where(User.id == user_id))


if __name__ == "__main__":
    asyncio.run(main())
