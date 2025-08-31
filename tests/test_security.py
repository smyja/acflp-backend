"""Tests for security functions and utilities."""

import secrets
from datetime import datetime, timedelta, UTC
from unittest.mock import AsyncMock, Mock, patch

import pytest
from jose import JWTError, jwt
from passlib.context import CryptContext

from src.app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_token,
    get_password_hash,
    verify_password,
    blacklist_token,
    blacklist_tokens,
    authenticate_user,
    get_current_user,
    get_current_superuser,
)
from src.app.core.exceptions.http_exceptions import UnauthorizedException
from src.app.schemas.user import UserCreateInternal


class TestPasswordHashing:
    """Test password hashing and verification."""
    
    def test_get_password_hash(self):
        """Test password hashing."""
        password = "test_password_123"
        hashed = get_password_hash(password)
        
        assert hashed != password
        assert len(hashed) > 50  # Bcrypt hashes are typically 60 characters
        assert hashed.startswith("$2b$")  # Bcrypt prefix
    
    def test_verify_password_correct(self):
        """Test password verification with correct password."""
        password = "test_password_123"
        hashed = get_password_hash(password)
        
        assert verify_password(password, hashed) is True
    
    def test_verify_password_incorrect(self):
        """Test password verification with incorrect password."""
        password = "test_password_123"
        wrong_password = "wrong_password"
        hashed = get_password_hash(password)
        
        assert verify_password(wrong_password, hashed) is False
    
    def test_verify_password_empty(self):
        """Test password verification with empty password."""
        password = "test_password_123"
        hashed = get_password_hash(password)
        
        assert verify_password("", hashed) is False
    
    def test_password_hash_different_each_time(self):
        """Test that password hashing produces different results each time."""
        password = "test_password_123"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)
        
        assert hash1 != hash2
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True


class TestTokenCreation:
    """Test JWT token creation."""
    
    @pytest.mark.asyncio
    async def test_create_access_token_default_expiry(self):
        """Test access token creation with default expiry."""
        data = {"sub": "testuser"}
        token = await create_access_token(data)
        
        assert isinstance(token, str)
        assert len(token) > 100  # JWT tokens are typically long
        
        # Decode without verification to check payload
        with patch("src.app.core.security.SECRET_KEY") as mock_secret:
            mock_secret.get_secret_value.return_value = "test_secret_key"
            payload = jwt.decode(token, "test_secret_key", algorithms=["HS256"])
            
            assert payload["sub"] == "testuser"
            assert "exp" in payload
            assert "iat" in payload
    
    @pytest.mark.asyncio
    async def test_create_access_token_custom_expiry(self):
        """Test access token creation with custom expiry."""
        data = {"sub": "testuser"}
        expires_delta = timedelta(hours=2)
        
        with patch("src.app.core.security.SECRET_KEY") as mock_secret:
            mock_secret.get_secret_value.return_value = "test_secret_key"
            token = await create_access_token(data, expires_delta)
            
            payload = jwt.decode(token, "test_secret_key", algorithms=["HS256"])
            
            # Check expiry is approximately 2 hours from now
            exp_time = datetime.fromtimestamp(payload["exp"], UTC)
            expected_exp = datetime.now(UTC) + expires_delta
            
            # Allow 1 minute tolerance
            assert abs((exp_time - expected_exp).total_seconds()) < 60
    
    @pytest.mark.asyncio
    async def test_create_refresh_token(self):
        """Test refresh token creation."""
        data = {"sub": "testuser"}
        token = await create_refresh_token(data)
        
        assert isinstance(token, str)
        assert len(token) > 100
        
        with patch("src.app.core.security.SECRET_KEY") as mock_secret:
            mock_secret.get_secret_value.return_value = "test_secret_key"
            payload = jwt.decode(token, "test_secret_key", algorithms=["HS256"])
            
            assert payload["sub"] == "testuser"
            assert payload["type"] == "refresh"
            assert "exp" in payload


