from fastapi import APIRouter

from .login import router as login_router
from .logout import router as logout_router
from .oauth import router as oauth_router
from .tasks import router as tasks_router
from .tasks_api import router as tasks_api_router
from .users import router as users_router
from .health import router as health_router

router = APIRouter(prefix="/v1")
router.include_router(login_router)
router.include_router(logout_router)
router.include_router(oauth_router)
router.include_router(users_router)
router.include_router(tasks_api_router)
router.include_router(tasks_router)
router.include_router(health_router)
