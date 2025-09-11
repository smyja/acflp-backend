#!/usr/bin/env python3
"""
Backward Compatible API Implementation
Supports both old and new language field structures during migration
"""

from typing import Optional
from pydantic import BaseModel, Field, validator
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

# This would be integrated into your existing API files


class BackwardCompatibleLanguageUpdate(BaseModel):
    """Supports both old and new language field formats"""

    # New format (preferred)
    spoken_languages: Optional[str] = Field(None, description="Comma-separated list of spoken languages")

    # Old format (for backward compatibility)
    source_languages: Optional[str] = Field(None, description="Legacy: comma-separated source languages")
    target_languages: Optional[str] = Field(None, description="Legacy: comma-separated target languages")

    @validator("spoken_languages", pre=True, always=True)
    def merge_language_fields(cls, v, values):
        """Merge old format into new format if needed"""
        if v is not None:
            # New format provided, use it
            return v

        # Check if old format is provided
        source = values.get("source_languages")
        target = values.get("target_languages")

        if source or target:
            # Merge old format into spoken_languages
            languages = set()
            if source:
                languages.update(lang.strip() for lang in source.split(",") if lang.strip())
            if target:
                languages.update(lang.strip() for lang in target.split(",") if lang.strip())
            return ",".join(sorted(languages)) if languages else None

        return None

    class Config:
        schema_extra = {
            "examples": [
                {"description": "New format (recommended)", "value": {"spoken_languages": "en,es,bini,yoruba"}},
                {
                    "description": "Old format (backward compatibility)",
                    "value": {"source_languages": "en,es", "target_languages": "bini,yoruba"},
                },
            ]
        }


class BackwardCompatibleUserResponse(BaseModel):
    """User response that includes both old and new formats"""

    id: int
    name: str
    username: str
    email: str
    profile_image_url: str

    # New format
    spoken_languages: Optional[str] = None

    # Old format (for backward compatibility)
    source_languages: Optional[str] = None
    target_languages: Optional[str] = None

    @classmethod
    def from_user_model(cls, user):
        """Create response from user model with backward compatibility"""
        spoken_langs = getattr(user, "spoken_languages", None)

        # For backward compatibility, split spoken_languages into source/target
        source_langs = None
        target_langs = None

        if spoken_langs:
            # Simple split for backward compatibility
            # In production, you might have more sophisticated logic
            langs = [lang.strip() for lang in spoken_langs.split(",") if lang.strip()]
            if langs:
                # Assume first half are source, second half are target
                mid = len(langs) // 2 if len(langs) > 1 else 1
                source_langs = ",".join(langs[:mid])
                target_langs = ",".join(langs[mid:]) if len(langs) > 1 else source_langs

        return cls(
            id=user.id,
            name=user.name,
            username=user.username,
            email=user.email,
            profile_image_url=user.profile_image_url,
            spoken_languages=spoken_langs,
            source_languages=source_langs,
            target_languages=target_langs,
        )


# Example API endpoint with backward compatibility
def create_backward_compatible_endpoints(router: APIRouter):
    """Add backward compatible endpoints to router"""

    @router.patch("/user/me/languages", response_model=BackwardCompatibleUserResponse)
    async def update_user_languages_compatible(
        language_update: BackwardCompatibleLanguageUpdate,
        current_user=Depends(get_current_user),  # Your auth dependency
        db: AsyncSession = Depends(get_db),  # Your DB dependency
    ):
        """Update user languages with backward compatibility"""

        # Update user with new spoken_languages field
        if language_update.spoken_languages:
            current_user.spoken_languages = language_update.spoken_languages

        await db.commit()
        await db.refresh(current_user)

        return BackwardCompatibleUserResponse.from_user_model(current_user)

    @router.patch("/admin/users/{user_id}/languages", response_model=BackwardCompatibleUserResponse)
    async def admin_update_user_languages_compatible(
        user_id: int,
        language_update: BackwardCompatibleLanguageUpdate,
        current_user=Depends(get_current_admin_user),  # Your admin auth dependency
        db: AsyncSession = Depends(get_db),
    ):
        """Admin update user languages with backward compatibility"""

        # Get user
        user = await db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Update user with new spoken_languages field
        if language_update.spoken_languages:
            user.spoken_languages = language_update.spoken_languages

        await db.commit()
        await db.refresh(user)

        return BackwardCompatibleUserResponse.from_user_model(user)


# Feature flag support
import os

USE_SPOKEN_LANGUAGES = os.getenv("USE_SPOKEN_LANGUAGES", "false").lower() == "true"


def get_user_languages_for_task_assignment(user):
    """Get user languages for task assignment with feature flag support"""
    if USE_SPOKEN_LANGUAGES and hasattr(user, "spoken_languages") and user.spoken_languages:
        # New implementation
        return [lang.strip() for lang in user.spoken_languages.split(",") if lang.strip()]
    else:
        # Fallback to old implementation or default
        return ["en"]  # Default fallback


# Migration helper functions
def migrate_user_languages_data(old_source_langs: str, old_target_langs: str) -> str:
    """Helper to migrate old language data to new format"""
    languages = set()

    if old_source_langs:
        languages.update(lang.strip() for lang in old_source_langs.split(",") if lang.strip())

    if old_target_langs:
        languages.update(lang.strip() for lang in old_target_langs.split(",") if lang.strip())

    return ",".join(sorted(languages)) if languages else None


# Example usage in task assignment
def get_next_task_compatible(user, db_session):
    """Task assignment with backward compatibility"""
    user_languages = get_user_languages_for_task_assignment(user)

    if USE_SPOKEN_LANGUAGES and user_languages:
        # New logic: filter by spoken languages
        query = db_session.query(Task).filter(Task.status == "pending", Task.source_language.in_(user_languages))
    else:
        # Old logic: return any available task
        query = db_session.query(Task).filter(Task.status == "pending")

    return query.first()
