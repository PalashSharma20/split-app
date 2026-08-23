"""Record which user's share is stored on a split.

Revision ID: 0014
Revises: 0013
"""

from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("split_history") as batch_op:
        batch_op.add_column(sa.Column("split_for_user_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_split_history_split_for_user_id_users",
            "users",
            ["split_for_user_id"],
            ["id"],
        )
    with op.batch_alter_table("recurring_expenses") as batch_op:
        batch_op.add_column(sa.Column("split_for_user_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_recurring_expenses_split_for_user_id_users",
            "users",
            ["split_for_user_id"],
            ["id"],
        )

    conn = op.get_bind()
    # Existing splits were entered from the uploading user's perspective.
    # Historical recurring rows predate creator tracking, so fall back to the
    # first configured user, which matches the legacy app's "you" semantics.
    conn.execute(
        sa.text(
            """
        UPDATE split_history
        SET split_for_user_id = COALESCE(
            (SELECT uploaded_by FROM transactions WHERE transactions.id = split_history.transaction_id),
            (SELECT MIN(id) FROM users)
        )
    """
        )
    )
    conn.execute(
        sa.text(
            """
        UPDATE recurring_expenses
        SET split_for_user_id = (SELECT MIN(id) FROM users)
    """
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("recurring_expenses") as batch_op:
        batch_op.drop_constraint(
            "fk_recurring_expenses_split_for_user_id_users", type_="foreignkey"
        )
        batch_op.drop_column("split_for_user_id")
    with op.batch_alter_table("split_history") as batch_op:
        batch_op.drop_constraint(
            "fk_split_history_split_for_user_id_users", type_="foreignkey"
        )
        batch_op.drop_column("split_for_user_id")
