"""Add payer and source fields for the local expense ledger.

Revision ID: 0010
Revises: 0009
"""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.add_column(sa.Column("payer_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("is_custom", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.create_foreign_key("fk_transactions_payer_id_users", "users", ["payer_id"], ["id"])
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.alter_column("is_custom", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.drop_constraint("fk_transactions_payer_id_users", type_="foreignkey")
        batch_op.drop_column("is_custom")
        batch_op.drop_column("payer_id")
