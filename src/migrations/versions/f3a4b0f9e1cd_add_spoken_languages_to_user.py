"""Add spoken_languages column to user

Revision ID: f3a4b0f9e1cd
Revises: 77c60bc1491d
Create Date: 2025-09-11 22:40:00

"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "f3a4b0f9e1cd"
down_revision: Union[str, None] = "77c60bc1491d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    # Only operate if the user table exists
    if "user" in inspector.get_table_names():
        # Check if the column already exists to avoid errors during repeated runs
        existing_cols = {col["name"] for col in inspector.get_columns("user")}
        if "spoken_languages" not in existing_cols:
            # Use IF NOT EXISTS for extra safety across environments
            op.execute('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS spoken_languages VARCHAR NULL')


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    if "user" in inspector.get_table_names():
        # Drop column if it exists
        op.execute('ALTER TABLE "user" DROP COLUMN IF EXISTS spoken_languages')

