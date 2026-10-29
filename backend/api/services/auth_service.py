import asyncio
import time
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from common.config import settings
from common.models import DailyUsage, User
from common.schemas.user import LoginRequest, UserCreate


_failed_logins: dict[str, list[float]] = {}
_login_limiter_lock = asyncio.Lock()
_MAX_FAILED_LOGINS = 5
_LOGIN_WINDOW_SECONDS = 10 * 60


def user_payload(user: User) -> dict[str, str | datetime]:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "created_at": user.created_at,
    }


def _create_token(user: User) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": user.id,
        "iat": now,
        "exp": now + timedelta(days=settings.jwt_expire_days),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


async def _check_login_limit(email: str) -> None:
    now = time.monotonic()
    async with _login_limiter_lock:
        attempts = [
            attempt for attempt in _failed_logins.get(email, [])
            if now - attempt < _LOGIN_WINDOW_SECONDS
        ]
        _failed_logins[email] = attempts
        if len(attempts) >= _MAX_FAILED_LOGINS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed login attempts. Try again in 10 minutes.",
                headers={"Retry-After": str(_LOGIN_WINDOW_SECONDS)},
            )


async def _record_failed_login(email: str) -> bool:
    async with _login_limiter_lock:
        now = time.monotonic()
        attempts = [
            attempt for attempt in _failed_logins.get(email, [])
            if now - attempt < _LOGIN_WINDOW_SECONDS
        ]
        attempts.append(now)
        _failed_logins[email] = attempts
        return len(attempts) >= _MAX_FAILED_LOGINS


async def _clear_failed_logins(email: str) -> None:
    async with _login_limiter_lock:
        _failed_logins.pop(email, None)


async def signup(payload: UserCreate, db: AsyncSession) -> tuple[User, str]:
    password_hash = await asyncio.to_thread(
        bcrypt.hashpw, payload.password.encode("utf-8"), bcrypt.gensalt()
    )
    user = User(
        email=payload.email,
        name=payload.name or payload.email.partition("@")[0],
        password_hash=password_hash.decode("utf-8"),
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists.") from exc
    await db.refresh(user)
    return user, _create_token(user)


async def login(payload: LoginRequest, db: AsyncSession) -> tuple[User, str]:
    await _check_login_limit(payload.email)
    user = await db.scalar(select(User).where(User.email == payload.email))
    valid_password = False
    if user is not None:
        valid_password = await asyncio.to_thread(
            bcrypt.checkpw,
            payload.password.encode("utf-8"),
            user.password_hash.encode("utf-8"),
        )
    if not valid_password or user is None:
        if await _record_failed_login(payload.email):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed login attempts. Try again in 10 minutes.",
                headers={"Retry-After": str(_LOGIN_WINDOW_SECONDS)},
            )
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    await _clear_failed_logins(payload.email)
    return user, _create_token(user)


def decode_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        user_id = payload.get("sub")
        if not isinstance(user_id, str) or not user_id:
            raise jwt.InvalidTokenError("Token subject missing")
        return user_id
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def today_usage_minutes(user_id: str, db: AsyncSession) -> int:
    today = datetime.now(UTC).date()
    minutes = await db.scalar(
        select(DailyUsage.minutes).where(
            DailyUsage.user_id == user_id,
            DailyUsage.date == today,
        )
    )
    return minutes or 0
