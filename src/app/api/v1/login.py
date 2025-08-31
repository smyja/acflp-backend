from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import settings
from ...core.db.database import async_get_db
from ...core.exceptions.http_exceptions import UnauthorizedException
from ...core.schemas import LoginCredentials, Token
from ...core.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    TokenType,
    authenticate_user,
    create_access_token,
    create_refresh_token,
    verify_token,
)

router = APIRouter(tags=["login"])


@router.post("/login", response_model=Token)
async def login(
    response: Response,
    credentials: LoginCredentials,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> dict[str, str]:
    """Modern JSON-based login endpoint.

    Accepts JSON payload with username/email and password.
    Returns access token and sets refresh token as httpOnly cookie.
    """
    user = await authenticate_user(username_or_email=credentials.username, password=credentials.password, db=db)
    if not user:
        raise UnauthorizedException("Wrong username, email or password.")

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = await create_access_token(data={"sub": user["username"]}, expires_delta=access_token_expires)

    refresh_token = await create_refresh_token(data={"sub": user["username"]})
    max_age = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60

    response.set_cookie(
        key="refresh_token", value=refresh_token, httponly=True, secure=True, samesite="lax", max_age=max_age
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/refresh")
async def refresh_access_token(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(async_get_db)]
) -> dict[str, str]:
    """Refresh access token using refresh token from HTTP-only cookie.

    Returns new access token and optionally new refresh token.
    Implements token rotation for enhanced security.
    """
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise UnauthorizedException("Refresh token missing.")

    user_data = await verify_token(refresh_token, TokenType.REFRESH, db)
    if not user_data:
        raise UnauthorizedException("Invalid refresh token.")

    # Create new access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    new_access_token = await create_access_token(
        data={"sub": user_data.username_or_email},
        expires_delta=access_token_expires
    )

    # Create new refresh token (token rotation)
    new_refresh_token = await create_refresh_token(data={"sub": user_data.username_or_email})
    max_age = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60

    # Set new refresh token as HTTP-only cookie
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=max_age
    )

    return {"access_token": new_access_token, "token_type": "bearer"}