class TestTokenVerification:
    """Test JWT token verification."""
    
    @pytest.mark.asyncio
    async def test_verify_token_valid_access(self, mock_db):
        """Test verification of valid access token."""
        with patch("src.app.core.security.SECRET_KEY") as mock_secret, \
             patch("src.app.core.security.crud_token_blacklist") as mock_blacklist:
            
            mock_secret.get_secret_value.return_value = "test_secret_key"
            mock_blacklist.exists.return_value = False  # Token not blacklisted
            
            # Create a valid token
            payload = {
                "sub": "testuser",
                "exp": datetime.now(UTC) + timedelta(hours=1),
                "iat": datetime.now(UTC)
            }
            token = jwt.encode(payload, "test_secret_key", algorithm="HS256")
            
            result = await verify_token(token, "access", mock_db)
            
            assert result is not None
            assert result.username_or_email == "testuser"
    
    @pytest.mark.asyncio
    async def test_verify_token_expired(self, mock_db):
        """Test verification of expired token."""
        with patch("src.app.core.security.SECRET_KEY") as mock_secret:
            mock_secret.get_secret_value.return_value = "test_secret_key"
            
            # Create an expired token
            payload = {
                "sub": "testuser",
                "exp": datetime.now(UTC) - timedelta(hours=1),  # Expired
                "iat": datetime.now(UTC) - timedelta(hours=2)
            }
            token = jwt.encode(payload, "test_secret_key", algorithm="HS256")
            
            result = await verify_token(token, "access", mock_db)
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_verify_token_blacklisted(self, mock_db):
        """Test verification of blacklisted token."""
        with patch("src.app.core.security.SECRET_KEY") as mock_secret, \
             patch("src.app.core.security.crud_token_blacklist") as mock_blacklist:
            
            mock_secret.get_secret_value.return_value = "test_secret_key"
            mock_blacklist.exists.return_value = True  # Token is blacklisted
            
            # Create a valid token
            payload = {
                "sub": "testuser",
                "exp": datetime.now(UTC) + timedelta(hours=1),
                "iat": datetime.now(UTC)
            }
            token = jwt.encode(payload, "test_secret_key", algorithm="HS256")
            
            result = await verify_token(token, "access", mock_db)
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_verify_token_invalid_signature(self, mock_db):
        """Test verification of token with invalid signature."""
        with patch("src.app.core.security.SECRET_KEY") as mock_secret:
            mock_secret.get_secret_value.return_value = "test_secret_key"
            
            # Create token with different secret
            payload = {
                "sub": "testuser",
                "exp": datetime.now(UTC) + timedelta(hours=1),
                "iat": datetime.now(UTC)
            }
            token = jwt.encode(payload, "different_secret", algorithm="HS256")
            
            result = await verify_token(token, "access", mock_db)
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_verify_token_wrong_type(self, mock_db):
        """Test verification of token with wrong type."""
        with patch("src.app.core.security.SECRET_KEY") as mock_secret, \
             patch("src.app.core.security.crud_token_blacklist") as mock_blacklist:
            
            mock_secret.get_secret_value.return_value = "test_secret_key"
            mock_blacklist.exists.return_value = False
            
            # Create refresh token but verify as access
            payload = {
                "sub": "testuser",
                "type": "refresh",
                "exp": datetime.now(UTC) + timedelta(hours=1),
                "iat": datetime.now(UTC)
            }
            token = jwt.encode(payload, "test_secret_key", algorithm="HS256")
            
            result = await verify_token(token, "access", mock_db)
            
            assert result is None


