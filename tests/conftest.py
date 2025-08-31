from collections.abc import Callable, Generator
from typing import Any
from unittest.mock import AsyncMock, Mock
import uuid
from datetime import datetime, timezone

import pytest
from faker import Faker
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session

from app.core.config import settings
from app.main import app
from app.schemas.user import UserRead, UserCreate
from app.schemas.post import PostRead, PostCreate
from app.schemas.tier import TierRead, TierCreate
from app.schemas.task import TaskRead, TaskCreate

DATABASE_URI = settings.POSTGRES_URI
DATABASE_PREFIX = settings.POSTGRES_SYNC_PREFIX

sync_engine = create_engine(DATABASE_PREFIX + DATABASE_URI)
local_session = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)


fake = Faker()


@pytest.fixture(scope="session")
def client() -> Generator[TestClient, Any, None]:
    with TestClient(app) as _client:
        yield _client
    app.dependency_overrides = {}
    sync_engine.dispose()


@pytest.fixture
def db() -> Generator[Session, Any, None]:
    session = local_session()
    yield session
    session.close()


def override_dependency(dependency: Callable[..., Any], mocked_response: Any) -> None:
    app.dependency_overrides[dependency] = lambda: mocked_response


@pytest.fixture
def mock_db():
    """Mock database session for unit tests."""
    return Mock(spec=AsyncSession)


@pytest.fixture
def mock_redis():
    """Mock Redis connection for unit tests."""
    mock_redis = Mock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.delete = AsyncMock(return_value=True)
    return mock_redis


@pytest.fixture
def sample_user_data():
    """Generate sample user data for tests."""
    return {
        "name": fake.name(),
        "username": fake.user_name(),
        "email": fake.email(),
        "password": fake.password(),
    }


@pytest.fixture
def sample_user_read():
    """Generate a sample UserRead object."""
    import uuid

    from app.schemas.user import UserRead

    return UserRead(
        id=1,
        uuid=uuid.uuid4(),
        name=fake.name(),
        username=fake.user_name(),
        email=fake.email(),
        profile_image_url=fake.image_url(),
        is_superuser=False,
        created_at=fake.date_time(),
        updated_at=fake.date_time(),
        tier_id=None,
    )


@pytest.fixture
def current_user_dict():
    """Mock current user from auth dependency."""
    return {
        "id": 1,
        "username": fake.user_name(),
        "email": fake.email(),
        "name": fake.name(),
        "is_superuser": False,
    }


@pytest.fixture
def sample_post_data():
    """Generate sample post data for tests."""
    return {
        "title": fake.sentence(nb_words=4),
        "content": fake.text(max_nb_chars=500),
        "media_url": fake.image_url(),
    }


@pytest.fixture
def sample_post_read():
    """Generate a sample PostRead object."""
    return PostRead(
        id=1,
        title=fake.sentence(nb_words=4),
        content=fake.text(max_nb_chars=500),
        media_url=fake.image_url(),
        created_by_user_id=1,
        created_at=fake.date_time(tzinfo=timezone.utc),
        updated_at=fake.date_time(tzinfo=timezone.utc),
    )


@pytest.fixture
def sample_tier_data():
    """Generate sample tier data for tests."""
    return {
        "name": fake.word().capitalize(),
        "description": fake.text(max_nb_chars=200),
    }


@pytest.fixture
def sample_tier_read():
    """Generate a sample TierRead object."""
    return TierRead(
        id=1,
        name=fake.word().capitalize(),
        description=fake.text(max_nb_chars=200),
        created_at=fake.date_time(tzinfo=timezone.utc),
        updated_at=fake.date_time(tzinfo=timezone.utc),
    )


@pytest.fixture
def sample_task_data():
    """Generate sample task data for tests."""
    return {
        "title": fake.sentence(nb_words=4),
        "text": fake.text(max_nb_chars=200),
        "source_language": "en",
        "task_type": "text_translation",
    }


@pytest.fixture
def sample_task_read():
    """Generate a sample TaskRead object."""
    return TaskRead(
        id=1,
        title=fake.sentence(nb_words=4),
        text=fake.text(max_nb_chars=200),
        media_url=None,
        created_by_user_id=1,
        assignee_id=None,
        translated_by_user_id=None,
        created_at=fake.date_time(tzinfo=timezone.utc),
        source_language="en",
        target_language="es",
        task_type="text_translation",
        status="pending",
        translated_text=None,
        translated_at=None,
    )


@pytest.fixture
def mock_jwt_token():
    """Mock JWT token for authentication tests."""
    return "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIiwiZXhwIjoxNjQwOTk1MjAwfQ.test_token"


@pytest.fixture
def auth_headers(mock_jwt_token):
    """Generate authorization headers for authenticated requests."""
    return {"Authorization": f"Bearer {mock_jwt_token}"}


@pytest.fixture
def superuser_dict():
    """Mock superuser from auth dependency."""
    return {
        "id": 2,
        "username": "admin",
        "email": "admin@example.com",
        "name": "Admin User",
        "is_superuser": True,
    }
