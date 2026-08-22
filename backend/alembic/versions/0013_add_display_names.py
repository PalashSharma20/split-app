"""Add optional display names for users.

Revision ID: 0013
Revises: 0012
"""
import os
from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("display_name", sa.String(), nullable=True))
    conn = op.get_bind()
    for n in ("1", "2"):
        email = os.getenv(f"USER_{n}_EMAIL", "").strip()
        name = os.getenv(f"USER_{n}_NAME", "").strip()
        if email and name:
            conn.execute(sa.text("UPDATE users SET display_name = :name WHERE email = :email"), {"name": name, "email": email})


def downgrade() -> None:
    op.drop_column("users", "display_name")
