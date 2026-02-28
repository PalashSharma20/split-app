"""Add already_added to SplitType enum

Revision ID: 0004
Revises: 0003
Create Date: 2026-02-28
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

OLD_SPLIT_TYPE = sa.Enum(
    "equal", "full_you", "full_other", "percent", "exact", "personal",
    name="splittype",
)
NEW_SPLIT_TYPE = sa.Enum(
    "equal", "full_you", "full_other", "percent", "exact", "personal", "already_added",
    name="splittype",
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE splittype ADD VALUE IF NOT EXISTS 'already_added'")
    else:
        with op.batch_alter_table("split_history") as batch_op:
            batch_op.alter_column("split_type", type_=NEW_SPLIT_TYPE, existing_type=OLD_SPLIT_TYPE)


def downgrade() -> None:
    # Postgres does not support removing enum values; downgrade is a no-op for the enum.
    pass
