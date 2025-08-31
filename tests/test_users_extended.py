"""Extended tests for user endpoints to improve coverage."""

from unittest.mock import AsyncMock, Mock, patch
from typing import Any

import pytest
from fastapi import Request

from src.app.api.v1.users import (
    read_user_rate_limits,
    read_user_tier,
    patch_user_tier,
)
from src.app.core.exceptions.http_exceptions import NotFoundException
from src.app.schemas.user import UserTierUpdate


class TestUserRateLimits:
    """Test user rate limits endpoint."""
    
    @pytest.mark.asyncio
    async def test_read_user_rate_limits_success(self, mock_db):
        """Test successful user rate limits retrieval."""
        request = Mock(spec=Request)
        username = "testuser"
        
        mock_user = Mock()
        mock_user.id = 1
        mock_user.tier_id = 1
        
        mock_tier = Mock()
        mock_tier.id = 1
        mock_tier.name = "basic"
        
        mock_rate_limits = [
            {"id": 1, "name": "api_calls", "limit": 100, "period": 3600},
            {"id": 2, "name": "uploads", "limit": 10, "period": 3600},
        ]
        
        with patch("src.app.api.v1.users.crud_users") as mock_crud_users, \
             patch("src.app.api.v1.users.crud_tiers") as mock_crud_tiers, \
             patch("src.app.api.v1.users.crud_rate_limits") as mock_crud_rate_limits:
            
            mock_crud_users.get.return_value = mock_user
            mock_crud_tiers.get.return_value = mock_tier
            mock_crud_rate_limits.get_multi.return_value = mock_rate_limits
            
            result = await read_user_rate_limits(request, username, mock_db)
            
            assert "user" in result
            assert "tier" in result
            assert "rate_limits" in result
            assert result["user"]["username"] == username
            assert result["tier"]["name"] == "basic"
            assert len(result["rate_limits"]) == 2
    
    @pytest.mark.asyncio
    async def test_read_user_rate_limits_user_not_found(self, mock_db):
        """Test user rate limits when user doesn't exist."""
        request = Mock(spec=Request)
        username = "nonexistent"
        
        with patch("src.app.api.v1.users.crud_users") as mock_crud_users:
            mock_crud_users.get.return_value = None
            
            with pytest.raises(NotFoundException, match="User not found"):
                await read_user_rate_limits(request, username, mock_db)
    
    @pytest.mark.asyncio
    async def test_read_user_rate_limits_no_tier(self, mock_db):
        """Test user rate limits when user has no tier."""
        request = Mock(spec=Request)
        username = "testuser"
        
        mock_user = Mock()
        mock_user.id = 1
        mock_user.tier_id = None
        
        with patch("src.app.api.v1.users.crud_users") as mock_crud_users:
            mock_crud_users.get.return_value = mock_user
            
            result = await read_user_rate_limits(request, username, mock_db)
            
            assert "user" in result
            assert "tier" in result
            assert "rate_limits" in result
            assert result["tier"] is None
            assert result["rate_limits"] == []


class TestUserTier:
    """Test user tier endpoints."""
    
    @pytest.mark.asyncio
    async def test_read_user_tier_success(self, mock_db):
        """Test successful user tier retrieval."""
        request = Mock(spec=Request)
        username = "testuser"
        
        mock_user = Mock()
        mock_user.id = 1
        mock_user.tier_id = 1
        
        mock_tier = {
            "id": 1,
            "name": "premium",
            "description": "Premium tier"
        }
        
        with patch("src.app.api.v1.users.crud_users") as mock_crud_users, \
             patch("src.app.api.v1.users.crud_tiers") as mock_crud_tiers:
            
            mock_crud_users.get.return_value = mock_user
            mock_crud_tiers.get.return_value = mock_tier
            
            result = await read_user_tier(request, username, mock_db)
            
            assert result["name"] == "premium"
            assert result["description"] == "Premium tier"
    
    @pytest.mark.asyncio
    async def test_read_user_tier_user_not_found(self, mock_db):
        """Test user tier when user doesn't exist."""
        request = Mock(spec=Request)
        username = "nonexistent"
        
        with patch("src.app.api.v1.users.crud_users") as mock_crud_users:
            mock_crud_users.get.return_value = None
            
            with pytest.raises(NotFoundException, match="User not found"):
                await read_user_tier(request, username, mock_db)
    
    @pytest.mark.asyncio
    async def test_read_user_tier_no_tier(self, mock_db):
        """Test user tier when user has no tier."""
        request = Mock(spec=Request)
        username = "testuser"
        
        mock_user = Mock()
        mock_user.id = 1
        mock_user.tier_id = None
        
        with patch("src.app.api.v1.users.crud_users") as mock_crud_users:
            mock_crud_users.get.return_value = mock_user
            
            result = await read_user_tier(request, username, mock_db)
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_patch_user_tier_success(self, mock_db):
        """Test successful user tier update."""
        request = Mock(spec=Request)
        username = "testuser"
        values = UserTierUpdate(tier_id=2)
        
        mock_user = Mock()
        mock_user.id = 1
        
        mock_tier = Mock()
        mock_tier.id = 2
        mock_tier.name = "premium"
        
        with patch("src.app.api.v1.users.crud_users") as mock_crud_users, \
             patch("src.app.api.v1.users.crud_tiers") as mock_crud_tiers:
            
            mock_crud_users.get.return_value = mock_user
            mock_crud_tiers.get.return_value = mock_tier
            mock_crud_users.update.return_value = None
            
            result = await patch_user_tier(request, username, values, mock_db)
            
            assert result["message"] == "User tier updated successfully"
            
            # Verify update was called
            mock_crud_users.update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_patch_user_tier_user_not_found(self, mock_db):
        """Test user tier update when user doesn't exist."""
        request = Mock(spec=Request)
        username = "nonexistent"
        values = UserTierUpdate(tier_id=2)
        
        with patch("src.app.api.v1.users.crud_users") as mock_crud_users:
            mock_crud_users.get.return_value = None
            
            with pytest.raises(NotFoundException, match="User not found"):
                await patch_user_tier(request, username, values, mock_db)
    
    @pytest.mark.asyncio
    async def test_patch_user_tier_tier_not_found(self, mock_db):
        """Test user tier update when tier doesn't exist."""
        request = Mock(spec=Request)
        username = "testuser"
        values = UserTierUpdate(tier_id=999)
        
        mock_user = Mock()
        mock_user.id = 1
        
        with patch("src.app.api.v1.users.crud_users") as mock_crud_users, \
             patch("src.app.api.v1.users.crud_tiers") as mock_crud_tiers:
            
            mock_crud_users.get.return_value = mock_user
            mock_crud_tiers.get.return_value = None
            
            with pytest.raises(NotFoundException, match="Tier not found"):
                await patch_user_tier(request, username, values, mock_db)


