from collections.abc import Callable, Generator
from datetime import UTC
from typing import Any
from unittest.mock import AsyncMock, Mock

from faker import Faker
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session
from src.app.core.config import settings
from src.app.main import app
from src.app.schemas.task import TaskRead

DATABASE_URI = settings.postgres_uri
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
    """
    Mock database session for unit tests.
    """
    return Mock(spec=AsyncSession)


@pytest.fixture
def mock_redis():
    """
    Mock Redis connection for unit tests.
    """
    mock_redis = Mock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.delete = AsyncMock(return_value=True)
    return mock_redis


@pytest.fixture(scope="session")
def event_loop():
    """
    Create an instance of the default event loop for the test session.
    """
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    yield loop
    # Don't close the loop if it's still running
    if not loop.is_closed():
        try:
            loop.close()
        except RuntimeError:
            pass


@pytest.fixture(scope="session", autouse=True)
def setup_cache_client():
    """
    Initialize cache client for tests to prevent MissingClientError.
    """
    from unittest.mock import AsyncMock, Mock

    from src.app.core.utils import cache

    # Create a mock Redis client for tests
    mock_client = Mock()
    mock_client.get = AsyncMock(return_value=None)
    mock_client.set = AsyncMock(return_value=True)
    mock_client.delete = AsyncMock(return_value=True)
    mock_client.exists = AsyncMock(return_value=False)
    mock_client.expire = AsyncMock(return_value=True)
    mock_client.keys = AsyncMock(return_value=[])
    mock_client.pipeline = Mock()
    mock_client.pipeline.return_value.set = Mock()
    mock_client.pipeline.return_value.expire = Mock()
    mock_client.pipeline.return_value.execute = AsyncMock(return_value=[])

    # Set the mock client globally for tests
cache.client = mock_client

    yield

    # Clean up after tests
    cache.client = None


# -------------------------
# Postgres Testcontainers fixtures for integration tests
# -------------------------


@pytest.fixture(scope="session")
def pg_container():
    """Start a Postgres container for integration tests.

    Requires `testcontainers[postgresql]` to be installed and Docker running.
    """
    try:
        from testcontainers.postgres import PostgresContainer  # type: ignore
    except Exception as e:  # pragma: no cover - optional dependency
        pytest.skip(f"testcontainers not available: {e}")

    with PostgresContainer("postgres:16-alpine") as postgres:
        yield postgres


