from typing import Annotated

from crudadmin import CRUDAdmin
from crudadmin.admin_interface.model_view import PasswordTransformer
from pydantic import BaseModel, Field

from ..core.security import get_password_hash
from ..models.task import Task
from ..models.tier import Tier
from ..models.user import User
from ..schemas.task import TaskUpdate
from ..schemas.tier import TierCreate, TierUpdate
from ..schemas.user import UserCreate, UserUpdate


class TaskCreateAdmin(BaseModel):
    title: Annotated[str, Field(min_length=2, max_length=255, examples=["This is my task"])]
    text: Annotated[str, Field(min_length=1, max_length=63206, examples=["This is the content of my task."])]
    created_by_user_id: int
    media_url: Annotated[
        str | None,
        Field(pattern=r"^(https?|ftp)://[^\s/$.?#].[^\s]*$", examples=["https://www.taskimageurl.com"], default=None),
    ]
    source_language: Annotated[str, Field(max_length=50, examples=["en"])]
    target_language: Annotated[str | None, Field(max_length=50, examples=["es"], default=None)]
    task_type: Annotated[str, Field(max_length=50, examples=["text_translation"])]
    status: Annotated[str, Field(max_length=50, examples=["pending"], default="pending")]


def register_admin_views(admin: CRUDAdmin) -> None:
    """Register all models and their schemas with the admin interface.

    This function adds all available models to the admin interface with appropriate
    schemas and permissions.
    """

    password_transformer = PasswordTransformer(
        password_field="password",
        hashed_field="hashed_password",
        hash_function=get_password_hash,
        required_fields=["name", "username", "email"],
    )

    admin.add_view(
        model=User,
        create_schema=UserCreate,
        update_schema=UserUpdate,
        allowed_actions={"view", "create", "update"},
        password_transformer=password_transformer,
    )

    admin.add_view(
        model=Tier,
        create_schema=TierCreate,
        update_schema=TierUpdate,
        allowed_actions={"view", "create", "update", "delete"},
    )

    admin.add_view(
        model=Task,
        create_schema=TaskCreateAdmin,
        update_schema=TaskUpdate,
        allowed_actions={"view", "create", "update", "delete"},
    )
