"""Seed the two known users with Splitwise IDs and AMEX account numbers.

Values are read from environment variables so nothing sensitive is committed:

    USER_1_EMAIL            e.g. you@gmail.com
    USER_1_SPLITWISE_ID     e.g. 12345678
    USER_1_AMEX_ACCOUNT     e.g. XXXX-12345   (optional)

    USER_2_EMAIL            e.g. partner@gmail.com
    USER_2_SPLITWISE_ID     e.g. 87654321
    USER_2_AMEX_ACCOUNT     e.g. XXXX-67890   (optional)

If any required var is missing the migration is skipped with a warning so
the schema migration still succeeds and you can populate users manually later.

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-28
"""
import os
from datetime import datetime

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

users_table = sa.table(
    "users",
    sa.column("email", sa.String),
    sa.column("splitwise_user_id", sa.String),
    sa.column("amex_account_number", sa.String),
    sa.column("created_at", sa.DateTime),
)


def _build_users() -> list[dict]:
    users = []
    for n in ("1", "2"):
        email = os.getenv(f"USER_{n}_EMAIL", "").strip()
        sw_id = os.getenv(f"USER_{n}_SPLITWISE_ID", "").strip()
        amex = os.getenv(f"USER_{n}_AMEX_ACCOUNT", "").strip() or None

        if not email or not sw_id:
            print(
                f"[seed] USER_{n}_EMAIL or USER_{n}_SPLITWISE_ID not set — skipping user {n}. "
                "Populate users.splitwise_user_id manually if needed."
            )
            continue

        users.append(
            {
                "email": email,
                "splitwise_user_id": sw_id,
                "amex_account_number": amex,
                "created_at": datetime.utcnow(),
            }
        )
    return users


def upgrade() -> None:
    rows = _build_users()
    if rows:
        op.bulk_insert(users_table, rows)


def downgrade() -> None:
    # Remove only the seeded emails so a targeted downgrade is safe
    conn = op.get_bind()
    for n in ("1", "2"):
        email = os.getenv(f"USER_{n}_EMAIL", "").strip()
        if email:
            conn.execute(
                sa.text("DELETE FROM users WHERE email = :email"),
                {"email": email},
            )
