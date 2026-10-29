from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.config import settings
from common.models import DailyUsage, InterviewSession


async def ensure_session_quota(user_id: str, requested_min: int, db: AsyncSession) -> None:
    today = datetime.now(UTC).date()
    used = await db.scalar(
        select(DailyUsage.minutes).where(
            DailyUsage.user_id == user_id,
            DailyUsage.date == today,
        )
    ) or 0
    if used + requested_min > settings.daily_minutes_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="This interview would exceed your daily practice limit.",
        )

    live_session_id = await db.scalar(
        select(InterviewSession.id).where(
            InterviewSession.user_id == user_id,
            InterviewSession.status == "live",
        ).limit(1)
    )
    if live_session_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have a live interview in progress.",
        )
