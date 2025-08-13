import uuid
from datetime import datetime
from enum import Enum
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from pydantic import EmailStr
from sqlmodel import Field, Relationship, SQLModel, Column, DECIMAL


# Common field definitions to reduce duplication
def decimal_field(default_value: str = "0.00") -> Field:
    """Standard decimal field for monetary amounts"""
    return Field(sa_column=Column(DECIMAL(10, 2)), default=Decimal(default_value))


def status_field(default_status: str = "pending") -> Field:
    """Standard status field with VARCHAR column"""
    return Field(
        sa_column=Column("status", sa.String(50), nullable=False, server_default=default_status),
        default=default_status
    )


def language_field(column_name: str, nullable: bool = False, default_value=None):
    """Standard language field with VARCHAR column"""
    if nullable:
        return Field(
            sa_column=Column(column_name, sa.String(50), nullable=True),
            default=default_value
        )
    else:
        return Field(sa_column=Column(column_name, sa.String(50), nullable=False))


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=40)


# UserRegister inherits from UserCreate to reduce duplication
class UserRegister(UserCreate):
    pass


# Properties to receive via API on update, all are optional
class UserUpdate(UserBase):
    email: EmailStr | None = Field(default=None, max_length=255)  # type: ignore
    password: str | None = Field(default=None, min_length=8, max_length=40)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=40)
    new_password: str = Field(min_length=8, max_length=40)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    total_earnings: Decimal = decimal_field()
    items: list["Item"] = Relationship(back_populates="owner", cascade_delete=True)
    created_tasks: list["Task"] = Relationship(
        back_populates="created_by",
        cascade_delete=True,
    )
    task_submissions: list["TaskSubmission"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={
            "foreign_keys": "[TaskSubmission.user_id]",
        },
        cascade_delete=True,
    )
    earnings: list["UserEarning"] = Relationship(cascade_delete=True)


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


# Shared properties
class ItemBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Properties to receive on item creation
class ItemCreate(ItemBase):
    pass


# Properties to receive on item update
class ItemUpdate(ItemBase):
    title: str | None = Field(default=None, min_length=1, max_length=255)  # type: ignore


# Database model, database table inferred from class name
class Item(ItemBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    owner: User | None = Relationship(back_populates="items")


# Properties to return via API, id is always required
class ItemPublic(ItemBase):
    id: uuid.UUID
    owner_id: uuid.UUID


class ItemsPublic(SQLModel):
    data: list[ItemPublic]
    count: int


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=40)


# Task System Models
class TaskType(str, Enum):
    TEXT_TRANSLATION = "text_translation"
    TTS_RECORDING = "tts_recording"


class Language(str, Enum):
    BINI = "bini"
    URHOBO = "urhobo"
    IGBO = "igbo"
    CALABAR = "calabar"


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REJECTED = "rejected"


class SubmissionStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


