from datetime import UTC, datetime
import uuid as uuid_pkg

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db.database import Base


class Task(Base):
    __tablename__ = "task"

    id: Mapped[int] = mapped_column("id", autoincrement=True, nullable=False, unique=True, primary_key=True, init=False)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    text: Mapped[str] = mapped_column(String(63206))
    source_language: Mapped[str] = mapped_column(String(50))
    task_type: Mapped[str] = mapped_column(String(50))
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), default=None, index=True)
    translated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), default=None, index=True)
    target_language: Mapped[str | None] = mapped_column(String(50), default=None)
    translated_text: Mapped[str | None] = mapped_column(String(63206), default=None)
    uuid: Mapped[uuid_pkg.UUID] = mapped_column(default_factory=uuid_pkg.uuid4, primary_key=True, unique=True)
    media_url: Mapped[str | None] = mapped_column(String, default=None)
    status: Mapped[str] = mapped_column(String(50), default="pending")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default_factory=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    translated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    is_deleted: Mapped[bool] = mapped_column(default=False, index=True)
