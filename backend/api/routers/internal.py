import hmac
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from common.config import settings
from common.db import get_db
from common.models import InterviewSession
from common.schemas.live import SessionFinalizeRequest
from fastapi import Depends
from api.services.report_generator import generate_report
from api.services.report_service import ensure_pending_report, mark_session_completed


router = APIRouter(prefix="/api/internal", tags=["internal"])


@router.post("/sessions/{session_id}/finalize")
async def finalize_session(
    session_id: str,
    payload: SessionFinalizeRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
    internal_secret: Annotated[str | None, Header(alias="X-Internal-Secret")] = None,
) -> dict[str, bool]:
    expected_secret = settings.internal_secret
    if not internal_secret or not hmac.compare_digest(internal_secret, expected_secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal secret.")
    interview = await db.get(InterviewSession, session_id, with_for_update=True)
    if interview is None:
        raise HTTPException(status_code=404, detail="Interview session not found.")
    current_job_id = (interview.live_state or {}).get("active_job_id")
    changed = False
    if interview.status == "live":
        if payload.end_reason == "abandoned" and payload.job_id is None:
            changed = await mark_session_completed(db, interview, "abandoned")
        elif payload.job_id and current_job_id == payload.job_id:
            changed = await mark_session_completed(db, interview, payload.end_reason)
        else:
            return {"finalized": False}
    elif interview.status != "completed":
        return {"finalized": False}
    report = await ensure_pending_report(db, session_id)
    await db.commit()
    if report.status == "pending":
        background_tasks.add_task(generate_report, session_id)
    return {"finalized": changed or interview.status == "completed"}
