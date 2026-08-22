"""Seed the two known users and their AMEX account numbers.

Values are read from environment variables so nothing sensitive is committed:

    USER_1_EMAIL            e.g. you@gmail.com
    USER_1_AMEX_ACCOUNT     e.g. XXXX-12345   (optional)

    USER_2_EMAIL            e.g. partner@gmail.com
    USER_2_AMEX_ACCOUNT     e.g. XXXX-67890   (optional)

If either email is missing the corresponding user is skipped so the schema
migration can still succeed and you can populate users manually later.

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
        # Kept for backwards compatibility with databases created before the
        # app became a local ledger; it is no longer required.
        sw_id = os.getenv(f"USER_{n}_SPLITWISE_ID", "").strip() or None
        amex = os.getenv(f"USER_{n}_AMEX_ACCOUNT", "").strip() or None

        if not email:
            print(
                f"[seed] USER_{n}_EMAIL not set — skipping user {n}."
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
