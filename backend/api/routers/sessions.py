from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from api.services.livekit_service import create_session_token
from api.services.plan_generator import profile_snapshot
from api.services.quota import ensure_session_quota
from api.services.session_service import plan_topics, prepare_session
from common.db import get_db
from common.models import InterviewSession, Report, Resume, User
from common.resume_store import read_profile
from common.schemas.plan import (
    PlanSessionRequest,
    PlanSessionResponse,
    SessionDetailResponse,
    SessionListItem,
)
from common.schemas.live import LiveTokenResponse


router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("", response_model=PlanSessionResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_session(
    payload: PlanSessionRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PlanSessionResponse:
    resume = await db.scalar(
        select(Resume).where(
            Resume.id == payload.resume_id,
            Resume.user_id == current_user.id,
            Resume.status == "ready",
        )
    )
    if resume is None:
        raise HTTPException(status_code=404, detail="Ready resume not found.")
    try:
        profile = await read_profile(resume.id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=500, detail="The extracted resume profile is unavailable.") from exc

    await ensure_session_quota(current_user.id, payload.duration_min, db)
    session = InterviewSession(
        user_id=current_user.id,
        resume_id=resume.id,
        mode="resume",
        level=payload.level,
        duration_min=payload.duration_min,
        status="planning",
        profile_snapshot=profile_snapshot(profile),
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    background_tasks.add_task(
        prepare_session, session.id, profile, payload.level, payload.duration_min
    )
    return PlanSessionResponse(id=session.id, status="planning")


@router.get("", response_model=list[SessionListItem])
async def list_sessions(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[SessionListItem]:
    rows = await db.execute(
        select(InterviewSession, Resume.filename, Report.status, Report.data)
        .outerjoin(Resume, InterviewSession.resume_id == Resume.id)
        .outerjoin(Report, InterviewSession.id == Report.session_id)
        .where(InterviewSession.user_id == current_user.id)
        .order_by(InterviewSession.created_at.desc())
    )
    items = []
    for session, filename, report_status, report_data in rows:
        score = None
        if report_status == "ready" and isinstance(report_data, dict):
            raw_score = report_data.get("overall_score")
            if isinstance(raw_score, (int, float)):
                score = round(raw_score)
        items.append(
            SessionListItem(
                id=session.id,
                resume_filename=filename,
                level=session.level,
                duration_min=session.duration_min,
                status=session.status,
                created_at=session.created_at,
                overall_score=score,
                report_status=report_status,
            )
        )
    return items


@router.get("/{session_id}", response_model=SessionDetailResponse)
async def get_session(
    session_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SessionDetailResponse:
    row = await db.execute(
        select(InterviewSession, Resume.filename)
        .outerjoin(Resume, InterviewSession.resume_id == Resume.id)
        .where(InterviewSession.id == session_id, InterviewSession.user_id == current_user.id)
    )
    result = row.first()
    if result is None:
        raise HTTPException(status_code=404, detail="Interview session not found.")
    session, filename = result
    return SessionDetailResponse(
        id=session.id,
        resume_id=session.resume_id,
        resume_filename=filename,
        level=session.level,
        duration_min=session.duration_min,
        status=session.status,
        created_at=session.created_at,
        topics=plan_topics(session),
        error=session.error,
    )


@router.post("/{session_id}/token", response_model=LiveTokenResponse)
async def create_token(
    session_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LiveTokenResponse:
    session = await db.scalar(
        select(InterviewSession).where(
            InterviewSession.id == session_id,
            InterviewSession.user_id == current_user.id,
        )
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Interview session not found.")
    if session.status not in {"ready", "live"}:
        raise HTTPException(status_code=409, detail="This interview is not ready to start.")
    token = create_session_token(
        session, current_user.id, dispatch_agent=session.status == "ready"
    )
    return LiveTokenResponse.model_validate(token)
