import asyncio
import sys

from sqlalchemy import update

from src.app.core.db.database import local_session
from src.app.models.language import Language
from src.app.models.task import Task
from src.app.models.user import user_languages


def _norm(name: str | None) -> str | None:
    if name is None:
        return None
    return name.strip().lower() or None


async def rename_language(old_name: str, new_name: str) -> None:
    old = _norm(old_name)
    new = _norm(new_name)
    if not old or not new or old == new:
        print("Invalid names. Provide two different non-empty names.")
        return

    async with local_session() as session:  # type: AsyncSession
        # Ensure the destination language exists
        dest = await session.get(Language, new)
        if not dest:
            session.add(Language(name=new))
            await session.flush()

        src = await session.get(Language, old)
        if not src:
            print(f"Language '{old}' not found")
            await session.rollback()
            return

        # Rewire associations in the join table (by id now)
        await session.execute(
            update(user_languages).where(user_languages.c.language_id == src.id).values(language_id=dest.id)
        )

        # Update tasks that reference the old language value
        await session.execute(update(Task).where(Task.target_language == old).values(target_language=new))
        await session.execute(update(Task).where(Task.source_language == old).values(source_language=new))

        # Remove the old language row (no children reference it now)
        await session.delete(src)
        await session.commit()

        print(f"Renamed language '{old}' -> '{new}'")


async def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python -m src.scripts.rename_language <old_name> <new_name>")
        return
    await rename_language(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    asyncio.run(main())
