from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from ..core.schemas import PersistentDeletion, TimestampSchema, UUIDSchema


class TaskBase(BaseModel):
    title: Annotated[str, Field(min_length=2, max_length=255, examples=["This is my task"])]
    text: Annotated[str, Field(min_length=1, max_length=63206, examples=["This is the content of my task."])]
    source_language: Annotated[str, Field(max_length=50, examples=["en"])]
    target_language: Annotated[str | None, Field(max_length=50, examples=["es"], default=None)]
    task_type: Annotated[str, Field(max_length=50, examples=["text_translation"])]
    status: Annotated[str, Field(max_length=50, examples=["pending"], default="pending")]


class Task(TimestampSchema, TaskBase, UUIDSchema, PersistentDeletion):
    media_url: Annotated[
        str | None,
        Field(pattern=r"^(https?|ftp)://[^\s/$.?#].[^\s]*$", examples=["https://www.taskimageurl.com"], default=None),
    ]
    created_by_user_id: int


class TaskRead(BaseModel):
    id: int
    title: Annotated[str, Field(min_length=2, max_length=255, examples=["This is my task"])]
    text: Annotated[str, Field(min_length=1, max_length=63206, examples=["This is the content of my task."])]
    media_url: Annotated[
        str | None,
        Field(examples=["https://www.taskimageurl.com"], default=None),
    ]
    created_by_user_id: int
    assignee_id: int | None
    translated_by_user_id: int | None
    created_at: datetime
    source_language: str
    target_language: str | None
    task_type: str
    status: str
    translated_text: str | None
    translated_at: datetime | None


class TaskCreate(TaskBase):
    model_config = ConfigDict(extra="forbid")

    media_url: Annotated[
        str | None,
        Field(pattern=r"^(https?|ftp)://[^\s/$.?#].[^\s]*$", examples=["https://www.taskimageurl.com"], default=None),
    ]


class TaskCreateInternal(TaskCreate):
    created_by_user_id: int


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Annotated[
        str | None, Field(min_length=2, max_length=255, examples=["This is my updated task"], default=None)
    ]
    text: Annotated[
        str | None,
        Field(min_length=1, max_length=63206, examples=["This is the updated content of my task."], default=None),
    ]
    media_url: Annotated[
        str | None,
        Field(pattern=r"^(https?|ftp)://[^\s/$.?#].[^\s]*$", examples=["https://www.taskimageurl.com"], default=None),
    ]
    source_language: Annotated[str | None, Field(max_length=50, examples=["en"], default=None)]
    target_language: Annotated[str | None, Field(max_length=50, examples=["es"], default=None)]
    task_type: Annotated[str | None, Field(max_length=50, examples=["text_translation"], default=None)]
    status: Annotated[str | None, Field(max_length=50, examples=["in_progress"], default=None)]
    assignee_id: Annotated[int | None, Field(examples=[1], default=None)]
    translated_text: Annotated[
        str | None, Field(min_length=1, max_length=63206, examples=["This is the translated content."], default=None)
    ]
    translated_by_user_id: Annotated[int | None, Field(examples=[1], default=None)]
    translated_at: Annotated[datetime | None, Field(examples=["2023-01-01T00:00:00Z"], default=None)]


class TaskUpdateInternal(TaskUpdate):
    updated_at: datetime


class TaskTranslationCreate(BaseModel):
    translated_text: Annotated[
        str, Field(min_length=1, max_length=63206, examples=["This is the translated content of my task."])
    ]


class TaskDelete(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_deleted: bool
    deleted_at: datetime
