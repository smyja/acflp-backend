from contextlib import suppress

import anyio
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import settings
from ...core.db.database import async_get_db
from ...core.schemas import HealthCheck
from ...core.utils import cache, queue, rate_limit

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthCheck)
async def health() -> HealthCheck:
    return HealthCheck(
        name=settings.APP_NAME,
        version=settings.APP_VERSION or "",
        description=settings.APP_DESCRIPTION or "",
    )


@router.get("/ready")
async def readiness(response: Response, db: AsyncSession = Depends(async_get_db)) -> dict[str, str]:
    """Readiness probe with lightweight dependency checks.

    - DB: simple `SELECT 1` with 1s timeout
    - Redis cache: `PING` if client configured
    - Rate limiter Redis: `PING` if client configured
    - Queue (ARQ): ping if pool configured (best-effort)

    Returns 200 when all available dependencies are healthy, 503 otherwise.
    """

    results: dict[str, str] = {}
    ok = True

    # Prevent caching by proxies
    response.headers["Cache-Control"] = "no-store"

    # Database check
    try:
        async with anyio.move_on_after(1):  # 1s timeout
            await db.execute("SELECT 1")
            results["database"] = "ok"
    except Exception:
        results["database"] = "fail"
        ok = False

    # Redis cache check (optional)
    try:
        if cache.client is not None:
            async with anyio.move_on_after(0.5):
                pong = await cache.client.ping()
                results["redis_cache"] = "ok" if pong else "fail"
                ok = ok and bool(pong)
        else:
            results["redis_cache"] = "unconfigured"
    except Exception:
        results["redis_cache"] = "fail"
        ok = False

    # Rate limiter Redis check (optional)
    try:
        if rate_limit.client is not None:
            async with anyio.move_on_after(0.5):
                pong = await rate_limit.client.ping()
                results["redis_rate_limit"] = "ok" if pong else "fail"
                ok = ok and bool(pong)
        else:
            results["redis_rate_limit"] = "unconfigured"
    except Exception:
        results["redis_rate_limit"] = "fail"
        ok = False

    # Queue (ARQ) check (best effort)
    try:
        if queue.pool is not None:
            # Some ARQ versions support ping(); if not, just mark as present
            ping_ok = False
            with suppress(Exception):
                # type: ignore[attr-defined]
                ping_ok = bool(await queue.pool.ping())  # noqa: F841
            results["queue"] = "ok" if ping_ok or queue.pool is not None else "fail"
            ok = ok and (ping_ok or queue.pool is not None)
        else:
            results["queue"] = "unconfigured"
    except Exception:
        results["queue"] = "fail"
        ok = False

    if not ok:
        # Return details with 503
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=results)

    results["status"] = "ready"
    return results
