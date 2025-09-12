"""Drop spoken_languages column from user

Revision ID: de01e0f3b2a6
Revises: f3a4b0f9e1cd
Create Date: 2025-09-11 23:30:00

"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "de01e0f3b2a6"
down_revision: Union[str, None] = "1f3ce3e9fffd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if "user" in inspector.get_table_names():
        op.execute('ALTER TABLE "user" DROP COLUMN IF EXISTS spoken_languages')


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if "user" in inspector.get_table_names():
        op.execute('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS spoken_languages VARCHAR NULL')
