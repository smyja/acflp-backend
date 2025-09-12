import asyncio
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.db.database import local_session
from src.app.models.language import Language

DEFAULT_LANGUAGES: list[str] = [
    # Core
    "english",
    "yoruba",
    "igbo",
    "hausa",
    "bini",
    "swahili",
    "amharic",
    "zulu",
    "xhosa",
    "shona",
    "urhobo",
    "twi",
    "fula",
    "somali",
    # Regionally common lingua francas
    "arabic",
    "french",
    "portuguese",
]


def _norm(name: str | None) -> str | None:
    if not name:
        return None
    return name.strip().lower()


async def _ensure_languages(session: AsyncSession, names: Iterable[str]) -> int:
    count = 0
    for raw in names:
        name = _norm(raw)
        if not name:
            continue
        result = await session.execute(select(Language).where(Language.name == name))
        exists = result.scalar_one_or_none()
        if not exists:
            session.add(Language(name=name))
            count += 1
    if count:
        await session.commit()
    return count


async def _cleanup_numeric_names(session: AsyncSession) -> int:
    """Remove accidental numeric language names like "1".

    This should not be common, but can happen if an admin accidentally posts
    numeric values. Safe to run, idempotent.
    """
    removed = 0
    result = await session.execute(select(Language))
    for lang in result.scalars():
        if lang.name.isdigit():
            await session.delete(lang)
            removed += 1
    if removed:
        await session.commit()
    return removed


async def main() -> None:
    async with local_session() as session:
        removed = await _cleanup_numeric_names(session)
        added = await _ensure_languages(session, DEFAULT_LANGUAGES)
        print(f"Removed numeric placeholders: {removed}")
        print(f"Added languages: {added}")


if __name__ == "__main__":
    asyncio.run(main())