class TestTokenBlacklisting:
    """Test token blacklisting functionality."""
    
    @pytest.mark.asyncio
    async def test_blacklist_token_success(self, mock_db):
        """Test successful token blacklisting."""
        with patch("src.app.core.security.SECRET_KEY") as mock_secret, \
             patch("src.app.core.security.crud_token_blacklist") as mock_blacklist:
            
            mock_secret.get_secret_value.return_value = "test_secret_key"
            mock_blacklist.create = AsyncMock()
            
            # Create a token with expiration
            exp_time = datetime.now(UTC) + timedelta(hours=1)
            payload = {
                "sub": "testuser",
                "exp": exp_time,
                "iat": datetime.now(UTC)
            }
            token = jwt.encode(payload, "test_secret_key", algorithm="HS256")
            
            await blacklist_token(token, mock_db)
            
            # Verify create was called
            mock_blacklist.create.assert_called_once()
            call_args = mock_blacklist.create.call_args
            blacklist_obj = call_args.kwargs["object"]
            
            assert blacklist_obj.token == token
            assert isinstance(blacklist_obj.expires_at, datetime)
    
    @pytest.mark.asyncio
    async def test_blacklist_token_no_expiration(self, mock_db):
        """Test blacklisting token without expiration."""
        with patch("src.app.core.security.SECRET_KEY") as mock_secret, \
             patch("src.app.core.security.crud_token_blacklist") as mock_blacklist:
            
            mock_secret.get_secret_value.return_value = "test_secret_key"
            mock_blacklist.create = AsyncMock()
            
            # Create a token without expiration
            payload = {
                "sub": "testuser",
                "iat": datetime.now(UTC)
            }
            token = jwt.encode(payload, "test_secret_key", algorithm="HS256")
            
            await blacklist_token(token, mock_db)
            
            # Should not call create if no expiration
            mock_blacklist.create.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_blacklist_tokens_multiple(self, mock_db):
        """Test blacklisting multiple tokens."""
        with patch("src.app.core.security.blacklist_token") as mock_blacklist_single:
            mock_blacklist_single.return_value = None
            
            access_token = "access_token_123"
            refresh_token = "refresh_token_456"
            
            await blacklist_tokens(access_token, refresh_token, mock_db)
            
            # Verify both tokens were blacklisted
            assert mock_blacklist_single.call_count == 2
            calls = mock_blacklist_single.call_args_list
            
            # Check that both tokens were called
            tokens_called = [call.args[0] for call in calls]
            assert access_token in tokens_called
            assert refresh_token in tokens_called


class TestUserAuthentication:
    """Test user authentication functions."""
    
    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, mock_db):
        """Test successful user authentication."""
        username = "testuser"
        password = "password123"
        hashed_password = get_password_hash(password)
        
        mock_user = {
            "id": 1,
            "username": username,
            "hashed_password": hashed_password,
            "is_deleted": False
        }
        
        with patch("src.app.core.security.crud_users") as mock_crud:
            mock_crud.get.return_value = mock_user
            
            result = await authenticate_user(username, password, mock_db)
            
            assert result == mock_user
    
    @pytest.mark.asyncio
    async def test_authenticate_user_not_found(self, mock_db):
        """Test authentication when user doesn't exist."""
        username = "nonexistent"
        password = "password123"
        
        with patch("src.app.core.security.crud_users") as mock_crud:
            mock_crud.get.return_value = None
            
            result = await authenticate_user(username, password, mock_db)
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(self, mock_db):
        """Test authentication with wrong password."""
        username = "testuser"
        password = "wrong_password"
        correct_password = "correct_password"
        hashed_password = get_password_hash(correct_password)
        
        mock_user = {
            "id": 1,
            "username": username,
            "hashed_password": hashed_password,
            "is_deleted": False
        }
        
        with patch("src.app.core.security.crud_users") as mock_crud:
            mock_crud.get.return_value = mock_user
            
            result = await authenticate_user(username, password, mock_db)
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_authenticate_user_deleted(self, mock_db):
        """Test authentication with deleted user."""
        username = "testuser"
        password = "password123"
        hashed_password = get_password_hash(password)
        
        mock_user = {
            "id": 1,
            "username": username,
            "hashed_password": hashed_password,
            "is_deleted": True  # User is deleted
        }
        
        with patch("src.app.core.security.crud_users") as mock_crud:
            mock_crud.get.return_value = mock_user
            
            result = await authenticate_user(username, password, mock_db)
            
            assert result is None


