"""Add balance_checkpoints table

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-03
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "balance_checkpoints",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("checkpoint_date", sa.Date(), nullable=False),
        sa.Column("label", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("balance_checkpoints")
