"""
Tests for OAuth authentication endpoints.
"""

from unittest.mock import AsyncMock, Mock, patch

from fastapi import HTTPException, Request, Response
from fastapi.responses import RedirectResponse
import pytest
from src.app.api.v1.oauth import (
    _create_oauth_user,
    get_google_user_info,
    google_callback,
    google_login,
)
from src.app.core.config import settings
from src.app.schemas.user import UserCreateInternal


class MockUserInfo:
    """
    Mock user info from OAuth provider.
    """

    def __init__(self, email: str = "test@example.com", display_name: str = "Test User", first_name: str = "Test"):
        self.email = email
        self.display_name = display_name
        self.first_name = first_name


class TestCreateOAuthUser:
    """
    Test OAuth user creation functionality.
    """

    @pytest.mark.asyncio
    async def test_create_oauth_user_success(self, mock_db):
        """
        Test successful OAuth user creation.
        """
        user_info = MockUserInfo(email="newuser@example.com", display_name="New User")

        with patch("src.app.api.v1.oauth.crud_users") as mock_crud, patch(
            "src.app.api.v1.oauth.get_password_hash"
        ) as mock_hash, patch("src.app.api.v1.oauth.secrets.token_urlsafe") as mock_token:
            mock_token.return_value = "secure_random_password"
            mock_hash.return_value = "hashed_password"
            mock_crud.get = AsyncMock(return_value=None)  # Username available
            mock_crud.create = AsyncMock(return_value=None)

            await _create_oauth_user(mock_db, user_info)

            # Verify user creation was called
            mock_crud.create.assert_called_once()
            call_args = mock_crud.create.call_args
            user_data = call_args.kwargs["object"]

            assert isinstance(user_data, UserCreateInternal)
            assert user_data.email == "newuser@example.com"
            assert user_data.name == "New User"
            assert user_data.hashed_password == "hashed_password"
            assert user_data.username == "newuser"

    @pytest.mark.asyncio
    async def test_create_oauth_user_username_conflict(self, mock_db):
        """
        Test OAuth user creation with username conflict.
        """
        user_info = MockUserInfo(email="test@example.com", display_name="Test User")

        with patch("src.app.api.v1.oauth.crud_users") as mock_crud, patch(
            "src.app.api.v1.oauth.get_password_hash"
        ) as mock_hash, patch("src.app.api.v1.oauth.secrets.token_urlsafe") as mock_token:
            mock_token.return_value = "secure_random_password"
            mock_hash.return_value = "hashed_password"

            # Simulate username conflict - first call returns existing user, second returns None
            mock_crud.get = AsyncMock(side_effect=[Mock(), None])  # First username taken, second available
            mock_crud.create = AsyncMock(return_value=None)

            await _create_oauth_user(mock_db, user_info)

            # Verify user creation was called with incremented username
            mock_crud.create.assert_called_once()
            call_args = mock_crud.create.call_args
            user_data = call_args.kwargs["object"]

            assert user_data.username == "test1"  # Should be incremented

    @pytest.mark.asyncio
    async def test_create_oauth_user_short_username(self, mock_db):
        """
        Test OAuth user creation with very short email prefix.
        """
        user_info = MockUserInfo(email="a@example.com", display_name="A User")

        with patch("src.app.api.v1.oauth.crud_users") as mock_crud, patch(
            "src.app.api.v1.oauth.get_password_hash"
        ) as mock_hash, patch("src.app.api.v1.oauth.secrets.token_urlsafe") as mock_token:
            mock_token.return_value = "secure_random_password"
            mock_hash.return_value = "hashed_password"
            mock_crud.get = AsyncMock(return_value=None)
            mock_crud.create = AsyncMock(return_value=None)

            await _create_oauth_user(mock_db, user_info)

            # Verify fallback username is used
            call_args = mock_crud.create.call_args
            user_data = call_args.kwargs["object"]
            assert user_data.username == "user"  # Should fallback to "user"

    @pytest.mark.asyncio
    async def test_create_oauth_user_max_attempts(self, mock_db):
        """
        Test OAuth user creation when max username attempts reached.
        """
        user_info = MockUserInfo(email="test@example.com", display_name="Test User")

        with patch("src.app.api.v1.oauth.crud_users") as mock_crud, patch(
            "src.app.api.v1.oauth.get_password_hash"
        ) as mock_hash, patch("src.app.api.v1.oauth.secrets.token_urlsafe") as mock_token, patch(
            "src.app.api.v1.oauth.secrets.randbelow"
        ) as mock_randbelow:
            mock_token.return_value = "secure_random_password"
            mock_hash.return_value = "hashed_password"
            mock_randbelow.return_value = 123456

            # Simulate all usernames taken until max attempts
            mock_crud.get = AsyncMock(side_effect=[Mock()] * 10000 + [None])  # All taken, then available
            mock_crud.create = AsyncMock(return_value=None)

            await _create_oauth_user(mock_db, user_info)

            # Verify random username is used
            call_args = mock_crud.create.call_args
            user_data = call_args.kwargs["object"]
            assert user_data.username == "user123456"

    @pytest.mark.asyncio
    async def test_create_oauth_user_database_error(self, mock_db):
        """
        Test OAuth user creation with database error.
        """
        user_info = MockUserInfo(email="test@example.com", display_name="Test User")

        with patch("src.app.api.v1.oauth.crud_users") as mock_crud, patch(
            "src.app.api.v1.oauth.get_password_hash"
        ) as mock_hash, patch("src.app.api.v1.oauth.secrets.token_urlsafe") as mock_token:
            mock_token.return_value = "secure_random_password"
            mock_hash.return_value = "hashed_password"
            mock_crud.get = AsyncMock(return_value=None)
            mock_crud.create = AsyncMock(side_effect=Exception("Database error"))

            with pytest.raises(HTTPException) as exc_info:
                await _create_oauth_user(mock_db, user_info)

            assert exc_info.value.status_code == 500
            assert "Failed to create user account" in str(exc_info.value.detail)


