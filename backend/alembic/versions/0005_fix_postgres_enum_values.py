"""Ensure personal and already_added exist in the Postgres splittype enum

These values were added in 0003/0004 using batch_alter_table, which works
for SQLite but does not execute ALTER TYPE on Postgres. This migration
idempotently adds the missing values on Postgres databases.

Revision ID: 0005
Revises: 0004
Create Date: 2026-02-28
"""
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE splittype ADD VALUE IF NOT EXISTS 'personal'")
        op.execute("ALTER TYPE splittype ADD VALUE IF NOT EXISTS 'already_added'")


def downgrade() -> None:
    # Postgres does not support removing enum values.
    pass
