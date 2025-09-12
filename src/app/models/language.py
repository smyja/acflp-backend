from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.db.database import Base


class Language(Base):
    __tablename__ = "languages"

    name: Mapped[str] = mapped_column(String(255), primary_key=True, index=True)
    users = relationship("User", secondary="user_languages", back_populates="languages")