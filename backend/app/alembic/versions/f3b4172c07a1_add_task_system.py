"""Add task system

Revision ID: f3b4172c07a1
Revises: 1a31ce608336
Create Date: 2025-08-11 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "f3b4172c07a1"
down_revision = "1a31ce608336"
branch_labels = None
depends_on = None


def upgrade():
    # Add total_earnings to user
    op.add_column(
        "user",
        sa.Column(
            "total_earnings",
            sa.Numeric(10, 2),
            nullable=False,
            server_default=sa.text("0.00"),
        ),
    )

    # task table - using VARCHAR for enum fields to avoid PostgreSQL enum creation
    op.create_table(
        "task",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("created_by_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("task_type", sa.String(length=50), nullable=False),
        sa.Column("source_language", sa.String(length=50), nullable=False),
        sa.Column("target_language", sa.String(length=50), nullable=True),
        sa.Column("content", sa.String(length=5000), nullable=False),
        sa.Column(
            "reward_amount",
            sa.Numeric(10, 2),
            nullable=False,
            server_default=sa.text("0.00"),
        ),
        sa.Column(
            "max_submissions", sa.Integer(), nullable=False, server_default=sa.text("1")
        ),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # tasksubmission table
    op.create_table(
        "tasksubmission",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("task_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("reviewer_id", sa.UUID(), nullable=True),
        sa.Column("reviewer_notes", sa.String(length=1000), nullable=True),
        sa.Column("content", sa.String(length=5000), nullable=True),
        sa.Column("audio_file_url", sa.String(length=500), nullable=True),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["task.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_id"],
            ["user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # userearning table
    op.create_table(
        "userearning",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("submission_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
        ),
        sa.ForeignKeyConstraint(
            ["submission_id"],
            ["tasksubmission.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    bind = op.get_bind()

    # Drop tables in reverse order of dependencies
    op.drop_table("userearning")
    op.drop_table("tasksubmission")
    op.drop_table("task")

    # Remove added column
    op.drop_column("user", "total_earnings")

    # No enum types were created in this migration