class TestGoogleLogin:
    """
    Test Google OAuth login initiation.
    """

    @pytest.mark.asyncio
    async def test_google_login_success(self):
        """
        Test successful Google login initiation.
        """
        request = Mock(spec=Request)

        with patch("src.app.api.v1.oauth.google_sso") as mock_sso:
            mock_redirect = Mock()
            mock_sso.get_login_redirect = AsyncMock(return_value=mock_redirect)

            result = await google_login(request)

            assert result == mock_redirect
            mock_sso.get_login_redirect.assert_called_once()


class TestGoogleCallback:
    """
    Test Google OAuth callback handling.
    """

    @pytest.mark.asyncio
    async def test_google_callback_existing_user(self, mock_db):
        """
        Test Google callback with existing user.
        """
        request = Mock(spec=Request)
        response = Mock(spec=Response)
        user_info = MockUserInfo(email="existing@example.com", display_name="Existing User")
        existing_user = Mock()
        existing_user.username = "existing_user"

        with patch("src.app.api.v1.oauth.google_sso") as mock_sso, patch(
            "src.app.api.v1.oauth.crud_users"
        ) as mock_crud, patch("src.app.api.v1.oauth.create_access_token") as mock_access_token, patch(
            "src.app.api.v1.oauth.create_refresh_token"
        ) as mock_refresh_token:
            mock_sso.verify_and_process = AsyncMock(return_value=user_info)
            mock_crud.get = AsyncMock(return_value=existing_user)
            mock_access_token.return_value = "access_token_123"
            mock_refresh_token.return_value = "refresh_token_123"

            result = await google_callback(request, response, mock_db)

            assert isinstance(result, RedirectResponse)
            # Check the Location header instead of url attribute
            location_header = result.headers.get("location", "")
            assert "token=access_token_123" in location_header
            assert settings.FRONTEND_URL in location_header

            # Verify tokens were created
            mock_access_token.assert_called_once()
            mock_refresh_token.assert_called_once()

            # Verify refresh token cookie was set
            response.set_cookie.assert_called_once()

    @pytest.mark.asyncio
    async def test_google_callback_new_user(self, mock_db):
        """
        Test Google callback with new user creation.
        """
        request = Mock(spec=Request)
        response = Mock(spec=Response)
        user_info = MockUserInfo(email="newuser@example.com", display_name="New User")
        new_user = Mock()
        new_user.username = "newuser"

        with patch("src.app.api.v1.oauth.google_sso") as mock_sso, patch(
            "src.app.api.v1.oauth.crud_users"
        ) as mock_crud, patch("src.app.api.v1.oauth._create_oauth_user") as mock_create_user, patch(
            "src.app.api.v1.oauth.create_access_token"
        ) as mock_access_token, patch("src.app.api.v1.oauth.create_refresh_token") as mock_refresh_token:
            mock_sso.verify_and_process = AsyncMock(return_value=user_info)
            mock_crud.get = AsyncMock(side_effect=[None, new_user])  # First call: no existing user, second: new user
            mock_create_user.return_value = None
            mock_access_token.return_value = "access_token_123"
            mock_refresh_token.return_value = "refresh_token_123"

            result = await google_callback(request, response, mock_db)

            assert isinstance(result, RedirectResponse)
            # Check the Location header instead of url attribute
            location_header = result.headers.get("location", "")
            assert "token=access_token_123" in location_header

            # Verify user creation was called
            mock_create_user.assert_called_once()

    @pytest.mark.asyncio
    async def test_google_callback_no_user_info(self, mock_db):
        """
        Test Google callback with no user info.
        """
        request = Mock(spec=Request)
        response = Mock(spec=Response)

        with patch("src.app.api.v1.oauth.google_sso") as mock_sso:
            mock_sso.verify_and_process = AsyncMock(return_value=None)

            with pytest.raises(HTTPException) as exc_info:
                await google_callback(request, response, mock_db)

            assert exc_info.value.status_code == 400
            assert "Failed to get user information from Google" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_google_callback_invalid_email(self, mock_db):
        """
        Test Google callback with invalid email.
        """
        request = Mock(spec=Request)
        response = Mock(spec=Response)
        user_info = MockUserInfo(email="invalid_email", display_name="Test User")

        with patch("src.app.api.v1.oauth.google_sso") as mock_sso:
            mock_sso.verify_and_process = AsyncMock(return_value=user_info)

            with pytest.raises(HTTPException) as exc_info:
                await google_callback(request, response, mock_db)

            assert exc_info.value.status_code == 400
            assert "Invalid email from OAuth provider" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_google_callback_user_creation_failed(self, mock_db):
        """
        Test Google callback when user creation fails.
        """
        request = Mock(spec=Request)
        response = Mock(spec=Response)
        user_info = MockUserInfo(email="newuser@example.com", display_name="New User")

        with patch("src.app.api.v1.oauth.google_sso") as mock_sso, patch(
            "src.app.api.v1.oauth.crud_users"
        ) as mock_crud, patch("src.app.api.v1.oauth._create_oauth_user") as mock_create_user:
            mock_sso.verify_and_process = AsyncMock(return_value=user_info)
            mock_crud.get = AsyncMock(side_effect=[None, None])  # No existing user, creation failed
            mock_create_user = AsyncMock(return_value=None)

            with pytest.raises(HTTPException) as exc_info:
                await google_callback(request, response, mock_db)

            assert exc_info.value.status_code == 500
            assert "Failed to create user account" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_google_callback_generic_error(self, mock_db):
        """
        Test Google callback with generic error.
        """
        request = Mock(spec=Request)
        response = Mock(spec=Response)

        with patch("src.app.api.v1.oauth.google_sso") as mock_sso:
            mock_sso.verify_and_process = AsyncMock(side_effect=Exception("Generic error"))

            result = await google_callback(request, response, mock_db)

            assert isinstance(result, RedirectResponse)
            # Check the Location header instead of url attribute
            location_header = result.headers.get("location", "")
            assert "auth/error" in location_header
            assert "Authentication%20failed" in location_header  # URL-encoded space


