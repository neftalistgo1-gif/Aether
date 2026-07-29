"""Create daily operation runs.

Revision ID: 20260728_25
Revises: 20260728_24
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260728_25"
down_revision: str | None = "20260728_24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "daily_operation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "completed",
                name="daily_operation_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("monthly_charges_created", sa.Integer(), nullable=False),
        sa.Column("extensions_expired", sa.Integer(), nullable=False),
        sa.Column("executed_by", sa.String(length=150), nullable=False),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_daily_operation_runs_run_date"),
        "daily_operation_runs",
        ["run_date"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_daily_operation_runs_run_date"),
        table_name="daily_operation_runs",
    )
    op.drop_table("daily_operation_runs")
