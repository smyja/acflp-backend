from fastapi import APIRouter

from ...core.config import settings
from ...core.schemas import HealthCheck

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthCheck)
async def health() -> HealthCheck:
    return HealthCheck(
        name=settings.APP_NAME,
        version=settings.APP_VERSION or "",
        description=settings.APP_DESCRIPTION or "",
    )
