"""Add suspension debt snapshot.

Revision ID: 20260728_13
Revises: 20260728_12
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260728_13"
down_revision: str | None = "20260728_12"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "suspensions",
        sa.Column("debt_snapshot", sa.JSON(), nullable=True),
    )
    op.execute(
        sa.text("UPDATE suspensions SET debt_snapshot = '[]'::json")
    )
    op.alter_column(
        "suspensions",
        "debt_snapshot",
        existing_type=sa.JSON(),
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column("suspensions", "debt_snapshot")
