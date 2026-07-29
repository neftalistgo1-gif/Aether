"""Create equipment recovery records.

Revision ID: 20260728_05
Revises: 20260728_04
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260728_05"
down_revision: str | None = "20260728_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "equipment_recoveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cancellation_id", sa.Uuid(), nullable=False),
        sa.Column("scheduled_for", sa.Date(), nullable=False),
        sa.Column(
            "assigned_technician",
            sa.String(length=150),
            nullable=False,
        ),
        sa.Column("expected_equipment", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "performed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("performed_by", sa.String(length=150), nullable=True),
        sa.Column("recovered_equipment", sa.JSON(), nullable=True),
        sa.Column("missing_equipment", sa.JSON(), nullable=True),
        sa.Column("condition_notes", sa.Text(), nullable=True),
        sa.Column("evidence_references", sa.JSON(), nullable=True),
        sa.Column(
            "receipt_reference",
            sa.String(length=500),
            nullable=True,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["cancellation_id"],
            ["cancellations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_equipment_recoveries_cancellation_id"),
        "equipment_recoveries",
        ["cancellation_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_equipment_recoveries_cancellation_id"),
        table_name="equipment_recoveries",
    )
    op.drop_table("equipment_recoveries")
