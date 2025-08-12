import sentry_sdk
from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette_admin.contrib.sqlmodel import Admin, ModelView
from starlette_admin.auth import AdminConfig, AdminUser, AuthProvider
from starlette_admin.exceptions import FormValidationError, LoginFailed

from app.api.main import api_router
from app.core.config import settings
from app.core.db import engine
from app.models import User, Item, Task, TaskSubmission, UserEarning


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


if settings.SENTRY_DSN and settings.ENVIRONMENT != "local":
    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
)

# Set all CORS enabled origins
if settings.all_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.all_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Add session middleware for admin authentication
app.add_middleware(SessionMiddleware, secret_key="your-secret-key")

app.include_router(api_router, prefix=settings.API_V1_STR)

# Starlette Admin Authentication Provider
class AdminAuthProvider(AuthProvider):
    async def login(
        self,
        username: str,
        password: str,
        remember_me: bool,
        request: Request,
        response: RedirectResponse,
    ) -> RedirectResponse:
        # Simple check - in production, use proper password hashing
        if username == "admin" and password == "admin":
            request.session.update({"token": "authenticated"})
            return response
        raise LoginFailed("Invalid username or password")

    async def is_authenticated(self, request: Request) -> bool:
        token = request.session.get("token")
        return token == "authenticated"

    def get_admin_config(self, request: Request) -> AdminConfig:
        return AdminConfig(app_title="ACFLP Admin")

    def get_admin_user(self, request: Request) -> AdminUser:
        return AdminUser(username="admin")

    async def logout(self, request: Request, response: RedirectResponse) -> RedirectResponse:
        request.session.clear()
        return response

# Starlette Admin - Django-like automatic admin interface
admin = Admin(
    engine,
    title="ACFLP Admin",
    base_url="/admin",
    auth_provider=AdminAuthProvider(),
)

# Register admin views with Starlette Admin
admin.add_view(ModelView(User, icon="fa fa-users"))
admin.add_view(ModelView(Item, icon="fa fa-box"))
admin.add_view(ModelView(Task, icon="fa fa-tasks"))
admin.add_view(ModelView(TaskSubmission, icon="fa fa-file-text"))
admin.add_view(ModelView(UserEarning, icon="fa fa-money"))

# Mount admin to FastAPI app
admin.mount_to(app)
