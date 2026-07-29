"""Add persisted read-only network state inspections.

Revision ID: 20260729_33
Revises: 20260729_32
Create Date: 2026-07-29
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260729_33"
down_revision: str | None = "20260729_32"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "network_state_inspections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("network_assignment_id", sa.Uuid(), nullable=False),
        sa.Column("router_id", sa.Uuid(), nullable=False),
        sa.Column("target_ip", sa.String(length=45), nullable=False),
        sa.Column("expected_blocked", sa.Boolean(), nullable=False),
        sa.Column("observed_blocked", sa.Boolean(), nullable=True),
        sa.Column("matches_expected", sa.Boolean(), nullable=True),
        sa.Column("entry_count", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "succeeded",
                "failed",
                name="network_inspection_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("requested_by", sa.String(length=150), nullable=False),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["network_assignment_id"],
            ["network_assignments.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["router_id"],
            ["mikrotik_routers.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["services.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_network_state_inspections_idempotency_key",
        "network_state_inspections",
        ["idempotency_key"],
        unique=True,
    )
    op.create_index(
        "ix_network_state_inspections_service_id",
        "network_state_inspections",
        ["service_id"],
        unique=False,
    )
    op.add_column(
        "network_control_commands",
        sa.Column("network_inspection_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_network_control_commands_network_inspection_id",
        "network_control_commands",
        "network_state_inspections",
        ["network_inspection_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_network_control_commands_network_inspection_id",
        "network_control_commands",
        ["network_inspection_id"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_network_control_commands_inspection_mode",
        "network_control_commands",
        ["network_inspection_id", "dry_run"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_network_control_commands_inspection_mode",
        "network_control_commands",
        type_="unique",
    )
    op.drop_index(
        "ix_network_control_commands_network_inspection_id",
        table_name="network_control_commands",
    )
    op.drop_constraint(
        "fk_network_control_commands_network_inspection_id",
        "network_control_commands",
        type_="foreignkey",
    )
    op.drop_column("network_control_commands", "network_inspection_id")
    op.drop_index(
        "ix_network_state_inspections_service_id",
        table_name="network_state_inspections",
    )
    op.drop_index(
        "ix_network_state_inspections_idempotency_key",
        table_name="network_state_inspections",
    )
    op.drop_table("network_state_inspections")
