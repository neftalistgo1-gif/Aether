"""Expand network action storage for decommission commands.

Revision ID: 20260729_31
Revises: 20260729_30
Create Date: 2026-07-29
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260729_31"
down_revision: str | None = "20260729_30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "network_control_commands",
        "action",
        existing_type=sa.String(length=10),
        type_=sa.String(length=12),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "network_control_commands",
        "action",
        existing_type=sa.String(length=12),
        type_=sa.String(length=10),
        existing_nullable=False,
    )
