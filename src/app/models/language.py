from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.db.database import Base


class Language(Base):
    __tablename__ = "languages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    users = relationship("User", secondary="user_languages", back_populates="languages")
