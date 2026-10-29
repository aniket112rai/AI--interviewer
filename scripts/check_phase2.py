import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import common.resume_store as resume_store
from common.db import SessionLocal, create_tables, dispose_database_engine
from common.models import DailyUsage, Evaluation as EvaluationRow, InterviewSession, Report as ReportRow
from common.models import Resume as ResumeRow, Turn, User
from common.resume_store import delete_profile, read_profile, resume_path, write_profile
from common.schemas.evaluation import Evaluation
from common.schemas.live import LiveState
from common.schemas.plan import Plan
from common.schemas.profile import Profile


def sample_plan() -> Plan:
    return Plan.model_validate(
        {
            "opening": {"text": "Hi, thanks for joining."},
            "closing": {"text": "That's all my questions."},
            "opening_sec": 120,
            "closing_sec": 120,
            "threads": [
                {
                    "id": "t1",
                    "phase": "project",
                    "topic": "Payment service reliability",
                    "weight": 1.0,
                    "time_budget_sec": 300,
                    "max_followups": 3,
                    "difficulty_start": "medium",
                    "context": ["Built a payment service."],
                    "goals": ["failure handling"],
                    "rubric": {"strong": "Specific", "average": "Some detail", "weak": "Vague"},
                    "seed_question": "How did you handle failures?",
                }
            ],
        }
    )


async def check_atomic_profile_write(resume_id: str, profile: Profile) -> None:
    target = resume_path(resume_id)
    await write_profile(resume_id, profile)
    original_dump = resume_store.json.dump

    def interrupted_dump(*args, **kwargs) -> None:
        args[1].write('{"summary":"partial')
        args[1].flush()
        raise OSError("simulated interrupted write")

    resume_store.json.dump = interrupted_dump
    try:
        try:
            await write_profile(resume_id, Profile(summary="must not replace the complete file"))
        except OSError:
            pass
        else:
            raise AssertionError("the interrupted profile write unexpectedly succeeded")
    finally:
        resume_store.json.dump = original_dump

    assert await read_profile(resume_id) == profile
    assert not list(target.parent.glob(f".{target.stem}.*.tmp"))


async def run_check() -> None:
    await create_tables()
    user_id = uuid4().hex
    resume_id = uuid4().hex
    session_id = uuid4().hex
    profile = Profile(
        summary="Backend engineer with experience building reliable services.",
        seniority="mid",
        total_experience_years=2.5,
        skills=["Python", "PostgreSQL"],
        primary_stack=["Python", "PostgreSQL"],
        achievements=["Improved service reliability."],
        probe_targets=["Failure handling", "Idempotency", "Retry strategy"],
    )
    plan = sample_plan()
    live_state = LiveState(goals_covered={"t1": []})
    evaluation = Evaluation(
        turn_idx=1,
        thread_id="t1",
        scored=True,
        correctness=0.8,
        depth=0.7,
        communication=0.9,
        quality=0.8,
        goals_covered=["failure handling"],
        missed_points=["idempotency"],
    )
    profile_written = False
    usage_date = datetime.now(UTC).date()

    try:
        async with SessionLocal() as session:
            async with session.begin():
                user = User(
                    id=user_id,
                    email=f"phase2-{user_id}@example.invalid",
                    name="Phase 2 Check",
                    password_hash="not-a-real-password-hash",
                )
                resume = ResumeRow(
                    id=resume_id, user_id=user_id, filename="sample.pdf", status="ready"
                )
                interview = InterviewSession(
                    id=session_id,
                    user_id=user_id,
                    resume_id=resume_id,
                    mode="resume",
                    level="mid",
                    duration_min=15,
                    status="ready",
                    plan=plan.model_dump(mode="json"),
                    live_state=live_state.model_dump(mode="json"),
                )
                usage = DailyUsage(user_id=user_id, date=usage_date, minutes=0)
                session.add(user)
                await session.flush()
                session.add(resume)
                await session.flush()
                session.add(interview)
                await session.flush()
                session.add_all(
                    [
                        usage,
                        Turn(
                            session_id=session_id,
                            idx=1,
                            role="user",
                            text="I added retries and idempotency keys.",
                        ),
                        EvaluationRow(session_id=session_id, **evaluation.model_dump()),
                        ReportRow(session_id=session_id, status="pending"),
                    ]
                )

        async with SessionLocal() as session:
            user = await session.get(User, user_id)
            resume = await session.get(ResumeRow, resume_id)
            interview = await session.get(InterviewSession, session_id)
            turn_id = (await session.execute(
                select(Turn.id).where(Turn.session_id == session_id)
            )).scalar_one()
            turn = await session.get(Turn, turn_id)
            scored = await session.get(
                EvaluationRow,
                (await session.execute(
                    select(EvaluationRow.id).where(
                        EvaluationRow.session_id == session_id
                    )
                )).scalar_one(),
            )
            usage = await session.get(DailyUsage, (user_id, usage_date))
            report = await session.get(ReportRow, session_id)
            assert user and user.id == user_id
            assert resume and resume.status == "ready"
            assert interview and interview.plan["threads"][0]["id"] == "t1"
            assert turn and turn.role == "user"
            assert scored and scored.goals_covered == ["failure handling"]
            assert usage and usage.minutes == 0
            assert report and report.status == "pending"

        await check_atomic_profile_write(resume_id, profile)
        profile_written = True
        print("Phase 2 database and atomic profile checks passed.")
    finally:
        if profile_written or resume_path(resume_id).exists():
            await delete_profile(resume_id)
        async with SessionLocal() as session:
            async with session.begin():
                await session.execute(delete(ReportRow).where(ReportRow.session_id == session_id))
                await session.execute(delete(EvaluationRow).where(EvaluationRow.session_id == session_id))
                await session.execute(delete(Turn).where(Turn.session_id == session_id))
                await session.execute(delete(InterviewSession).where(InterviewSession.id == session_id))
                await session.execute(delete(ResumeRow).where(ResumeRow.id == resume_id))
                await session.execute(
                    delete(DailyUsage).where(
                        DailyUsage.user_id == user_id, DailyUsage.date == usage_date
                    )
                )
                await session.execute(delete(User).where(User.id == user_id))
        await dispose_database_engine()


if __name__ == "__main__":
    asyncio.run(run_check())
