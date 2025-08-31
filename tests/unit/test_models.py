"""Unit tests for database models."""

import uuid
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.tier import Tier
from app.models.task import Task
from app.models.rate_limit import RateLimit


class TestUserModel:
    """Test User model functionality."""

    @pytest.mark.unit
    def test_user_creation(self):
        """Test creating a user instance."""
        user = User(
            name="Test User",
            username="testuser",
            email="test@example.com",
            hashed_password="hashed_password_123",
            profile_image_url="https://example.com/profile.jpg",
            is_superuser=False
        )
        user.tier_id = 1
        
        assert user.name == "Test User"
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.hashed_password == "hashed_password_123"
        assert user.profile_image_url == "https://example.com/profile.jpg"
        assert user.is_superuser is False
        assert user.tier_id == 1
        assert user.is_deleted is False
        assert isinstance(user.uuid, uuid.UUID)
        assert isinstance(user.created_at, datetime)

    @pytest.mark.unit
    def test_user_defaults(self):
        """Test user model default values."""
        user = User(
            name="Test User",
            username="testuser",
            email="test@example.com",
            hashed_password="hashed_password_123"
        )
        
        assert user.profile_image_url == "https://profileimageurl.com"
        assert user.is_superuser is False
        assert user.is_deleted is False
        assert user.tier_id is None
        assert user.updated_at is None
        assert user.deleted_at is None
        assert isinstance(user.uuid, uuid.UUID)
        assert isinstance(user.created_at, datetime)

    @pytest.mark.unit
    def test_user_superuser(self):
        """Test creating a superuser."""
        user = User(
            name="Admin User",
            username="admin",
            email="admin@example.com",
            hashed_password="hashed_password_123",
            is_superuser=True
        )
        
        assert user.is_superuser is True
        assert user.name == "Admin User"
        assert user.username == "admin"

    @pytest.mark.unit
    def test_user_soft_delete(self):
        """Test user soft delete functionality."""
        user = User(
            name="Test User",
            username="testuser",
            email="test@example.com",
            hashed_password="hashed_password_123",
            is_deleted=True,
            deleted_at=datetime.now(timezone.utc)
        )
        
        assert user.is_deleted is True
        assert user.deleted_at is not None
        assert isinstance(user.deleted_at, datetime)


class TestTierModel:
    """Test Tier model functionality."""

    @pytest.mark.unit
    def test_tier_creation(self):
        """Test creating a tier instance."""
        tier = Tier(
            name="Premium"
        )
        
        assert tier.name == "Premium"
        assert isinstance(tier.created_at, datetime)
        assert tier.updated_at is None

    @pytest.mark.unit
    def test_tier_defaults(self):
        """Test tier model default values."""
        tier = Tier(name="Basic")
        
        assert tier.name == "Basic"
        assert tier.updated_at is None
        assert isinstance(tier.created_at, datetime)

    @pytest.mark.unit
    def test_tier_update(self):
        """Test tier update functionality."""
        tier = Tier(
            name="Standard",
            updated_at=datetime.now(timezone.utc)
        )
        
        assert tier.name == "Standard"
        assert tier.updated_at is not None
        assert isinstance(tier.updated_at, datetime)


class TestTaskModel:
    """Test Task model functionality."""

    @pytest.mark.unit
    def test_task_creation(self):
        """Test creating a task instance."""
        task = Task(
            created_by_user_id=1,
            title="Translation Task",
            text="This is a text to translate",
            source_language="en",
            task_type="translation",
            assignee_id=2,
            target_language="es",
            status="pending"
        )
        
        assert task.created_by_user_id == 1
        assert task.title == "Translation Task"
        assert task.text == "This is a text to translate"
        assert task.source_language == "en"
        assert task.task_type == "translation"
        assert task.assignee_id == 2
        assert task.target_language == "es"
        assert task.status == "pending"
        assert task.is_deleted is False
        assert isinstance(task.uuid, uuid.UUID)
        assert isinstance(task.created_at, datetime)

    @pytest.mark.unit
    def test_task_defaults(self):
        """Test task model default values."""
        task = Task(
            created_by_user_id=1,
            title="Simple Task",
            text="Task content",
            source_language="en",
            task_type="review"
        )
        
        assert task.assignee_id is None
        assert task.translated_by_user_id is None
        assert task.target_language is None
        assert task.translated_text is None
        assert task.media_url is None
        assert task.status == "pending"
        assert task.is_deleted is False
        assert task.updated_at is None
        assert task.translated_at is None
        assert task.deleted_at is None
        assert isinstance(task.uuid, uuid.UUID)
        assert isinstance(task.created_at, datetime)

    @pytest.mark.unit
    def test_task_with_translation(self):
        """Test task with translation data."""
        task = Task(
            created_by_user_id=1,
            title="Translation Task",
            text="Hello world",
            source_language="en",
            task_type="translation",
            assignee_id=2,
            translated_by_user_id=3,
            target_language="es",
            translated_text="Hola mundo",
            status="completed",
            translated_at=datetime.now(timezone.utc)
        )
        
        assert task.translated_by_user_id == 3
        assert task.translated_text == "Hola mundo"
        assert task.status == "completed"
        assert task.translated_at is not None
        assert isinstance(task.translated_at, datetime)

    @pytest.mark.unit
    def test_task_with_media(self):
        """Test task with media URL."""
        task = Task(
            created_by_user_id=1,
            title="Media Task",
            text="Task with media",
            source_language="en",
            task_type="transcription",
            media_url="https://example.com/audio.mp3"
        )
        
        assert task.media_url == "https://example.com/audio.mp3"
        assert task.task_type == "transcription"

    @pytest.mark.unit
    def test_task_soft_delete(self):
        """Test task soft delete functionality."""
        task = Task(
            created_by_user_id=1,
            title="Deleted Task",
            text="This task is deleted",
            source_language="en",
            task_type="translation",
            is_deleted=True,
            deleted_at=datetime.now(timezone.utc)
        )
        
        assert task.is_deleted is True
        assert task.deleted_at is not None
        assert isinstance(task.deleted_at, datetime)


