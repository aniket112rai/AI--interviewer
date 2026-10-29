import math
from datetime import UTC, datetime

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from common.models import DailyUsage, InterviewSession, Report as ReportRow, utc_now


async def mark_session_completed(
    db: AsyncSession,
    session: InterviewSession,
    end_reason: str,
) -> bool:
    if session.status != "live":
        return False
    ended_at = utc_now()
    started_at = session.started_at or ended_at
    actual_seconds = max(0, int((ended_at - started_at).total_seconds()))
    actual_minutes = max(1, math.ceil(actual_seconds / 60))
    session.status = "completed"
    session.ended_at = ended_at
    session.duration_sec_actual = actual_seconds
    session.end_reason = end_reason
    usage_insert = insert(DailyUsage).values(
        user_id=session.user_id,
        date=datetime.now(UTC).date(),
        minutes=actual_minutes,
    )
    await db.execute(
        usage_insert.on_conflict_do_update(
            index_elements=[DailyUsage.user_id, DailyUsage.date],
            set_={"minutes": DailyUsage.minutes + actual_minutes},
        )
    )
    return True


async def ensure_pending_report(db: AsyncSession, session_id: str) -> ReportRow:
    report = await db.get(ReportRow, session_id, with_for_update=True)
    if report is None:
        report = ReportRow(session_id=session_id, status="pending")
        db.add(report)
        await db.flush()
    return report
