"""Tests for core schemas and validation."""

from datetime import UTC, datetime, timedelta
import uuid as uuid_pkg
from typing import Any

import pytest
from pydantic import ValidationError

from src.app.core.schemas import (
    HealthCheck,
    LoginCredentials,
    UUIDSchema,
    TimestampSchema,
    PersistentDeletion,
    Token,
    TokenData,
    TokenBlacklistBase,
    TokenBlacklistRead,
    TokenBlacklistCreate,
    TokenBlacklistUpdate,
)


class TestHealthCheck:
    """Test HealthCheck schema."""
    
    def test_health_check_valid(self):
        """Test valid HealthCheck creation."""
        health = HealthCheck(
            name="FastAPI App",
            version="1.0.0",
            description="A FastAPI application"
        )
        
        assert health.name == "FastAPI App"
        assert health.version == "1.0.0"
        assert health.description == "A FastAPI application"
    
    def test_health_check_missing_fields(self):
        """Test HealthCheck with missing required fields."""
        with pytest.raises(ValidationError) as exc_info:
            HealthCheck(name="App")
        
        errors = exc_info.value.errors()
        field_names = [error["loc"][0] for error in errors]
        assert "version" in field_names
        assert "description" in field_names
    
    def test_health_check_empty_strings(self):
        """Test HealthCheck with empty strings."""
        health = HealthCheck(
            name="",
            version="",
            description=""
        )
        
        assert health.name == ""
        assert health.version == ""
        assert health.description == ""


class TestLoginCredentials:
    """Test LoginCredentials schema."""
    
    def test_login_credentials_username(self):
        """Test LoginCredentials with username."""
        credentials = LoginCredentials(
            username="testuser",
            password="password123"
        )
        
        assert credentials.username == "testuser"
        assert credentials.password == "password123"
    
    def test_login_credentials_email(self):
        """Test LoginCredentials with email."""
        credentials = LoginCredentials(
            username="user@example.com",
            password="password123"
        )
        
        assert credentials.username == "user@example.com"
        assert credentials.password == "password123"
    
    def test_login_credentials_missing_fields(self):
        """Test LoginCredentials with missing fields."""
        with pytest.raises(ValidationError) as exc_info:
            LoginCredentials(username="testuser")
        
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("password",)
        assert errors[0]["type"] == "missing"
    
    def test_login_credentials_empty_values(self):
        """Test LoginCredentials with empty values."""
        credentials = LoginCredentials(
            username="",
            password=""
        )
        
        assert credentials.username == ""
        assert credentials.password == ""


class TestUUIDSchema:
    """Test UUIDSchema mixin."""
    
    def test_uuid_schema_auto_generation(self):
        """Test UUID is automatically generated."""
        schema = UUIDSchema()
        
        assert isinstance(schema.uuid, uuid_pkg.UUID)
        assert str(schema.uuid)  # Should be a valid UUID string
    
    def test_uuid_schema_custom_uuid(self):
        """Test UUID schema with custom UUID."""
        custom_uuid = uuid_pkg.uuid4()
        schema = UUIDSchema(uuid=custom_uuid)
        
        assert schema.uuid == custom_uuid
    
    def test_uuid_schema_string_uuid(self):
        """Test UUID schema with string UUID."""
        uuid_string = "123e4567-e89b-12d3-a456-426614174000"
        schema = UUIDSchema(uuid=uuid_string)
        
        assert isinstance(schema.uuid, uuid_pkg.UUID)
        assert str(schema.uuid) == uuid_string
    
    def test_uuid_schema_invalid_uuid(self):
        """Test UUID schema with invalid UUID."""
        with pytest.raises(ValidationError) as exc_info:
            UUIDSchema(uuid="invalid-uuid")
        
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("uuid",)