class TestRateLimitModel:
    """Test RateLimit model functionality."""

    @pytest.mark.unit
    def test_rate_limit_creation(self):
        """Test creating a rate limit instance."""
        rate_limit = RateLimit(
            tier_id=1,
            name="API Rate Limit",
            path="/api/v1/tasks",
            limit=100,
            period=3600
        )
        
        assert rate_limit.tier_id == 1
        assert rate_limit.name == "API Rate Limit"
        assert rate_limit.path == "/api/v1/tasks"
        assert rate_limit.limit == 100
        assert rate_limit.period == 3600
        assert isinstance(rate_limit.created_at, datetime)
        assert rate_limit.updated_at is None

    @pytest.mark.unit
    def test_rate_limit_defaults(self):
        """Test rate limit model default values."""
        rate_limit = RateLimit(
            tier_id=2,
            name="Basic Rate Limit",
            path="/api/v1/users",
            limit=50,
            period=1800
        )
        
        assert rate_limit.updated_at is None
        assert isinstance(rate_limit.created_at, datetime)

    @pytest.mark.unit
    def test_rate_limit_update(self):
        """Test rate limit update functionality."""
        rate_limit = RateLimit(
            tier_id=1,
            name="Updated Rate Limit",
            path="/api/v1/auth",
            limit=200,
            period=7200,
            updated_at=datetime.now(timezone.utc)
        )
        
        assert rate_limit.limit == 200
        assert rate_limit.period == 7200
        assert rate_limit.updated_at is not None
        assert isinstance(rate_limit.updated_at, datetime)

    @pytest.mark.unit
    def test_rate_limit_different_tiers(self):
        """Test rate limits for different tiers."""
        basic_limit = RateLimit(
            tier_id=1,
            name="Basic Tier Limit",
            path="/api/v1/tasks",
            limit=10,
            period=3600
        )
        
        premium_limit = RateLimit(
            tier_id=2,
            name="Premium Tier Limit",
            path="/api/v1/tasks",
            limit=1000,
            period=3600
        )
        
        assert basic_limit.tier_id == 1
        assert basic_limit.limit == 10
        assert premium_limit.tier_id == 2
        assert premium_limit.limit == 1000
        assert basic_limit.path == premium_limit.path
        assert basic_limit.period == premium_limit.period


class TestModelRelationships:
    """Test model relationships and foreign keys."""

    @pytest.mark.unit
    def test_user_tier_relationship(self):
        """Test user-tier relationship."""
        user = User(
            name="Test User",
            username="testuser",
            email="test@example.com",
            hashed_password="hashed_password_123"
        )
        user.tier_id = 1
        
        assert user.tier_id == 1

    @pytest.mark.unit
    def test_task_user_relationships(self):
        """Test task-user relationships."""
        task = Task(
            created_by_user_id=1,
            title="Test Task",
            text="Task content",
            source_language="en",
            task_type="translation",
            assignee_id=2,
            translated_by_user_id=3
        )
        
        assert task.created_by_user_id == 1
        assert task.assignee_id == 2
        assert task.translated_by_user_id == 3

    @pytest.mark.unit
    def test_rate_limit_tier_relationship(self):
        """Test rate limit-tier relationship."""
        rate_limit = RateLimit(
            tier_id=1,
            name="Test Rate Limit",
            path="/api/v1/test",
            limit=100,
            period=3600
        )
        
        assert rate_limit.tier_id == 1

    @pytest.mark.unit
    def test_task_optional_relationships(self):
        """Test task optional foreign key relationships."""
        task = Task(
            created_by_user_id=1,
            title="Simple Task",
            text="Task content",
            source_language="en",
            task_type="review"
        )
        
        # These should be None by default
        assert task.assignee_id is None
        assert task.translated_by_user_id is None