"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-02-28
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("splitwise_user_id", sa.String(), nullable=True),
        sa.Column("amex_account_number", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("amex_reference", sa.String(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("description_raw", sa.String(), nullable=False),
        sa.Column("description_normalized", sa.String(), nullable=False),
        sa.Column("merchant_key", sa.String(), nullable=False),
        sa.Column("sub_merchant_key", sa.String(), nullable=True),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("synced", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("splitwise_expense_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_transactions_amex_reference", "transactions", ["amex_reference"], unique=True)
    op.create_index("ix_transactions_merchant_key", "transactions", ["merchant_key"])
    op.create_index("ix_transactions_sub_merchant_key", "transactions", ["sub_merchant_key"])
    op.create_index("ix_transactions_synced", "transactions", ["synced"])

    op.create_table(
        "split_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("transactions.id"), nullable=False),
        sa.Column("merchant_key", sa.String(), nullable=False),
        sa.Column("sub_merchant_key", sa.String(), nullable=True),
        sa.Column(
            "split_type",
            sa.Enum("equal", "full_you", "full_other", "percent", "exact", name="splittype"),
            nullable=False,
        ),
        sa.Column("percent_you", sa.Numeric(5, 2), nullable=True),
        sa.Column("exact_you", sa.Numeric(10, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_split_history_merchant", "split_history", ["merchant_key"])
    op.create_index("ix_split_history_merchant_sub", "split_history", ["merchant_key", "sub_merchant_key"])
    op.create_index("ix_split_history_created_at", "split_history", ["created_at"])


def downgrade() -> None:
    op.drop_table("split_history")
    op.drop_table("transactions")
    op.drop_table("users")
