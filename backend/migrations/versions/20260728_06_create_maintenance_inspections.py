"""Create maintenance inspection records.

Revision ID: 20260728_06
Revises: 20260728_05
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260728_06"
down_revision: str | None = "20260728_05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def inspection_result_enum() -> sa.Enum:
    return sa.Enum(
        "ready_for_reuse",
        "needs_repair",
        "defective",
        "discarded",
        name="maintenance_inspection_result",
        native_enum=False,
    )


def upgrade() -> None:
    op.create_table(
        "maintenance_inspections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("equipment_recovery_id", sa.Uuid(), nullable=False),
        sa.Column("equipment_name", sa.String(length=150), nullable=False),
        sa.Column("technician", sa.String(length=150), nullable=False),
        sa.Column(
            "inspected_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("serial_number", sa.String(length=100), nullable=True),
        sa.Column("mac_address", sa.String(length=17), nullable=True),
        sa.Column("model", sa.String(length=150), nullable=True),
        sa.Column("cleaning_performed", sa.Boolean(), nullable=False),
        sa.Column("cleaning_notes", sa.Text(), nullable=True),
        sa.Column("tests", sa.JSON(), nullable=False),
        sa.Column("repairs_performed", sa.JSON(), nullable=False),
        sa.Column("evidence_references", sa.JSON(), nullable=False),
        sa.Column("result", inspection_result_enum(), nullable=False),
        sa.Column("decision_reason", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["equipment_recovery_id"],
            ["equipment_recoveries.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_maintenance_inspections_equipment_name"),
        "maintenance_inspections",
        ["equipment_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_maintenance_inspections_equipment_recovery_id"),
        "maintenance_inspections",
        ["equipment_recovery_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_maintenance_inspections_equipment_recovery_id"),
        table_name="maintenance_inspections",
    )
    op.drop_index(
        op.f("ix_maintenance_inspections_equipment_name"),
        table_name="maintenance_inspections",
    )
    op.drop_table("maintenance_inspections")