@pytest.fixture()
async def test_app_and_db_pg(pg_container):
    """Create a FastAPI app bound to the Postgres testcontainer via dependency override."""
    from contextlib import asynccontextmanager
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from src.app.api import router as api_router
    from src.app.core.config import settings
    from src.app.core.db.database import Base
    from src.app.core.setup import create_application

    # Convert DSN to async driver URL
    sync_url: str = pg_container.get_connection_url()
    async_url = sync_url.replace("postgresql://", "postgresql+asyncpg://")

    # Create engine & tables
    engine = create_async_engine(async_url, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    @asynccontextmanager
    async def noop_lifespan(app: FastAPI):
        yield

    app_local = create_application(
        router=api_router, settings=settings, create_tables_on_start=False, lifespan=noop_lifespan
    )

    from src.app.core.db.database import async_get_db as real_async_get_db

    async def override_async_get_db():
        async with SessionLocal() as session:
            yield session

    app_local.dependency_overrides[real_async_get_db] = override_async_get_db

    try:
        yield app_local, SessionLocal
    finally:
        app_local.dependency_overrides.clear()
        await engine.dispose()


@pytest.fixture(scope="function")
async def async_db_session():
    """
    Create a fresh async database session for each test with proper cleanup.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker
    from src.app.core.config import settings
    from src.app.core.db.database import Base

    # Create test database engine
    test_engine = create_async_engine(
        settings.POSTGRES_ASYNC_PREFIX + settings.postgres_uri, echo=False, pool_pre_ping=True
    )

    try:
        # Create all tables
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Create session
        TestSessionLocal = sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

        async with TestSessionLocal() as session:
            yield session

    finally:
        # Clean up - drop all tables with CASCADE
        try:
            async with test_engine.begin() as conn:
                await conn.run_sync(lambda sync_conn: Base.metadata.drop_all(sync_conn, checkfirst=True))
        except Exception:
            pass  # Ignore cleanup errors

        await test_engine.dispose()


@pytest.fixture
async def test_user_factory(async_db_session):
    """
    Factory for creating test users with realistic data.
    """
    from src.app.core.security import get_password_hash
    from src.app.models.user import User

    created_users = []

    async def _create_user(
        name: str = None,
        username: str = None,
        email: str = None,
        password: str = "testpassword123",
        is_superuser: bool = False,
    ):
        user = User(
            name=name or fake.name(),
            username=username or fake.user_name(),
            email=email or fake.email(),
            hashed_password=get_password_hash(password),
            is_superuser=is_superuser,
        )
        async_db_session.add(user)
        await async_db_session.commit()
        await async_db_session.refresh(user)
        created_users.append(user)
        return user

    yield _create_user

    # Cleanup
    for user in created_users:
        await async_db_session.delete(user)
    await async_db_session.commit()


@pytest.fixture
async def test_task_factory(async_db_session):
    """
    Factory for creating test tasks with realistic data.
    """
    from src.app.models.task import Task

    created_tasks = []

    async def _create_task(
        created_by_user_id: int,
        title: str = None,
        text: str = None,
        source_language: str = "en",
        target_language: str = "es",
        task_type: str = "text_translation",
        status: str = "pending",
        assignee_id: int = None,
    ):
        task = Task(
            created_by_user_id=created_by_user_id,
            title=title or fake.sentence(),
            text=text or fake.text(),
            source_language=source_language,
            target_language=target_language,
            task_type=task_type,
            status=status,
            assignee_id=assignee_id,
        )
        async_db_session.add(task)
        await async_db_session.commit()
        await async_db_session.refresh(task)
        created_tasks.append(task)
        return task

    yield _create_task

    # Cleanup
    for task in created_tasks:
        await async_db_session.delete(task)
    await async_db_session.commit()


@pytest.fixture
def sample_user_data():
    """
    Generate sample user data for tests.
    """
    return {
        "name": fake.name(),
        "username": fake.user_name(),
        "email": fake.email(),
        "password": fake.password(),
    }


@pytest.fixture
def sample_user_read():
    """
    Generate a sample UserRead object.
    """
    import uuid

    from src.app.schemas.user import UserRead

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
    """
    Mock current user from auth dependency.
    """
    return {
        "id": 1,
        "username": fake.user_name(),
        "email": fake.email(),
        "name": fake.name(),
        "is_superuser": False,
    }


@pytest.fixture
def sample_task_data():
    """
    Generate sample task data for tests.
    """
    return {
        "title": fake.sentence(nb_words=4),
        "text": fake.text(max_nb_chars=200),
        "source_language": "en",
        "task_type": "text_translation",
    }


@pytest.fixture
def sample_task_read():
    """
    Generate a sample TaskRead object.
    """
    return TaskRead(
        id=1,
        title=fake.sentence(nb_words=4),
        text=fake.text(max_nb_chars=200),
        media_url=None,
        created_by_user_id=1,
        assignee_id=None,
        translated_by_user_id=None,
        created_at=fake.date_time(tzinfo=UTC),
        source_language="en",
        target_language="es",
        task_type="text_translation",
        status="pending",
        translated_text=None,
        translated_at=None,
    )


@pytest.fixture
def mock_jwt_token():
    """
    Mock JWT token for authentication tests.
    """
    return "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIiwiZXhwIjoxNjQwOTk1MjAwfQ.test_token"


@pytest.fixture
def auth_headers(mock_jwt_token):
    """
    Generate authorization headers for authenticated requests.
    """
    return {"Authorization": f"Bearer {mock_jwt_token}"}


@pytest.fixture
def superuser_dict():
    """
    Mock superuser from auth dependency.
    """
    return {
        "id": 2,
        "username": "admin",
        "email": "admin@example.com",
        "name": "Admin User",
        "is_superuser": True,
    }


@pytest.fixture
def async_client():
    """
    Create a test client for API testing.
    """
    from fastapi.testclient import TestClient
    from src.app.main import app

    with TestClient(app) as client:
        yield client


@pytest.fixture
def authenticated_client(async_client):
    """
    Create an authenticated HTTP client with a test user.
    """
    # For now, return the client with mock authentication headers
    # This will be improved when we implement proper auth testing
    mock_token = "mock_jwt_token_for_testing"
    async_client.headers.update({"Authorization": f"Bearer {mock_token}"})

    # Mock user data
    mock_user = {"id": 1, "username": "testuser", "email": "test@example.com", "is_superuser": False}

    yield async_client, mock_user


@pytest.fixture
def superuser_client(async_client):
    """
    Create an authenticated HTTP client with a superuser.
    """
    # Mock superuser authentication
    mock_token = "mock_superuser_jwt_token_for_testing"
    async_client.headers.update({"Authorization": f"Bearer {mock_token}"})

    # Mock superuser data
    mock_superuser = {"id": 2, "username": "superuser", "email": "super@example.com", "is_superuser": True}

    yield async_client, mock_superuser


@pytest.fixture
def mock_external_api(monkeypatch):
    """
    Mock external API calls for testing.
    """
    from unittest.mock import AsyncMock

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "success", "data": "mocked"}

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.put.return_value = mock_response
    mock_client.delete.return_value = mock_response

    monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: mock_client)

    return mock_client


@pytest.fixture
def mock_database_error(monkeypatch):
    """
    Mock database errors for testing error scenarios.
    """
    from unittest.mock import AsyncMock

    from sqlalchemy.exc import SQLAlchemyError

    def _mock_error(operation="execute"):
        mock_func = AsyncMock(side_effect=SQLAlchemyError("Database error"))
        monkeypatch.setattr(f"sqlalchemy.ext.asyncio.AsyncSession.{operation}", mock_func)
        return mock_func

    return _mock_error


@pytest.fixture
def freeze_time():
    """
    Fixture for freezing time in tests.
    """
    from datetime import datetime
    from unittest.mock import patch

    def _freeze(frozen_time=None):
        if frozen_time is None:
            frozen_time = datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC)

        mock_datetime = patch("app.models.task.datetime")
        mock_utils_datetime = patch("app.core.utils.datetime")
        return mock_datetime, mock_utils_datetime

    return _freeze


@pytest.fixture(autouse=True)
def mock_jwt_validation(monkeypatch, request):
    """
    Mock JWT validation to prevent token parsing errors in tests.
    """
    # Do not mock for integration/e2e tests so tokens are verified end-to-end
    if request.node.get_closest_marker("integration") or request.node.get_closest_marker("e2e"):
        return
    from datetime import UTC, datetime, timedelta

    import jose.jwt

    # Store the original decode function
    original_decode = jose.jwt.decode

    # Mock JWT decode to return a valid payload with token_type
    def mock_jwt_decode(token, *args, **kwargs):
        # Check if we should bypass mocking (when options={'verify_signature': False})
        options = kwargs.get("options", {})
        if options.get("verify_signature") is False:
            # Use the original jwt.decode for test verification
            return original_decode(token, *args, **kwargs)

        # Default mock payload for other cases
        return {
            "sub": "testuser",
            "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
            "token_type": "access",
        }

    monkeypatch.setattr("jose.jwt.decode", mock_jwt_decode)
    monkeypatch.setattr("src.app.core.security.jwt.decode", mock_jwt_decode)

    return mock_jwt_decode
