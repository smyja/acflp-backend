from typing import Annotated, List

from crudadmin import CRUDAdmin
from crudadmin.admin_interface.model_view import PasswordTransformer
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.security import get_password_hash
from ..crud import language as crud_language
from ..models.language import Language
from ..models.task import Task
from ..models.user import User
from ..schemas.language import LanguageCreate, LanguageRead
from ..schemas.task import TaskUpdate
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


class UserUpdateAdmin(BaseModel):
    """Admin-specific schema for updating users with new language system."""
    name: Annotated[str | None, Field(min_length=2, max_length=30, examples=["User Userberg"], default=None)]
    username: Annotated[
        str | None,
        Field(
            min_length=2,
            max_length=20,
            pattern=r"^[a-z0-9][a-z0-9_-]*$",
            examples=["userberg"],
            default=None,
        ),
    ]
    email: Annotated[EmailStr | None, Field(examples=["user.userberg@example.com"], default=None)]
    profile_image_url: Annotated[
        str | None,
        Field(
            pattern=r"^(https?|ftp)://[^\s/$.?#].[^\s]*$", examples=["https://www.profileimageurl.com"], default=None
        ),
    ]
    language_names: Annotated[List[str] | None, Field(examples=[["English", "Yoruba", "Igbo"]], default=None)]


async def custom_user_update_handler(db: AsyncSession, user: User, update_data: UserUpdateAdmin) -> User:
    """Custom handler for updating users with language relationships."""
    # Update basic user fields
    if update_data.name is not None:
        user.name = update_data.name
    if update_data.username is not None:
        user.username = update_data.username
    if update_data.email is not None:
        user.email = update_data.email
    if update_data.profile_image_url is not None:
        user.profile_image_url = update_data.profile_image_url
    
    # Handle language relationships
    if update_data.language_names is not None:
        await crud_language.update_user_languages(
            db=db,
            user=user,
            language_names=update_data.language_names,
        )
    
    return user


def register_admin_views(admin: CRUDAdmin) -> None:
    """Register all models and their schemas with the admin interface.

    This function adds all available models to the admin interface with appropriate
    schemas and permissions.
    """
    # Define field names as constants to avoid hardcoded strings
    password_field = "password"  # noqa: S105

    password_transformer = PasswordTransformer(
        password_field=password_field,
        hashed_field="hashed_password",
        hash_function=get_password_hash,
        required_fields=["name", "username", "email"],
    )

    admin.add_view(
        model=User,
        create_schema=UserCreate,
        update_schema=UserUpdate,  # Use standard update schema compatible with FastCRUD
        allowed_actions={"view", "create", "update"},
        password_transformer=password_transformer,
    )

    admin.add_view(
        model=Task,
        create_schema=TaskCreateAdmin,
        update_schema=TaskUpdate,
        allowed_actions={"view", "create", "update", "delete"},
    )

    admin.add_view(
        model=Language,
        create_schema=LanguageCreate,
        update_schema=LanguageCreate,  # Same as create since only name field
        allowed_actions={"view", "create", "update", "delete"},
    )