# Task Base Models
class TaskBase(SQLModel):
    title: str = Field(max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    task_type: str
    source_language: str
    target_language: str | None = Field(default=None)  # For translation tasks
    content: str = Field(max_length=5000)  # Text to translate or TTS script
    reward_amount: Decimal = decimal_field()
    status: str = Field(default="pending")


class TaskCreate(TaskBase):
    pass


class TaskUpdate(SQLModel):
    title: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    content: str | None = Field(default=None, max_length=5000)
    reward_amount: Decimal | None = None
    status: str | None = Field(default=None)


# Database model for Task
class Task(TaskBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: uuid.UUID = Field(foreign_key="user.id", nullable=False)
    
    # Override enum fields to use VARCHAR to prevent PostgreSQL enum creation
    task_type: str = Field(sa_column=Column("task_type", sa.String(50), nullable=False))
    source_language: str = language_field("source_language")
    target_language: str | None = language_field("target_language", nullable=True, default_value=None)
    status: str = status_field()

    # Relationships
    created_by: User | None = Relationship(
        back_populates="created_tasks",
        sa_relationship_kwargs={
            "foreign_keys": "[Task.created_by_id]",
        },
    )
    submissions: list["TaskSubmission"] = Relationship(
        back_populates="task", cascade_delete=True
    )


class TaskPublic(TaskBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    created_by_id: uuid.UUID
    submission_count: int = 0


class TasksPublic(SQLModel):
    data: list[TaskPublic]
    count: int


# Task Submission Models
class TaskSubmissionBase(SQLModel):
    content: str | None = Field(default=None, max_length=5000)  # Translation text
    audio_file_url: str | None = Field(
        default=None, max_length=500
    )  # TTS recording URL
    notes: str | None = Field(default=None, max_length=1000)
    status: str = Field(default="pending")


class TaskSubmissionCreate(TaskSubmissionBase):
    task_id: uuid.UUID


class TaskSubmissionUpdate(SQLModel):
    content: str | None = Field(default=None, max_length=5000)
    audio_file_url: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=1000)
    status: str | None = Field(default=None)
    reviewer_notes: str | None = Field(default=None, max_length=1000)


# Database model for TaskSubmission
class TaskSubmission(TaskSubmissionBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    task_id: uuid.UUID = Field(foreign_key="task.id", nullable=False)
    user_id: uuid.UUID = Field(foreign_key="user.id", nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    reviewed_at: datetime | None = Field(default=None)
    reviewer_id: uuid.UUID | None = Field(foreign_key="user.id", nullable=True)
    reviewer_notes: str | None = Field(default=None, max_length=1000)
    
    # Override enum field to use VARCHAR to prevent PostgreSQL enum creation
    status: str = status_field()

    # Relationships
    task: Task | None = Relationship(back_populates="submissions")
    user: User | None = Relationship(
        back_populates="task_submissions",
        sa_relationship_kwargs={
            "foreign_keys": "[TaskSubmission.user_id]",
        },
    )
    reviewer: User | None = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[TaskSubmission.reviewer_id]",
        },
    )
    earnings: list["UserEarning"] = Relationship(
        back_populates="submission", cascade_delete=True
    )


class TaskSubmissionPublic(TaskSubmissionBase):
    id: uuid.UUID
    task_id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    reviewed_at: datetime | None
    reviewer_id: uuid.UUID | None
    reviewer_notes: str | None


class TaskSubmissionsPublic(SQLModel):
    data: list[TaskSubmissionPublic]
    count: int


# User Earnings Models
class UserEarningBase(SQLModel):
    amount: Decimal = Field(sa_column=Column(DECIMAL(10, 2)))
    description: str = Field(max_length=255)


class UserEarningCreate(UserEarningBase):
    user_id: uuid.UUID
    submission_id: uuid.UUID


# Database model for UserEarning
class UserEarning(UserEarningBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", nullable=False)
    submission_id: uuid.UUID = Field(foreign_key="tasksubmission.id", nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    user: User | None = Relationship()
    submission: TaskSubmission | None = Relationship(back_populates="earnings")


class UserEarningPublic(UserEarningBase):
    id: uuid.UUID
    user_id: uuid.UUID
    submission_id: uuid.UUID
    created_at: datetime


class UserEarningsPublic(SQLModel):
    data: list[UserEarningPublic]
    count: int
    total_earnings: Decimal


# User Statistics
class UserStats(SQLModel):
    total_earnings: Decimal
    total_submissions: int
    approved_submissions: int
    pending_submissions: int
    rejected_submissions: int


# Bulk Task Import Models - REMOVED (using flexible import only)


class FlexibleBulkImportRequest(SQLModel):
    """Request model for flexible JSONL import with field mapping"""
    field_mappings: dict[str, str] = Field(
        description="Map JSONL keys to task fields. Required: content_field. Optional: title_field, description_field, source_language_field, target_language_field, task_type_field, reward_amount_field"
    )
    default_values: dict[str, Any] = Field(
        default_factory=dict,
        description="Default values for missing fields"
    )
    raw_data: list[dict[str, Any]] = Field(
        description="Raw JSONL data as list of dictionaries"
    )


class FlexibleBulkImportResponse(SQLModel):
    """Response model for flexible bulk import"""
    success_count: int
    error_count: int
    total_count: int
    errors: list[str] = Field(default_factory=list)
    created_task_ids: list[uuid.UUID] = Field(default_factory=list)
    message: str
    sample_processed_data: list[dict[str, Any]] = Field(default_factory=list, description="First 3 processed items for verification")