class TestGetGoogleUserInfo:
    """
    Test Google user info endpoint.
    """

    @pytest.mark.asyncio
    async def test_get_google_user_info_success(self, mock_db):
        """
        Test successful Google user info retrieval.
        """
        request = Mock(spec=Request)
        user_info = MockUserInfo(email="test@example.com", display_name="Test User")

        with patch("src.app.api.v1.oauth.settings") as mock_settings, patch(
            "src.app.api.v1.oauth.google_sso"
        ) as mock_sso:
            mock_settings.ENVIRONMENT.value = "local"
            mock_sso.verify_and_process = AsyncMock(return_value=user_info)

            result = await get_google_user_info(request, mock_db)

            assert result["email"] == "test@example.com"
            assert result["name"] == "Test User"
            assert result["provider"] == "google"
            assert result["verified"] is True

    @pytest.mark.asyncio
    async def test_get_google_user_info_production_blocked(self, mock_db):
        """
        Test Google user info blocked in production.
        """
        request = Mock(spec=Request)

        with patch("src.app.api.v1.oauth.settings") as mock_settings:
            mock_settings.ENVIRONMENT.value = "production"

            with pytest.raises(HTTPException) as exc_info:
                await get_google_user_info(request, mock_db)

            assert exc_info.value.status_code == 404
            assert "Endpoint not available" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_google_user_info_no_user_info(self, mock_db):
        """
        Test Google user info with no user info.
        """
        request = Mock(spec=Request)

        with patch("src.app.api.v1.oauth.settings") as mock_settings, patch(
            "src.app.api.v1.oauth.google_sso"
        ) as mock_sso:
            mock_settings.ENVIRONMENT.value = "local"
            mock_sso.verify_and_process = AsyncMock(return_value=None)

            with pytest.raises(HTTPException) as exc_info:
                await get_google_user_info(request, mock_db)

            assert exc_info.value.status_code == 400
            assert "Failed to get user information from Google" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_google_user_info_oauth_error(self, mock_db):
        """
        Test Google user info with OAuth error.
        """
        request = Mock(spec=Request)

        with patch("src.app.api.v1.oauth.settings") as mock_settings, patch(
            "src.app.api.v1.oauth.google_sso"
        ) as mock_sso:
            mock_settings.ENVIRONMENT.value = "local"
            mock_sso.verify_and_process = AsyncMock(side_effect=Exception("OAuth error"))

            with pytest.raises(HTTPException) as exc_info:
                await get_google_user_info(request, mock_db)

            assert exc_info.value.status_code == 400
            assert "OAuth verification failed" in str(exc_info.value.detail)
