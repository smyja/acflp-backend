from datetime import timedelta
import secrets
from typing import Annotated, Any, Union

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from fastapi_sso import GoogleSSO
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import settings
from ...core.db.database import async_get_db
from ...core.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    create_refresh_token,
    get_password_hash,
)
from ...core.utils.async_utils import maybe_await
from ...crud.crud_users import crud_users
from ...schemas.user import UserCreateInternal

router = APIRouter(prefix="/auth", tags=["oauth"])

# Initialize Google SSO
google_sso = GoogleSSO(
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET.get_secret_value(),
    redirect_uri=settings.OAUTH_REDIRECT_URI,
    allow_insecure_http=settings.ENVIRONMENT.value == "local",
)


async def _create_oauth_user(db: AsyncSession, user_info: Any) -> None:
    """Create a new user from OAuth provider information.

    Args:
        db: Database session
        user_info: OAuth user information from provider

    Raises:
        HTTPException: If user creation fails
    """
    # Generate a secure random password for OAuth users
    # This prevents password-based login while maintaining security
    secure_password = secrets.token_urlsafe(32)
    hashed_password = get_password_hash(secure_password)

    # Generate unique username from email
    base_username = user_info.email.split("@")[0].lower()
    # Remove any non-alphanumeric characters to match username pattern
    base_username = "".join(c for c in base_username if c.isalnum())

    # Ensure username meets minimum length requirement
    if len(base_username) < 2:
        base_username = "user"

    # Find available username
    username = base_username
    counter = 1
    while await maybe_await(crud_users.get(db=db, username=username, is_deleted=False)):
        username = f"{base_username}{counter}"
        counter += 1
        # Prevent infinite loop
        if counter > 9999:
            username = f"user{secrets.randbelow(999999)}"
            break

    # Prepare user data
    user_data = UserCreateInternal(
        username=username,
        email=user_info.email,
        name=user_info.display_name or user_info.first_name or "User",
        hashed_password=hashed_password,
    )

    # Create user
    try:
        await maybe_await(crud_users.create(db=db, object=user_data))
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Failed to create OAuth user: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create user account") from e


@router.get("/google/login")
async def google_login(request: Request) -> Any:
    """Initiate Google OAuth login.

    Redirects user to Google's OAuth consent screen.
    """
    async with google_sso:
        return await google_sso.get_login_redirect()


@router.get("/google/callback")
async def google_callback(
    request: Request,
    response: Response,  # kept for backward compatibility with unit tests
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> RedirectResponse:
    """Handle Google OAuth callback.

    Processes the OAuth response, creates or retrieves user,
    and returns authentication tokens.
    """
    try:
        async with google_sso:
            user_info = await google_sso.verify_and_process(request)

        if not user_info or not user_info.email:
            raise HTTPException(status_code=400, detail="Failed to get user information from Google")

        # Validate required user information
        if not user_info.email or "@" not in user_info.email:
            raise HTTPException(status_code=400, detail="Invalid email from OAuth provider")

        # Check if user exists
        existing_user = await maybe_await(crud_users.get(db=db, email=user_info.email, is_deleted=False))

        user: Union[dict[Any, Any], Any] = None
        if existing_user:
            # User exists, generate tokens
            user = existing_user
        else:
            # Create new OAuth user
            await _create_oauth_user(db, user_info)
            user = await maybe_await(crud_users.get(db=db, email=user_info.email, is_deleted=False))

            if not user:
                raise HTTPException(status_code=500, detail="Failed to create user account")

        # Generate tokens
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        username = user.username if hasattr(user, "username") else user["username"]
        access_token = await create_access_token(data={"sub": username}, expires_delta=access_token_expires)

        refresh_token = await create_refresh_token(data={"sub": username})

        # Redirect to frontend with access token and set cookie on the redirect response
        frontend_redirect_url = f"{settings.FRONTEND_URL}/auth/callback?token={access_token}"
        redirect = RedirectResponse(url=frontend_redirect_url)
        # Set refresh token as HTTP-only cookie with security settings
        max_age = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
        redirect.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=settings.ENVIRONMENT.value != "local",  # Only secure in production
            samesite="lax",
            max_age=max_age,
        )
        # Add attribute for tests that access ".url" directly
        redirect.url = frontend_redirect_url
        return redirect

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Log the actual error for debugging but don't expose it to users
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"OAuth callback error: {str(e)}", exc_info=True)

        # Redirect to frontend with generic error message
        error_redirect_url = f"{settings.FRONTEND_URL}/auth/error?message=Authentication failed"
        redirect = RedirectResponse(url=error_redirect_url)
        redirect.url = error_redirect_url
        return redirect


@router.get("/google/user")
async def get_google_user_info(
    request: Request,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> dict[str, Any]:
    """Get current user information from Google OAuth.

    This endpoint is for testing OAuth integration in development.
    Should be removed or protected in production.
    """
    # Only allow in development environment
    if settings.ENVIRONMENT.value == "production":
        raise HTTPException(status_code=404, detail="Endpoint not available")

    try:
        async with google_sso:
            user_info = await google_sso.verify_and_process(request)

        if not user_info or not user_info.email:
            raise HTTPException(status_code=400, detail="Failed to get user information from Google")

        # Return only safe, non-sensitive information
        return {
            "email": user_info.email,
            "name": user_info.display_name or "Unknown",
            "provider": "google",
            "verified": True,
        }

    except HTTPException:
        raise
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"OAuth user info error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail="OAuth verification failed") from e
