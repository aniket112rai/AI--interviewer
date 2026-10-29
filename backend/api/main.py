import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from common.config import settings
from common.db import create_tables, dispose_database_engine
from api.routers.auth import router as auth_router
from api.routers.internal import router as internal_router
from api.routers.resumes import router as resumes_router
from api.routers.reports import router as reports_router
from api.routers.sessions import router as sessions_router
from api.services.resume_service import mark_stuck_resumes_failed
from api.services.session_service import mark_stuck_sessions_failed


@asynccontextmanager
async def lifespan(_: FastAPI):
    await create_tables()
    stuck_count = await mark_stuck_resumes_failed()
    if stuck_count:
        logging.getLogger(__name__).info("Marked %s interrupted resume upload(s) as failed.", stuck_count)
    stuck_sessions = await mark_stuck_sessions_failed()
    if stuck_sessions:
        logging.getLogger(__name__).info("Marked %s interrupted interview plan(s) as failed.", stuck_sessions)
    yield
    await dispose_database_engine()


app = FastAPI(title="AI Interviewer API", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(internal_router)
app.include_router(resumes_router)
app.include_router(sessions_router)
app.include_router(reports_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/api/health")
async def health() -> dict[str, bool]:
    return {"ok": True}