class TestTimestampSchema:
    """Test TimestampSchema mixin."""
    
    def test_timestamp_schema_auto_creation(self):
        """Test timestamps are automatically created."""
        before = datetime.now(UTC).replace(tzinfo=None)
        schema = TimestampSchema()
        after = datetime.now(UTC).replace(tzinfo=None)
        
        assert isinstance(schema.created_at, datetime)
        assert before <= schema.created_at <= after
        assert schema.updated_at is None
    
    def test_timestamp_schema_custom_timestamps(self):
        """Test timestamp schema with custom timestamps."""
        created = datetime(2023, 1, 1, 12, 0, 0)
        updated = datetime(2023, 1, 2, 12, 0, 0)
        
        schema = TimestampSchema(
            created_at=created,
            updated_at=updated
        )
        
        assert schema.created_at == created
        assert schema.updated_at == updated
    
    def test_timestamp_schema_serialization(self):
        """Test timestamp serialization to ISO format."""
        created = datetime(2023, 1, 1, 12, 0, 0)
        updated = datetime(2023, 1, 2, 12, 0, 0)
        
        schema = TimestampSchema(
            created_at=created,
            updated_at=updated
        )
        
        # Test serialization methods directly
        created_serialized = schema.serialize_dt(created, None)
        updated_serialized = schema.serialize_updated_at(updated, None)
        
        assert created_serialized == "2023-01-01T12:00:00"
        assert updated_serialized == "2023-01-02T12:00:00"
    
    def test_timestamp_schema_none_serialization(self):
        """Test timestamp serialization with None values."""
        schema = TimestampSchema()
        
        # Test serialization with None values
        created_none = schema.serialize_dt(None, None)
        updated_none = schema.serialize_updated_at(None, None)
        
        assert created_none is None
        assert updated_none is None
    
    def test_timestamp_schema_model_dump(self):
        """Test timestamp schema model dump includes serialized timestamps."""
        created = datetime(2023, 1, 1, 12, 0, 0)
        schema = TimestampSchema(created_at=created)
        
        data = schema.model_dump()
        
        assert "created_at" in data
        assert "updated_at" in data


class TestPersistentDeletion:
    """Test PersistentDeletion mixin."""
    
    def test_persistent_deletion_defaults(self):
        """Test default values for persistent deletion."""
        schema = PersistentDeletion()
        
        assert schema.deleted_at is None
        assert schema.is_deleted is False
    
    def test_persistent_deletion_custom_values(self):
        """Test persistent deletion with custom values."""
        deleted_time = datetime(2023, 1, 1, 12, 0, 0)
        schema = PersistentDeletion(
            deleted_at=deleted_time,
            is_deleted=True
        )
        
        assert schema.deleted_at == deleted_time
        assert schema.is_deleted is True
    
    def test_persistent_deletion_serialization(self):
        """Test deleted_at serialization."""
        deleted_time = datetime(2023, 1, 1, 12, 0, 0)
        schema = PersistentDeletion(deleted_at=deleted_time)
        
        # Test serialization method directly
        serialized = schema.serialize_dates(deleted_time, None)
        assert serialized == "2023-01-01T12:00:00"
        
        # Test with None
        none_serialized = schema.serialize_dates(None, None)
        assert none_serialized is None


class TestToken:
    """Test Token schema."""
    
    def test_token_valid(self):
        """Test valid Token creation."""
        token = Token(
            access_token="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
            token_type="bearer"
        )
        
        assert token.access_token == "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
        assert token.token_type == "bearer"
    
    def test_token_missing_fields(self):
        """Test Token with missing fields."""
        with pytest.raises(ValidationError) as exc_info:
            Token(access_token="token123")
        
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("token_type",)
    
    def test_token_empty_values(self):
        """Test Token with empty values."""
        token = Token(
            access_token="",
            token_type=""
        )
        
        assert token.access_token == ""
        assert token.token_type == ""


class TestTokenData:
    """Test TokenData schema."""
    
    def test_token_data_username(self):
        """Test TokenData with username."""
        token_data = TokenData(username_or_email="testuser")
        
        assert token_data.username_or_email == "testuser"
    
    def test_token_data_email(self):
        """Test TokenData with email."""
        token_data = TokenData(username_or_email="user@example.com")
        
        assert token_data.username_or_email == "user@example.com"
    
    def test_token_data_missing_field(self):
        """Test TokenData with missing field."""
        with pytest.raises(ValidationError) as exc_info:
            TokenData()
        
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("username_or_email",)


