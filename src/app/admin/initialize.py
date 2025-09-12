import asyncio

from crudadmin import CRUDAdmin

# Runtime monkey patch: coerce string IDs to integers in FastCRUD.get
# Some admin routes pass path params as strings (e.g., "1"). Postgres won't
# compare integer columns to VARCHAR without an explicit cast, which causes
# `operator does not exist: integer = character varying`. To avoid touching the
# third-party admin package internals, coerce common numeric identifiers.
try:  # pragma: no cover – best-effort safety patch
    from fastcrud.crud.fast_crud import FastCRUD as _FastCRUD  # type: ignore

    def _coerce_id(kwargs: dict) -> None:
        if "id" in kwargs and isinstance(kwargs["id"], str):
            v = kwargs["id"].strip()
            if v.isdigit():
                kwargs["id"] = int(v)

    _orig_get = _FastCRUD.get
    async def _patched_get(self, *args, **kwargs):  # type: ignore[no-redef]
        _coerce_id(kwargs)
        return await _orig_get(self, *args, **kwargs)
    _FastCRUD.get = _patched_get  # type: ignore[assignment]

    # Patch a few more commonly used methods that receive id in kwargs
    _orig_update = _FastCRUD.update
    async def _patched_update(self, *args, **kwargs):  # type: ignore[no-redef]
        _coerce_id(kwargs)
        return await _orig_update(self, *args, **kwargs)
    _FastCRUD.update = _patched_update  # type: ignore[assignment]

    _orig_delete = _FastCRUD.delete
    async def _patched_delete(self, *args, **kwargs):  # type: ignore[no-redef]
        _coerce_id(kwargs)
        return await _orig_delete(self, *args, **kwargs)
    _FastCRUD.delete = _patched_delete  # type: ignore[assignment]

    _orig_exists = _FastCRUD.exists
    async def _patched_exists(self, *args, **kwargs):  # type: ignore[no-redef]
        _coerce_id(kwargs)
        return await _orig_exists(self, *args, **kwargs)
    _FastCRUD.exists = _patched_exists  # type: ignore[assignment]
except Exception:  # pragma: no cover – if anything fails, admin will still start
    pass

from ..core.config import settings
from ..core.db.database import async_get_db
from .views import register_admin_views


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

    # Provide initial admin if configured; duplicate creation is handled gracefully
    # during admin.initialize() in app lifespan.
    initial_admin: dict[str, str] | None = None
    if settings.ADMIN_USERNAME and settings.ADMIN_PASSWORD:
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
