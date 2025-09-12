from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.language import Language
from ..models.user import User
from ..schemas.language import LanguageCreate


class CRUDLanguage:
    async def get_all(self, db: AsyncSession) -> List[Language]:
        """Get all available languages."""
        result = await db.execute(select(Language))
        return result.scalars().all()

    async def get_by_name(self, db: AsyncSession, name: str) -> Language | None:
        """Get a language by name."""
        result = await db.execute(select(Language).where(Language.name == name))
        return result.scalar_one_or_none()

    async def create(self, db: AsyncSession, obj_in: LanguageCreate) -> Language:
        """Create a new language."""
        db_obj = Language(name=obj_in.name)
        db.add(db_obj)
        await db.flush()
        return db_obj

    async def get_or_create(self, db: AsyncSession, name: str) -> Language:
        """Get a language by name or create it if it doesn't exist."""
        language = await self.get_by_name(db, name)
        if not language:
            language = await self.create(db, LanguageCreate(name=name))
        return language

    async def update_user_languages(self, db: AsyncSession, user: User, language_names: List[str]) -> User:
        """Update a user's languages."""
        # Clear existing languages
        user.languages.clear()

        # Add new languages
        for name in language_names:
            language = await self.get_or_create(db, name)
            user.languages.append(language)

        await db.commit()
        await db.refresh(user)
        return user


language = CRUDLanguage()
