from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import current_user_response
from api.services.auth_service import login, signup, user_payload
from common.config import settings
from common.db import get_db
from common.schemas.user import CurrentUserResponse, LoginRequest, UserResponse, UserCreate


router = APIRouter(prefix="/api/auth", tags=["auth"])
AUTH_COOKIE = "access_token"


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        AUTH_COOKIE,
        token,
        max_age=settings.jwt_expire_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.api_base_url.lower().startswith("https://"),
        samesite="lax",
        path="/",
    )


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def signup_route(
    payload: UserCreate,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    user, token = await signup(payload, db)
    _set_auth_cookie(response, token)
    return user_payload(user)


@router.post("/login", response_model=UserResponse)
async def login_route(
    payload: LoginRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    user, token = await login(payload, db)
    _set_auth_cookie(response, token)
    return user_payload(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout_route(response: Response) -> Response:
    response.delete_cookie(AUTH_COOKIE, path="/", httponly=True, secure=settings.api_base_url.lower().startswith("https://"), samesite="lax")
    return response


@router.get("/me", response_model=CurrentUserResponse)
async def me_route(
    response: Annotated[CurrentUserResponse, Depends(current_user_response)],
) -> CurrentUserResponse:
    return response
