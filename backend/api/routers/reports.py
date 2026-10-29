from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from api.services.report_generator import generate_report
from api.services.report_service import ensure_pending_report, mark_session_completed
from common.db import get_db
from common.models import InterviewSession, Report as ReportRow, Turn, User
from common.schemas.report import ReportResponse


router = APIRouter(prefix="/api/sessions", tags=["reports"])
ABANDONED_AFTER = timedelta(minutes=3)


@router.get("/{session_id}/report", response_model=ReportResponse)
async def get_report(
    session_id: str,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReportResponse:
    session = await db.scalar(
        select(InterviewSession)
        .where(
            InterviewSession.id == session_id,
            InterviewSession.user_id == current_user.id,
        )
        .with_for_update()
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Interview session not found.")

    if session.status == "live":
        last_turn_at = await db.scalar(
            select(Turn.created_at)
            .where(Turn.session_id == session_id)
            .order_by(Turn.idx.desc())
            .limit(1)
        )
        activity_at = last_turn_at or session.started_at or session.created_at
        if datetime.now(UTC) - activity_at >= ABANDONED_AFTER:
            await mark_session_completed(db, session, "abandoned")
        else:
            await db.commit()
            raise HTTPException(status_code=409, detail="This interview is still in progress.")

    if session.status != "completed":
        await db.commit()
        raise HTTPException(status_code=409, detail="A report is available after the interview is completed.")

    report = await ensure_pending_report(db, session_id)
    await db.commit()
    if report.status == "pending":
        background_tasks.add_task(generate_report, session_id)
    return ReportResponse(
        session_id=session_id,
        status=report.status,
        report=report.data if report.status == "ready" else None,
    )
