"""Create UISP-backed network device telemetry inventory.

Revision ID: 20260811_02
Revises: 20260810_01
Create Date: 2026-08-11
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260811_02"
down_revision: str | None = "20260810_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table("network_devices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("uisp_device_id", sa.String(length=100), nullable=False),
        sa.Column("service_id", sa.Uuid(), sa.ForeignKey("services.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("access_point_id", sa.Uuid(), sa.ForeignKey("network_access_points.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("device_type", sa.String(length=20), nullable=False),
        sa.Column("display_name", sa.String(length=150), nullable=False),
        sa.Column("management_ip", sa.String(length=45), nullable=True),
        sa.Column("mac_address", sa.String(length=17), nullable=True),
        sa.Column("current_status", sa.String(length=20), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("offline_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("observed_details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("uisp_device_id"),
    )
    op.create_index(op.f("ix_network_devices_uisp_device_id"), "network_devices", ["uisp_device_id"], unique=False)
    op.create_index(op.f("ix_network_devices_service_id"), "network_devices", ["service_id"], unique=False)
    op.create_index(op.f("ix_network_devices_access_point_id"), "network_devices", ["access_point_id"], unique=False)
    op.create_table("device_status_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.Uuid(), sa.ForeignKey("network_devices.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("previous_status", sa.String(length=20), nullable=True),
        sa.Column("new_status", sa.String(length=20), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_device_status_events_device_id"), "device_status_events", ["device_id"], unique=False)
    op.create_index(op.f("ix_device_status_events_detected_at"), "device_status_events", ["detected_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_device_status_events_detected_at"), table_name="device_status_events")
    op.drop_index(op.f("ix_device_status_events_device_id"), table_name="device_status_events")
    op.drop_table("device_status_events")
    op.drop_index(op.f("ix_network_devices_access_point_id"), table_name="network_devices")
    op.drop_index(op.f("ix_network_devices_service_id"), table_name="network_devices")
    op.drop_index(op.f("ix_network_devices_uisp_device_id"), table_name="network_devices")
    op.drop_table("network_devices")
