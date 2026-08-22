"""Add recurring local-ledger expense templates.

Revision ID: 0011
Revises: 0010
"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recurring_expenses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("cadence", sa.String(), nullable=False),
        sa.Column("payer_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("split_type", sa.Enum("equal", "full_you", "full_other", "percent", "exact", "personal", "already_added", name="splittype"), nullable=False),
        sa.Column("percent_you", sa.Numeric(5, 2), nullable=True),
        sa.Column("exact_you", sa.Numeric(10, 2), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.add_column(sa.Column("recurring_expense_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_transactions_recurring_expense", "recurring_expenses", ["recurring_expense_id"], ["id"])
        batch_op.create_unique_constraint("uq_transactions_recurring_occurrence", ["recurring_expense_id", "date"])


def downgrade() -> None:
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.drop_constraint("uq_transactions_recurring_occurrence", type_="unique")
        batch_op.drop_constraint("fk_transactions_recurring_expense", type_="foreignkey")
        batch_op.drop_column("recurring_expense_id")
    op.drop_table("recurring_expenses")
