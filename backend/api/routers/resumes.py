from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from api.services.resume_service import process_resume
from common.config import settings
from common.db import get_db
from common.models import Resume, User
from common.resume_store import delete_profile, read_profile
from common.schemas.profile import (
    Profile,
    ResumeDetailResponse,
    ResumeResponse,
    ResumeUploadResponse,
)


router = APIRouter(prefix="/api/resumes", tags=["resumes"])
_PDF_MAGIC = b"%PDF"
_DOCX_MAGIC = b"PK\x03\x04"


def _profile_summary(profile: Profile | None) -> str | None:
    if profile is None:
        return None
    return profile.summary


@router.post("", response_model=ResumeUploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_resume(
    background_tasks: BackgroundTasks,
    file: Annotated[UploadFile, File(...)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ResumeUploadResponse:
    filename = Path(file.filename or "").name
    extension = Path(filename).suffix.lower()
    if extension not in {".pdf", ".docx"}:
        raise HTTPException(status_code=400, detail="Please upload a PDF or DOCX file.")

    content = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    await file.close()
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"The file is too large. Maximum size is {settings.max_upload_mb} MB.",
        )

    expected_magic = _PDF_MAGIC if extension == ".pdf" else _DOCX_MAGIC
    if not content.startswith(expected_magic):
        raise HTTPException(status_code=400, detail="The file contents do not match its extension.")

    resume = Resume(
        user_id=current_user.id,
        filename=filename[:255],
        status="parsing",
    )
    db.add(resume)
    await db.commit()
    await db.refresh(resume)
    background_tasks.add_task(process_resume, resume.id, content, extension)
    return ResumeUploadResponse(id=resume.id, status="parsing")


@router.get("", response_model=list[ResumeResponse])
async def list_resumes(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ResumeResponse]:
    resumes = await db.scalars(
        select(Resume)
        .where(Resume.user_id == current_user.id)
        .order_by(Resume.created_at.desc())
    )
    result: list[ResumeResponse] = []
    for resume in resumes:
        profile = None
        if resume.status == "ready":
            try:
                profile = await read_profile(resume.id)
            except (FileNotFoundError, ValueError):
                profile = None
        result.append(
            ResumeResponse(
                id=resume.id,
                filename=resume.filename,
                status=resume.status,
                created_at=resume.created_at,
                summary=_profile_summary(profile),
                error=resume.error,
            )
        )
    return result


@router.get("/{resume_id}", response_model=ResumeDetailResponse)
async def get_resume(
    resume_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ResumeDetailResponse:
    resume = await db.scalar(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == current_user.id)
    )
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found.")

    profile = None
    if resume.status == "ready":
        try:
            profile = await read_profile(resume.id)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=500, detail="The extracted resume profile is unavailable.") from exc
    return ResumeDetailResponse(
        id=resume.id,
        filename=resume.filename,
        status=resume.status,
        created_at=resume.created_at,
        summary=_profile_summary(profile),
        error=resume.error,
        profile=profile,
    )


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_resume(
    resume_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    resume = await db.scalar(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == current_user.id)
    )
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found.")
    await db.delete(resume)
    await db.commit()
    await delete_profile(resume_id)
