from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from api.main import app
from common.db import SessionLocal
from common.models import DailyUsage, User


async def clean_up(email: str) -> None:
    async with SessionLocal() as session:
        async with session.begin():
            user_id = await session.scalar(select(User.id).where(User.email == email))
            if user_id:
                await session.execute(delete(DailyUsage).where(DailyUsage.user_id == user_id))
                await session.execute(delete(User).where(User.id == user_id))


def run_api_check(email: str) -> None:
    with TestClient(app) as client:
        unauthenticated = client.get("/api/auth/me")
        assert unauthenticated.status_code == 401

        signup = client.post(
            "/api/auth/signup",
            json={"email": email, "password": "phase3-check-password", "name": "Phase 3 Check"},
        )
        assert signup.status_code == 201, signup.text
        payload = signup.json()
        assert "token" not in payload and "password_hash" not in payload
        token = signup.cookies["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        me = client.get("/api/auth/me", headers=headers)
        assert me.status_code == 200, me.text
        assert me.json()["email"] == email
        assert me.json()["minutes_used"] == 0

        login = client.post(
            "/api/auth/login", json={"email": email, "password": "phase3-check-password"}
        )
        assert login.status_code == 200, login.text
        refreshed = client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {login.cookies['access_token']}"}
        )
        assert refreshed.status_code == 200

        for attempt in range(5):
            wrong = client.post(
                "/api/auth/login", json={"email": email, "password": "wrong-password"}
            )
            expected = 429 if attempt == 4 else 401
            assert wrong.status_code == expected, wrong.text
if __name__ == "__main__":
    test_email = f"phase3-{uuid4().hex}@example.invalid"
    try:
        run_api_check(test_email)
    finally:
        asyncio.run(clean_up(test_email))
    print("Phase 3 signup, login, protected route, token reuse, and rate-limit checks passed.")
