from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from sqlalchemy.exc import IntegrityError

from .admin.initialize import create_admin_interface
from .api import router
from .core.config import settings
from .core.setup import create_application, lifespan_factory

admin = create_admin_interface()


@asynccontextmanager
async def lifespan_with_admin(app: FastAPI) -> AsyncGenerator[None, None]:
    """Custom lifespan that includes admin initialization."""
    # Get the default lifespan
    default_lifespan = lifespan_factory(settings)

    # Run the default lifespan initialization and our admin initialization
    async with default_lifespan(app):
        # Initialize admin interface if it exists
        if admin:
            # Initialize admin database and setup
            try:
                await admin.initialize()
            except IntegrityError as e:
                # If initial admin already exists, ignore and continue startup
                msg = str(e).lower()
                if ("unique" in msg or "duplicate key" in msg) and "admin_user" in msg:
                    logging.getLogger(__name__).info("Admin user already exists; continuing startup")
                else:
                    raise
            except Exception as e:  # Fallbacks for concurrency and cross-driver differences
                msg = str(e).lower()
                # 1) Ignore duplicate admin user creation
                if ("unique" in msg or "duplicate" in msg) and "admin_user" in msg:
                    logging.getLogger(__name__).info("Admin user already exists; continuing startup")
                    
                # 2) Ignore benign races where admin tables were created by another worker
                elif "already exists" in msg and "admin_" in msg:
                    logging.getLogger(__name__).info("Admin tables already exist; continuing startup")
                else:
                    raise

        yield


app = create_application(router=router, settings=settings, lifespan=lifespan_with_admin)

# Mount admin interface if enabled
if admin:
    app.mount(settings.CRUD_ADMIN_MOUNT_PATH, admin.app)
