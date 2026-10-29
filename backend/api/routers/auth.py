from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import current_user_response
from api.services.auth_service import login, signup, user_payload
from common.db import get_db
from common.schemas.user import CurrentUserResponse, LoginRequest, TokenResponse, UserCreate


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup_route(
    payload: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    user, token = await signup(payload, db)
    return {"token": token, "user": user_payload(user)}


@router.post("/login", response_model=TokenResponse)
async def login_route(
    payload: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    user, token = await login(payload, db)
    return {"token": token, "user": user_payload(user)}


@router.get("/me", response_model=CurrentUserResponse)
async def me_route(
    response: Annotated[CurrentUserResponse, Depends(current_user_response)],
) -> CurrentUserResponse:
    return response