class TestTokenBlacklistSchemas:
    """Test token blacklist schemas."""
    
    def test_token_blacklist_base(self):
        """Test TokenBlacklistBase schema."""
        expires_at = datetime(2023, 12, 31, 23, 59, 59)
        blacklist = TokenBlacklistBase(
            token="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
            expires_at=expires_at
        )
        
        assert blacklist.token == "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
        assert blacklist.expires_at == expires_at
    
    def test_token_blacklist_read(self):
        """Test TokenBlacklistRead schema."""
        expires_at = datetime(2023, 12, 31, 23, 59, 59)
        blacklist = TokenBlacklistRead(
            id=1,
            token="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
            expires_at=expires_at
        )
        
        assert blacklist.id == 1
        assert blacklist.token == "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
        assert blacklist.expires_at == expires_at
    
    def test_token_blacklist_create(self):
        """Test TokenBlacklistCreate schema."""
        expires_at = datetime(2023, 12, 31, 23, 59, 59)
        blacklist = TokenBlacklistCreate(
            token="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
            expires_at=expires_at
        )
        
        assert blacklist.token == "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
        assert blacklist.expires_at == expires_at
    
    def test_token_blacklist_update(self):
        """Test TokenBlacklistUpdate schema."""
        expires_at = datetime(2023, 12, 31, 23, 59, 59)
        blacklist = TokenBlacklistUpdate(
            token="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
            expires_at=expires_at
        )
        
        assert blacklist.token == "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
        assert blacklist.expires_at == expires_at
    
    def test_token_blacklist_missing_fields(self):
        """Test token blacklist schemas with missing fields."""
        with pytest.raises(ValidationError) as exc_info:
            TokenBlacklistBase(token="token123")
        
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("expires_at",)
    
    def test_token_blacklist_invalid_datetime(self):
        """Test token blacklist with invalid datetime."""
        with pytest.raises(ValidationError) as exc_info:
            TokenBlacklistBase(
                token="token123",
                expires_at="invalid-datetime"
            )
        
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("expires_at",)


class TestSchemaInheritance:
    """Test schema inheritance and combinations."""
    
    def test_combined_mixins(self):
        """Test combining multiple schema mixins."""
        from pydantic import BaseModel
        
        class CombinedSchema(UUIDSchema, TimestampSchema, PersistentDeletion, BaseModel):
            name: str
        
        schema = CombinedSchema(name="Test")
        
        # Check all mixin fields are present
        assert hasattr(schema, "uuid")
        assert hasattr(schema, "created_at")
        assert hasattr(schema, "updated_at")
        assert hasattr(schema, "deleted_at")
        assert hasattr(schema, "is_deleted")
        assert schema.name == "Test"
        
        # Check default values
        assert isinstance(schema.uuid, uuid_pkg.UUID)
        assert isinstance(schema.created_at, datetime)
        assert schema.updated_at is None
        assert schema.deleted_at is None
        assert schema.is_deleted is False
    
    def test_schema_serialization_methods(self):
        """Test that serialization methods work correctly."""
        timestamp_schema = TimestampSchema()
        deletion_schema = PersistentDeletion()
        
        # Test timestamp serialization
        test_datetime = datetime(2023, 1, 1, 12, 0, 0)
        assert timestamp_schema.serialize_dt(test_datetime, None) == "2023-01-01T12:00:00"
        assert timestamp_schema.serialize_updated_at(test_datetime, None) == "2023-01-01T12:00:00"
        
        # Test deletion serialization
        assert deletion_schema.serialize_dates(test_datetime, None) == "2023-01-01T12:00:00"
        
        # Test None serialization
        assert timestamp_schema.serialize_dt(None, None) is None
        assert timestamp_schema.serialize_updated_at(None, None) is None
        assert deletion_schema.serialize_dates(None, None) is None