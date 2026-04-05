"""Replace checkpoint_date cutoff with checkpoint_transaction_id

Using a transaction ID instead of a date avoids the edge case where
transactions on the checkpoint date get excluded from future balance
computations (e.g. checkpoint on April 2 → new April 2 transactions missed).

checkpoint_date is kept for display purposes only.

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("balance_checkpoints") as batch_op:
        batch_op.add_column(sa.Column("checkpoint_transaction_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("balance_checkpoints") as batch_op:
        batch_op.drop_column("checkpoint_transaction_id")
