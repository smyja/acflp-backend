"""Unit tests for authentication endpoints."""

from unittest.mock import AsyncMock, Mock, patch
from datetime import timedelta

import pytest
from fastapi import Response, Request
from jose import JWTError

from src.app.api.v1.login import login, refresh_access_token
from src.app.api.v1.logout import logout
from src.app.core.exceptions.http_exceptions import UnauthorizedException
from src.app.core.schemas import LoginCredentials, Token


class TestLogin:
    """Test login endpoint."""

    @pytest.mark.asyncio
    async def test_login_success(self, mock_db):
        """Test successful login."""
        credentials = LoginCredentials(username="testuser", password="testpass123")
        response = Mock(spec=Response)

        mock_user = {
            "id": 1,
            "username": "testuser",
            "email": "test@example.com",
            "is_superuser": False,
        }

        with patch("src.app.api.v1.login.authenticate_user") as mock_auth:
            mock_auth.return_value = mock_user

            with patch("src.app.api.v1.login.create_access_token") as mock_access_token:
                mock_access_token.return_value = "mock_access_token"

                with patch(
                    "src.app.api.v1.login.create_refresh_token"
                ) as mock_refresh_token:
                    mock_refresh_token.return_value = "mock_refresh_token"

                    result = await login(response, credentials, mock_db)

                    assert result["access_token"] == "mock_access_token"
                    assert result["token_type"] == "bearer"

                    # Verify cookie was set
                    response.set_cookie.assert_called_once()
                    cookie_call = response.set_cookie.call_args
                    assert cookie_call[1]["key"] == "refresh_token"
                    assert cookie_call[1]["value"] == "mock_refresh_token"
                    assert cookie_call[1]["httponly"] is True
                    assert cookie_call[1]["secure"] is True

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, mock_db):
        """Test login with invalid credentials."""
        credentials = LoginCredentials(username="testuser", password="wrongpass")
        response = Mock(spec=Response)

        with patch("src.app.api.v1.login.authenticate_user") as mock_auth:
            mock_auth.return_value = None

            with pytest.raises(
                UnauthorizedException, match="Wrong username, email or password"
            ):
                await login(response, credentials, mock_db)

    @pytest.mark.asyncio
    async def test_login_user_not_found(self, mock_db):
        """Test login when user doesn't exist."""
        credentials = LoginCredentials(username="nonexistent", password="testpass123")
        response = Mock(spec=Response)

        with patch("src.app.api.v1.login.authenticate_user") as mock_auth:
            mock_auth.return_value = None

            with pytest.raises(UnauthorizedException):
                await login(response, credentials, mock_db)


class TestRefreshToken:
    """Test refresh token endpoint."""

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, mock_db):
        """Test successful token refresh."""
        request = Mock(spec=Request)
        request.cookies = {"refresh_token": "valid_refresh_token"}
        response = Mock(spec=Response)

        mock_user_data = Mock()
        mock_user_data.username_or_email = "testuser"

        with patch("src.app.api.v1.login.verify_token") as mock_verify:
            mock_verify.return_value = mock_user_data

            with patch("src.app.api.v1.login.create_access_token") as mock_access_token:
                mock_access_token.return_value = "new_access_token"

                with patch(
                    "src.app.api.v1.login.create_refresh_token"
                ) as mock_refresh_token:
                    mock_refresh_token.return_value = "new_refresh_token"

                    result = await refresh_access_token(request, response, mock_db)

                    assert result["access_token"] == "new_access_token"
                    assert result["token_type"] == "bearer"

                    # Verify new refresh token cookie was set
                    response.set_cookie.assert_called_once()
                    cookie_call = response.set_cookie.call_args
                    assert cookie_call[1]["key"] == "refresh_token"
                    assert cookie_call[1]["value"] == "new_refresh_token"

    @pytest.mark.asyncio
    async def test_refresh_token_missing(self, mock_db):
        """Test refresh when refresh token is missing."""
        request = Mock(spec=Request)
        request.cookies = {}  # No refresh token
        response = Mock(spec=Response)

        with pytest.raises(UnauthorizedException, match="Refresh token missing"):
            await refresh_access_token(request, response, mock_db)

    @pytest.mark.asyncio
    async def test_refresh_token_invalid(self, mock_db):
        """Test refresh with invalid refresh token."""
        request = Mock(spec=Request)
        request.cookies = {"refresh_token": "invalid_refresh_token"}
        response = Mock(spec=Response)

        with patch("src.app.api.v1.login.verify_token") as mock_verify:
            mock_verify.return_value = None  # Invalid token

            with pytest.raises(UnauthorizedException, match="Invalid refresh token"):
                await refresh_access_token(request, response, mock_db)


class TestLogout:
    """Test logout endpoint."""

    @pytest.mark.asyncio
    async def test_logout_success(self, mock_db):
        """Test successful logout."""
        response = Mock(spec=Response)
        access_token = "valid_access_token"
        refresh_token = "valid_refresh_token"

        with patch("src.app.api.v1.logout.blacklist_tokens") as mock_blacklist:
            mock_blacklist.return_value = None

            result = await logout(response, access_token, mock_db, refresh_token)

            assert result["message"] == "Logged out successfully"

            # Verify tokens were blacklisted
            mock_blacklist.assert_called_once_with(
                access_token=access_token, refresh_token=refresh_token, db=mock_db
            )

            # Verify refresh token cookie was deleted
            response.delete_cookie.assert_called_once_with(key="refresh_token")

    @pytest.mark.asyncio
    async def test_logout_missing_refresh_token(self, mock_db):
        """Test logout when refresh token is missing."""
        response = Mock(spec=Response)
        access_token = "valid_access_token"
        refresh_token = None  # Missing refresh token

        with pytest.raises(UnauthorizedException, match=r".*[Ii]nvalid.*token.*"):
            await logout(response, access_token, mock_db, refresh_token)

    @pytest.mark.asyncio
    async def test_logout_jwt_error(self, mock_db):
        """Test logout when JWT error occurs."""
        response = Mock(spec=Response)
        access_token = "invalid_access_token"
        refresh_token = "valid_refresh_token"

        with patch("src.app.api.v1.logout.blacklist_tokens") as mock_blacklist:
            mock_blacklist.side_effect = JWTError("Invalid token")

            with pytest.raises(UnauthorizedException, match="Invalid token"):
                await logout(response, access_token, refresh_token, mock_db)

    @pytest.mark.asyncio
    async def test_logout_blacklist_error(self, mock_db):
        """Test logout when blacklisting fails."""
        response = Mock(spec=Response)
        access_token = "valid_access_token"
        refresh_token = "valid_refresh_token"

        with patch("src.app.api.v1.logout.blacklist_tokens") as mock_blacklist:
            mock_blacklist.side_effect = Exception("Database error")

            with pytest.raises(Exception, match="Database error"):
                await logout(response, access_token, refresh_token, mock_db)