class TestUserEndpointsEdgeCases:
    """Test edge cases for user endpoints."""
    
    @pytest.mark.asyncio
    async def test_user_creation_with_special_characters(self, mock_db):
        """Test user creation with special characters in username."""
        from src.app.api.v1.users import write_user
        from src.app.schemas.user import UserCreate
        
        request = Mock(spec=Request)
        user_data = UserCreate(
            username="test_user-123",
            email="test@example.com",
            password="password123",
            name="Test User"
        )
        
        with patch("src.app.api.v1.users.crud_users") as mock_crud_users, \
             patch("src.app.api.v1.users.get_password_hash") as mock_hash:
            
            mock_crud_users.exists.return_value = False
            mock_hash.return_value = "hashed_password"
            
            mock_created_user = Mock()
            mock_created_user.id = 1
            mock_crud_users.create.return_value = mock_created_user
            
            mock_user_read = {
                "id": 1,
                "username": "test_user-123",
                "email": "test@example.com",
                "name": "Test User"
            }
            mock_crud_users.get.return_value = mock_user_read
            
            result = await write_user(request, user_data, mock_db)
            
            assert result["username"] == "test_user-123"
    
    @pytest.mark.asyncio
    async def test_user_creation_password_hashing(self, mock_db):
        """Test that password is properly hashed during user creation."""
        from src.app.api.v1.users import write_user
        from src.app.schemas.user import UserCreate
        
        request = Mock(spec=Request)
        user_data = UserCreate(
            username="testuser",
            email="test@example.com",
            password="plaintext_password",
            name="Test User"
        )
        
        with patch("src.app.api.v1.users.crud_users") as mock_crud_users, \
             patch("src.app.api.v1.users.get_password_hash") as mock_hash:
            
            mock_crud_users.exists.return_value = False
            mock_hash.return_value = "hashed_password_123"
            
            mock_created_user = Mock()
            mock_created_user.id = 1
            mock_crud_users.create.return_value = mock_created_user
            
            mock_user_read = {
                "id": 1,
                "username": "testuser",
                "email": "test@example.com",
                "name": "Test User"
            }
            mock_crud_users.get.return_value = mock_user_read
            
            await write_user(request, user_data, mock_db)
            
            # Verify password was hashed
            mock_hash.assert_called_once_with(password="plaintext_password")
            
            # Verify create was called with hashed password
            create_call = mock_crud_users.create.call_args
            user_internal = create_call.kwargs["object"]
            assert user_internal.hashed_password == "hashed_password_123"
            assert not hasattr(user_internal, "password")  # Original password should be removed
    
    @pytest.mark.asyncio
    async def test_user_creation_failed_after_creation(self, mock_db):
        """Test user creation when user is not found after creation."""
        from src.app.api.v1.users import write_user
        from src.app.schemas.user import UserCreate
        
        request = Mock(spec=Request)
        user_data = UserCreate(
            username="testuser",
            email="test@example.com",
            password="password123",
            name="Test User"
        )
        
        with patch("src.app.api.v1.users.crud_users") as mock_crud_users, \
             patch("src.app.api.v1.users.get_password_hash") as mock_hash:
            
            mock_crud_users.exists.return_value = False
            mock_hash.return_value = "hashed_password"
            
            mock_created_user = Mock()
            mock_created_user.id = 1
            mock_crud_users.create.return_value = mock_created_user
            mock_crud_users.get.return_value = None  # User not found after creation
            
            with pytest.raises(NotFoundException, match="Created user not found"):
                await write_user(request, user_data, mock_db)
    
    @pytest.mark.asyncio
    async def test_user_creation_no_id_after_creation(self, mock_db):
        """Test user creation when created user has no ID."""
        from src.app.api.v1.users import write_user
        from src.app.schemas.user import UserCreate
        
        request = Mock(spec=Request)
        user_data = UserCreate(
            username="testuser",
            email="test@example.com",
            password="password123",
            name="Test User"
        )
        
        with patch("src.app.api.v1.users.crud_users") as mock_crud_users, \
             patch("src.app.api.v1.users.get_password_hash") as mock_hash:
            
            mock_crud_users.exists.return_value = False
            mock_hash.return_value = "hashed_password"
            
            # Mock created user without ID
            mock_created_user = Mock(spec=[])
            mock_crud_users.create.return_value = mock_created_user
            
            with pytest.raises(NotFoundException, match="Created user has no ID"):
                await write_user(request, user_data, mock_db)