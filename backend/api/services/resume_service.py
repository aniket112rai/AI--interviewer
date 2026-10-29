import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import update

from api.services.profile_extractor import extract_profile
from api.services.resume_parser import ResumeProcessingError, parse_resume_text
from common.db import SessionLocal
from common.models import Resume
from common.resume_store import delete_profile, resume_path, write_profile


logger = logging.getLogger(__name__)
_GENERIC_PROCESSING_ERROR = "We could not process this resume. Please try another PDF or DOCX file."


async def process_resume(resume_id: str, content: bytes, extension: str) -> None:
    try:
        async with SessionLocal() as db:
            resume = await db.get(Resume, resume_id)
            if resume is None or resume.status != "parsing":
                return

        extracted_text = await asyncio.to_thread(parse_resume_text, content, extension)
        profile = await extract_profile(extracted_text)
        await write_profile(resume_id, profile)

        async with SessionLocal() as db:
            async with db.begin():
                resume = await db.get(Resume, resume_id)
                if resume is None or resume.status != "parsing":
                    await delete_profile(resume_id)
                    return
                resume.profile_path = str(resume_path(resume_id))
                resume.status = "ready"
                resume.error = None
                resume.updated_at = datetime.now(UTC)
    except Exception as exc:
        await delete_profile(resume_id)
        readable_error = exc.args[0] if isinstance(exc, ResumeProcessingError) and exc.args else _GENERIC_PROCESSING_ERROR
        async with SessionLocal() as db:
            async with db.begin():
                resume = await db.get(Resume, resume_id)
                if resume is not None and resume.status == "parsing":
                    resume.status = "failed"
                    resume.error = str(readable_error)[:500]
                    resume.updated_at = datetime.now(UTC)
        if not isinstance(exc, ResumeProcessingError):
            logger.warning("Resume processing failed (%s).", type(exc).__name__)


async def mark_stuck_resumes_failed() -> int:
    cutoff = datetime.now(UTC) - timedelta(minutes=5)
    now = datetime.now(UTC)
    async with SessionLocal() as db:
        async with db.begin():
            result = await db.execute(
                update(Resume)
                .where(Resume.status == "parsing", Resume.created_at < cutoff)
                .values(
                    status="failed",
                    error="Resume processing stopped before it finished. Please upload it again.",
                    updated_at=now,
                )
            )
            return result.rowcount or 0
