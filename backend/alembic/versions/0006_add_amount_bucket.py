"""Add amount_bucket to split_history; backfill from transactions

Buckets: xs (<15), sm (15-75), md (75-250), lg (250+)
Existing rules are automatically adapted by joining split_history to
transactions via transaction_id to recover the original amount.

Revision ID: 0006
Revises: 0005
Create Date: 2026-02-28
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("split_history") as batch_op:
        batch_op.add_column(sa.Column("amount_bucket", sa.String(), nullable=True))

    # Backfill bucket for all existing rows using the linked transaction amount.
    # Subquery form works on both SQLite and Postgres.
    op.execute("""
        UPDATE split_history
        SET amount_bucket = (
            SELECT CASE
                WHEN CAST(t.amount AS FLOAT) < 20  THEN 'xs'
                WHEN CAST(t.amount AS FLOAT) < 75  THEN 'sm'
                WHEN CAST(t.amount AS FLOAT) < 250 THEN 'md'
                ELSE 'lg'
            END
            FROM transactions t
            WHERE t.id = split_history.transaction_id
        )
    """)


def downgrade() -> None:
    with op.batch_alter_table("split_history") as batch_op:
        batch_op.drop_column("amount_bucket")
