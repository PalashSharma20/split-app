"""Add card_member/account_number to transactions; add personal to SplitType

Revision ID: 0003
Revises: 0002
Create Date: 2026-02-28
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

NEW_SPLIT_TYPE = sa.Enum(
    "equal", "full_you", "full_other", "percent", "exact", "personal",
    name="splittype",
)
OLD_SPLIT_TYPE = sa.Enum(
    "equal", "full_you", "full_other", "percent", "exact",
    name="splittype",
)


def upgrade() -> None:
    # Add card_member and account_number to transactions
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.add_column(sa.Column("card_member", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("account_number", sa.String(), nullable=True))

    # Add "personal" to the enum.
    # Postgres requires ALTER TYPE; SQLite stores enums as strings so no DDL needed.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE splittype ADD VALUE IF NOT EXISTS 'personal'")
    else:
        with op.batch_alter_table("split_history") as batch_op:
            batch_op.alter_column("split_type", type_=NEW_SPLIT_TYPE, existing_type=OLD_SPLIT_TYPE)


def downgrade() -> None:
    # NOTE: Postgres does not support removing enum values; downgrade is a no-op for the enum.
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.drop_column("account_number")
        batch_op.drop_column("card_member")
