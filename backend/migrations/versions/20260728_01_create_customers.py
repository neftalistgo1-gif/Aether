"""Create customers table.

Revision ID: 20260728_01
Revises:
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260728_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("phones", sa.JSON(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_customers_full_name"),
        "customers",
        ["full_name"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_customers_full_name"), table_name="customers")
    op.drop_table("customers")
