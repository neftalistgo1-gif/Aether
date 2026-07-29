"""Create safe MikroTik network control.

Revision ID: 20260728_14
Revises: 20260728_13
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260728_14"
down_revision: str | None = "20260728_13"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mikrotik_routers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("endpoint_url", sa.String(length=500), nullable=False),
        sa.Column(
            "suspended_address_list",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column("credential_key", sa.String(length=50), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("verify_tls", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_mikrotik_routers_name"),
        "mikrotik_routers",
        ["name"],
        unique=True,
    )
    op.create_table(
        "network_control_commands",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("network_assignment_id", sa.Uuid(), nullable=False),
        sa.Column("router_id", sa.Uuid(), nullable=False),
        sa.Column(
            "action",
            sa.Enum(
                "suspend",
                "reactivate",
                "reconcile",
                name="network_control_action",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("target_ip", sa.String(length=45), nullable=False),
        sa.Column("desired_blocked", sa.Boolean(), nullable=False),
        sa.Column("dry_run", sa.Boolean(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "simulated",
                "succeeded",
                "failed",
                name="network_command_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("requested_by", sa.String(length=150), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("changed_router", sa.Boolean(), nullable=True),
        sa.Column("result_details", sa.JSON(), nullable=True),
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
        op.f("ix_network_control_commands_idempotency_key"),
        "network_control_commands",
        ["idempotency_key"],
        unique=True,
    )
    op.create_index(
        op.f("ix_network_control_commands_service_id"),
        "network_control_commands",
        ["service_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_network_control_commands_service_id"),
        table_name="network_control_commands",
    )
    op.drop_index(
        op.f("ix_network_control_commands_idempotency_key"),
        table_name="network_control_commands",
    )
    op.drop_table("network_control_commands")
    op.drop_index(
        op.f("ix_mikrotik_routers_name"),
        table_name="mikrotik_routers",
    )
    op.drop_table("mikrotik_routers")
