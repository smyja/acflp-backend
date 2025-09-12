import asyncio
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.db.database import local_session


def column_exists(conn: sa.engine.Connection, table: str, column: str) -> bool:
    insp = sa.inspect(conn)
    cols = {c["name"] for c in insp.get_columns(table)}
    return column in cols


def table_exists(conn: sa.engine.Connection, table: str) -> bool:
    insp = sa.inspect(conn)
    return table in insp.get_table_names()


def fk_name(conn: sa.engine.Connection, table: str, column: str) -> Optional[str]:
    insp = sa.inspect(conn)
    for fk in insp.get_foreign_keys(table):
        if column in fk.get("constrained_columns", []):
            return fk.get("name")
    return None


def pk_name(conn: sa.engine.Connection, table: str) -> Optional[str]:
    insp = sa.inspect(conn)
    pk = insp.get_pk_constraint(table)
    return pk.get("name") if pk else None


def has_constraint(conn: sa.engine.Connection, table: str, name: str) -> bool:
    insp = sa.inspect(conn)
    # PK name
    pk = insp.get_pk_constraint(table)
    if pk and pk.get("name") == name:
        return True
    # uniques
    for uc in insp.get_unique_constraints(table):
        if uc.get("name") == name:
            return True
    # fks
    for fk in insp.get_foreign_keys(table):
        if fk.get("name") == name:
            return True
    # indexes not covered; we only care about named constraints
    return False


def pk_columns(conn: sa.engine.Connection, table: str) -> list[str]:
    insp = sa.inspect(conn)
    pk = insp.get_pk_constraint(table)
    return list(pk.get("constrained_columns") or [])


async def migrate() -> None:
    async with local_session() as session:  # type: AsyncSession
        async with session.bind.begin() as async_conn:
            def sync_migrate(conn: sa.engine.Connection) -> None:
                # 1) Ensure languages table has id column populated and unique
                if table_exists(conn, "languages"):
                    has_id = column_exists(conn, "languages", "id")
                    if not has_id:
                        # Add id column with sequence/default and populate
                        conn.execute(text("ALTER TABLE languages ADD COLUMN id INTEGER"))
                        conn.execute(text("CREATE SEQUENCE IF NOT EXISTS languages_id_seq OWNED BY languages.id"))
                        conn.execute(text("ALTER TABLE languages ALTER COLUMN id SET DEFAULT nextval('languages_id_seq')"))
                        conn.execute(text("UPDATE languages SET id = nextval('languages_id_seq') WHERE id IS NULL"))
                    # Make id not null (safe if already set)
                    conn.execute(text("ALTER TABLE languages ALTER COLUMN id SET NOT NULL"))
                    # Ensure id is unique so it can be FK target before PK switch
                    if not has_constraint(conn, "languages", "languages_id_key"):
                        conn.execute(text("ALTER TABLE languages ADD CONSTRAINT languages_id_key UNIQUE (id)"))
                    # Ensure name is unique
                    if not has_constraint(conn, "languages", "languages_name_key"):
                        conn.execute(text("ALTER TABLE languages ADD CONSTRAINT languages_name_key UNIQUE (name)"))

                # 2) Update user_languages join to use language_id instead of language_name
                if table_exists(conn, "user_languages"):
                    if column_exists(conn, "user_languages", "language_name") and not column_exists(
                        conn, "user_languages", "language_id"
                    ):
                        # Add new column
                        conn.execute(text("ALTER TABLE user_languages ADD COLUMN language_id INTEGER"))
                        # Fill from languages by name
                        conn.execute(
                            text(
                                """
                                UPDATE user_languages ul
                                SET language_id = l.id
                                FROM languages l
                                WHERE ul.language_name = l.name
                                """
                            )
                        )
                        # Add new FK (languages.id is unique at this point)
                        conn.execute(
                            text(
                                "ALTER TABLE user_languages ADD CONSTRAINT user_languages_language_id_fkey "
                                "FOREIGN KEY (language_id) REFERENCES languages(id) ON DELETE CASCADE"
                            )
                        )
                        # Drop old FK if present
                        fk = fk_name(conn, "user_languages", "language_name")
                        if fk:
                            conn.execute(text(f"ALTER TABLE user_languages DROP CONSTRAINT {fk}"))
                        # Drop old PK, set new composite PK
                        pk_ul = pk_name(conn, "user_languages")
                        if pk_ul:
                            conn.execute(text(f"ALTER TABLE user_languages DROP CONSTRAINT {pk_ul}"))
                        conn.execute(
                            text(
                                "ALTER TABLE user_languages ADD CONSTRAINT user_languages_pkey "
                                "PRIMARY KEY (user_id, language_id)"
                            )
                        )
                        # Drop old column
                        conn.execute(text("ALTER TABLE user_languages DROP COLUMN language_name"))

                # 3) Switch languages primary key from name to id (after dependents updated)
                if table_exists(conn, "languages"):
                    # Only switch PK if not already on id
                    if pk_columns(conn, "languages") != ["id"]:
                        pk_lang = pk_name(conn, "languages")
                        if pk_lang:
                            conn.execute(text(f"ALTER TABLE languages DROP CONSTRAINT {pk_lang}"))
                        conn.execute(text("ALTER TABLE languages ADD CONSTRAINT languages_pkey PRIMARY KEY (id)"))
                    # Keep languages_id_key to avoid breaking existing FKs created earlier

            await async_conn.run_sync(sync_migrate)

    print("Language PK migration completed (id primary key, join updated).")


if __name__ == "__main__":
    asyncio.run(migrate())
