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
from starlette.templating import Jinja2Templates

from app.api.main import api_router
from app.core.config import settings
from app.core.db import engine
from app.models import User, Item, Task, TaskSubmission, UserEarning
from app.admin import BulkTaskImportView, FlexibleBulkImportView


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
        from sqlmodel import Session, select
        from app.core.security import verify_password

        # Authenticate against the actual user database
        with Session(engine) as session:
            user = session.exec(select(User).where(User.email == username)).first()

            if (
                user
                and user.is_superuser
                and verify_password(password, user.hashed_password)
            ):
                request.session.update(
                    {
                        "admin_user": username,
                        "admin_user_id": str(user.id),
                        "admin_user_name": user.full_name or username,
                    }
                )
            else:
                raise LoginFailed("Invalid credentials or insufficient permissions")
        return response

    async def is_authenticated(self, request: Request) -> bool:
        return request.session.get("admin_user") is not None

    def get_admin_config(self, request: Request) -> AdminConfig:
        return AdminConfig(app_title="ACFLP Admin")

    def get_admin_user(self, request: Request) -> AdminUser:
        username = request.session.get("admin_user", "admin")
        display_name = request.session.get("admin_user_name", username)
        return AdminUser(username=display_name)

    async def logout(
        self, request: Request, response: RedirectResponse
    ) -> RedirectResponse:
        request.session.clear()
        return response


# Configure templates for custom admin views
templates = Jinja2Templates(directory="app/templates")



admin = Admin(
    engine,
    title="ACFLP Admin",
    base_url="/admin",
    auth_provider=AdminAuthProvider(),
)

# your ModelView registrations...
admin.add_view(ModelView(User, icon="fa fa-users"))
admin.add_view(ModelView(Item, icon="fa fa-box"))
admin.add_view(ModelView(Task, icon="fa fa-tasks"))
admin.add_view(ModelView(TaskSubmission, icon="fa fa-file-text"))
admin.add_view(ModelView(UserEarning, icon="fa fa-dollar-sign"))

# add the custom pages as CustomView instances
admin.add_view(BulkTaskImportView(templates))
admin.add_view(FlexibleBulkImportView(templates))

admin.mount_to(app)
