"""Extended tests for user endpoints to improve coverage."""

from unittest.mock import AsyncMock, Mock, patch
from typing import Any

import pytest
from fastapi import Request


from src.app.core.exceptions.http_exceptions import NotFoundException









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