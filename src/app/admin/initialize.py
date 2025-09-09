import asyncio
from typing import Optional

from crudadmin import CRUDAdmin

from ..core.config import settings
from ..core.db.database import async_engine, async_get_db
from .views import register_admin_views


def _should_provide_initial_admin(username: str) -> bool:
    """Return True if we should pass initial_admin to CRUDAdmin.

    We proactively check if an admin user with the configured username already
    exists in the admin table to avoid UNIQUE constraint violations on
    subsequent startups or requests. If the table doesn't exist yet or any
    error occurs while checking, we return True to allow first-time creation.
    """

    async def _check() -> bool:
        try:
            async with async_engine.connect() as conn:
                # Attempt a direct query; if table doesn't exist this will raise.
                result = await conn.exec_driver_sql(
                    "SELECT 1 FROM admin_user WHERE username = :username LIMIT 1",
                    {"username": username},
                )
                row = result.first()
                return row is None
        except Exception:
            # If table is missing or any error, treat as first-time setup.
            return True

    # create_admin_interface is called at import time (no running loop),
    # so it's safe to run a short async check synchronously here.
    try:
        return asyncio.run(_check())
    except RuntimeError:
        # Fallback if there's already a running loop (e.g., unit tests)
        # In that case, don't risk blocking; let CRUDAdmin handle creation.
        return True


def create_admin_interface() -> CRUDAdmin | None:
    """Create and configure the admin interface."""
    if not settings.CRUD_ADMIN_ENABLED:
        return None

    session_backend = "memory"
    redis_config = None

    if settings.CRUD_ADMIN_REDIS_ENABLED:
        session_backend = "redis"
        redis_config = {
            "host": settings.CRUD_ADMIN_REDIS_HOST,
            "port": settings.CRUD_ADMIN_REDIS_PORT,
            "db": settings.CRUD_ADMIN_REDIS_DB,
            "password": (
                settings.CRUD_ADMIN_REDIS_PASSWORD if settings.CRUD_ADMIN_REDIS_PASSWORD not in ("None", "") else None
            ),
            "ssl": settings.CRUD_ADMIN_REDIS_SSL,
        }

    initial_admin: Optional[dict[str, str]] = None
    if settings.ADMIN_USERNAME and settings.ADMIN_PASSWORD and _should_provide_initial_admin(settings.ADMIN_USERNAME):
        initial_admin = {"username": settings.ADMIN_USERNAME, "password": settings.ADMIN_PASSWORD}

    admin = CRUDAdmin(
        session=async_get_db,
        SECRET_KEY=settings.SECRET_KEY.get_secret_value(),
        mount_path=settings.CRUD_ADMIN_MOUNT_PATH,
        session_backend=session_backend,
        redis_config=redis_config,
        allowed_ips=settings.CRUD_ADMIN_ALLOWED_IPS_LIST if settings.CRUD_ADMIN_ALLOWED_IPS_LIST else None,
        allowed_networks=settings.CRUD_ADMIN_ALLOWED_NETWORKS_LIST
        if settings.CRUD_ADMIN_ALLOWED_NETWORKS_LIST
        else None,
        max_sessions_per_user=settings.CRUD_ADMIN_MAX_SESSIONS,
        session_timeout_minutes=settings.CRUD_ADMIN_SESSION_TIMEOUT,
        secure_cookies=settings.SESSION_SECURE_COOKIES,
        enforce_https=settings.CRUD_ADMIN_ENFORCE_HTTPS,
        track_events=settings.CRUD_ADMIN_TRACK_EVENTS,
        track_sessions_in_db=settings.CRUD_ADMIN_TRACK_SESSIONS,
        initial_admin=initial_admin,
    )

    register_admin_views(admin)

    return admin
