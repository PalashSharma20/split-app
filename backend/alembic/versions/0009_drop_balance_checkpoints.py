"""Drop balance_checkpoints table

Revision ID: 0009
Revises: 0008
Create Date: 2026-04-05
"""
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("balance_checkpoints")


def downgrade() -> None:
    import sqlalchemy as sa
    op.create_table(
        "balance_checkpoints",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("checkpoint_date", sa.Date(), nullable=False),
        sa.Column("checkpoint_transaction_id", sa.Integer(), nullable=True),
        sa.Column("label", sa.String(), nullable=True),
    )