class TestCurrentUserDependencies:
    """Test current user dependency functions."""
    
    @pytest.mark.asyncio
    async def test_get_current_user_success(self, mock_db):
        """Test successful current user retrieval."""
        token = "valid_token"
        mock_token_data = Mock()
        mock_token_data.username_or_email = "testuser"
        
        mock_user = {
            "id": 1,
            "username": "testuser",
            "email": "test@example.com",
            "is_deleted": False
        }
        
        with patch("src.app.core.security.verify_token") as mock_verify, \
             patch("src.app.core.security.crud_users") as mock_crud:
            
            mock_verify.return_value = mock_token_data
            mock_crud.get.return_value = mock_user
            
            result = await get_current_user(token, mock_db)
            
            assert result == mock_user
    
    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self, mock_db):
        """Test current user with invalid token."""
        token = "invalid_token"
        
        with patch("src.app.core.security.verify_token") as mock_verify:
            mock_verify.return_value = None
            
            with pytest.raises(UnauthorizedException):
                await get_current_user(token, mock_db)
    
    @pytest.mark.asyncio
    async def test_get_current_user_not_found(self, mock_db):
        """Test current user when user doesn't exist."""
        token = "valid_token"
        mock_token_data = Mock()
        mock_token_data.username_or_email = "nonexistent"
        
        with patch("src.app.core.security.verify_token") as mock_verify, \
             patch("src.app.core.security.crud_users") as mock_crud:
            
            mock_verify.return_value = mock_token_data
            mock_crud.get.return_value = None
            
            with pytest.raises(UnauthorizedException):
                await get_current_user(token, mock_db)
    
    @pytest.mark.asyncio
    async def test_get_current_superuser_success(self, mock_db):
        """Test successful superuser retrieval."""
        mock_user = {
            "id": 1,
            "username": "admin",
            "is_superuser": True
        }
        
        with patch("src.app.core.security.get_current_user") as mock_get_user:
            mock_get_user.return_value = mock_user
            
            result = await get_current_superuser("token", mock_db)
            
            assert result == mock_user
    
    @pytest.mark.asyncio
    async def test_get_current_superuser_not_superuser(self, mock_db):
        """Test superuser dependency with regular user."""
        mock_user = {
            "id": 1,
            "username": "user",
            "is_superuser": False
        }
        
        with patch("src.app.core.security.get_current_user") as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with pytest.raises(UnauthorizedException, match="Not enough permissions"):
                await get_current_superuser("token", mock_db)
    
    @pytest.mark.asyncio
    async def test_get_current_superuser_missing_field(self, mock_db):
        """Test superuser dependency with user missing is_superuser field."""
        mock_user = {
            "id": 1,
            "username": "user"
            # Missing is_superuser field
        }
        
        with patch("src.app.core.security.get_current_user") as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with pytest.raises(UnauthorizedException, match="Not enough permissions"):
                await get_current_superuser("token", mock_db)


class TestSecurityEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_password_hash_special_characters(self):
        """Test password hashing with special characters."""
        password = "p@ssw0rd!#$%^&*()_+-=[]{}|;':,.<>?"
        hashed = get_password_hash(password)
        
        assert verify_password(password, hashed) is True
    
    def test_password_hash_unicode(self):
        """Test password hashing with unicode characters."""
        password = "пароль123🔒"
        hashed = get_password_hash(password)
        
        assert verify_password(password, hashed) is True
    
    @pytest.mark.asyncio
    async def test_token_creation_empty_data(self):
        """Test token creation with empty data."""
        data = {}
        token = await create_access_token(data)
        
        assert isinstance(token, str)
        assert len(token) > 0
    
    @pytest.mark.asyncio
    async def test_verify_token_malformed(self, mock_db):
        """Test verification of malformed token."""
        malformed_token = "not.a.valid.jwt.token"
        
        result = await verify_token(malformed_token, "access", mock_db)
        
        assert result is None