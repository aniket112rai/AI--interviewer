from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from api.main import app
from common.config import settings
from common.db import SessionLocal, dispose_database_engine
from common.models import DailyUsage, InterviewSession, Resume, User
from common.resume_store import delete_profile, write_profile
from common.schemas.profile import Profile


TEST_EMAIL = f"phase5-{uuid4().hex}@example.invalid"


def make_profile() -> Profile:
    return Profile(
        summary="Software engineer with hands-on experience building payment and inventory systems.",
        seniority="mid",
        total_experience_years=3.0,
        skills=["Python", "FastAPI", "PostgreSQL", "React", "AWS"],
        primary_stack=["Python", "FastAPI", "PostgreSQL", "React"],
        experience=[
            {
                "company": "Northstar Commerce",
                "role": "Software Engineer",
                "duration_months": 36,
                "tech": ["Python", "FastAPI", "PostgreSQL"],
                "responsibilities": ["Owned a payment API serving 50,000 requests per day."],
                "achievements": ["Reduced duplicate charges by 42 percent."],
            }
        ],
        projects=[
            {
                "name": "Payment reliability service",
                "description": "Retry-safe payment processing with idempotency keys.",
                "stack": ["Python", "FastAPI", "PostgreSQL"],
                "achievements": ["Improved p95 latency from 800 ms to 220 ms."],
            },
            {
                "name": "Inventory reconciliation platform",
                "description": "Reconciled daily settlement files for commerce operations.",
                "stack": ["Python", "AWS", "PostgreSQL"],
                "achievements": ["Reduced manual investigation by 60 percent."],
            },
        ],
        achievements=["Handled 50,000 daily API requests."],
        probe_targets=[
            "Verify how the 50,000 requests per day figure was measured.",
            "Clarify ownership of the idempotency design.",
            "Explore the PostgreSQL query and indexing decisions.",
        ],
    )


async def prepare_test_resume(profile: Profile) -> tuple[str, str, str, str]:
    quota_email = f"phase5-quota-{uuid4().hex}@example.invalid"
    async with SessionLocal() as db:
        async with db.begin():
            user = User(
                email=TEST_EMAIL,
                name="Phase 5 Check",
                password_hash="unused-check-hash",
            )
            db.add(user)
            await db.flush()
            resume = Resume(user_id=user.id, filename="phase5-resume.pdf", status="ready")
            db.add(resume)
            await db.flush()
            resume_id = resume.id
            user_id = user.id
            quota_user = User(
                email=quota_email,
                name="Phase 5 Quota Check",
                password_hash="unused-check-hash",
            )
            db.add(quota_user)
            await db.flush()
            quota_resume = Resume(
                user_id=quota_user.id, filename="phase5-quota-resume.pdf", status="ready"
            )
            db.add(quota_resume)
            await db.flush()
            quota_user_id = quota_user.id
            quota_resume_id = quota_resume.id
            db.add(
                DailyUsage(
                    user_id=quota_user_id,
                    date=datetime.now(UTC).date(),
                    minutes=settings.daily_minutes_limit - 1,
                )
            )
    await write_profile(resume_id, profile)
    await write_profile(quota_resume_id, profile)
    await dispose_database_engine()
    return user_id, resume_id, quota_user_id, quota_resume_id


def run_api_check(
    user_id: str,
    resume_id: str,
    quota_user_id: str,
    quota_resume_id: str,
    durations: tuple[int, ...],
) -> list[str]:
    created_ids: list[str] = []
    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {_create_token_for_id(user_id)}"}
        for duration in durations:
            response = client.post(
                "/api/sessions",
                headers=headers,
                json={"resume_id": resume_id, "level": "mid", "duration_min": duration},
            )
            assert response.status_code == 202, response.text
            session_id = response.json()["id"]
            created_ids.append(session_id)
            details = client.get(f"/api/sessions/{session_id}", headers=headers)
            assert details.status_code == 200, details.text
            session = details.json()
            assert session["status"] == "ready", session
            assert len(session["topics"]) == {15: 3, 30: 5, 45: 8}[duration], session
            assert all(isinstance(topic, str) and topic.strip() for topic in session["topics"])
            assert not any(key in session for key in ("plan", "rubric", "goals", "seed_question"))

            token_response = client.post(f"/api/sessions/{session_id}/token", headers=headers)
            assert token_response.status_code == 200, token_response.text
            token_data = token_response.json()
            assert token_data["room"] == session_id
            assert token_data["url"] == settings.livekit_url
            assert token_data["token"]

        listed = client.get("/api/sessions", headers=headers)
        assert listed.status_code == 200, listed.text
        assert {item["id"] for item in listed.json()} >= set(created_ids)
        assert client.get("/api/dev/token", headers=headers).status_code == 404

        blocked = client.post(
            "/api/sessions",
            headers={"Authorization": f"Bearer {_create_token_for_id(quota_user_id)}"},
            json={"resume_id": quota_resume_id, "level": "mid", "duration_min": 15},
        )
        assert blocked.status_code == 429, blocked.text
    return created_ids


def _create_token_for_id(user_id: str) -> str:
    from datetime import timedelta
    import jwt

    from common.config import settings

    now = datetime.now(UTC)
    return jwt.encode(
        {"sub": user_id, "iat": now, "exp": now + timedelta(days=settings.jwt_expire_days)},
        settings.jwt_secret,
        algorithm="HS256",
    )


async def cleanup(
    user_id: str,
    resume_id: str,
    quota_user_id: str,
    quota_resume_id: str,
    session_ids: list[str],
) -> None:
    await dispose_database_engine()
    await delete_profile(quota_resume_id)
    await delete_profile(resume_id)
    async with SessionLocal() as db:
        async with db.begin():
            if session_ids:
                await db.execute(delete(InterviewSession).where(InterviewSession.id.in_(session_ids)))
            user_ids = [user_id, quota_user_id]
            await db.execute(delete(DailyUsage).where(DailyUsage.user_id.in_(user_ids)))
            await db.execute(delete(User).where(User.id.in_(user_ids)))
    await dispose_database_engine()


if __name__ == "__main__":
    profile = make_profile()
    user_id, resume_id, quota_user_id, quota_resume_id = asyncio.run(prepare_test_resume(profile))
    session_ids: list[str] = []
    try:
        session_ids = run_api_check(
            user_id, resume_id, quota_user_id, quota_resume_id, (15, 30, 45)
        )
    finally:
        asyncio.run(cleanup(user_id, resume_id, quota_user_id, quota_resume_id, session_ids))
    print("Phase 5 15/30/45-minute plans, topic privacy, token, dev-token removal, and quota checks passed.")
