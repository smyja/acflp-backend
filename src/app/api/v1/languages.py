from typing import List, Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.db.database import async_get_db
from ...schemas.language import LanguageRead, UserLanguageUpdate
from ...models.user import User
from ...models.language import Language
from ..dependencies import get_current_user, get_current_superuser

router = APIRouter()


@router.get("/", response_model=List[LanguageRead])
async def get_languages(db: Annotated[AsyncSession, Depends(async_get_db)]):
    """Get all available languages."""
    result = await db.execute(select(Language))
    return result.scalars().all()


@router.patch("/me", response_model=dict)
async def update_my_languages(
    language_update: UserLanguageUpdate,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
):
    """Update current user's language preferences by language names."""
    user = await db.get(User, current_user["id"])  # type: ignore[index]
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Resolve or create languages, then replace association list
    resolved: list[Language] = []
    for name in language_update.language_names:
        result = await db.execute(select(Language).where(Language.name == name))
        lang = result.scalar_one_or_none()
        if not lang:
            lang = Language(name=name)
            db.add(lang)
            # Flush to ensure PK persistence before association
            await db.flush()
        resolved.append(lang)

    # Replace associations
    user.languages.clear()
    for lang in resolved:
        user.languages.append(lang)

    await db.commit()
    await db.refresh(user)

    return {
        "message": "Languages updated successfully",
        "languages": [lang.name for lang in user.languages],
    }


