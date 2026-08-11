"""Create MikroTik interface traffic history.

Revision ID: 20260811_04
Revises: 20260811_03
Create Date: 2026-08-11
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260811_04"
down_revision: str | None = "20260811_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mikrotik_traffic_samples",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("router_id", sa.Uuid(), sa.ForeignKey("mikrotik_routers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("interface_name", sa.String(length=150), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rx_bytes", sa.BigInteger(), nullable=False),
        sa.Column("tx_bytes", sa.BigInteger(), nullable=False),
        sa.Column("rx_bps", sa.Float(), nullable=False),
        sa.Column("tx_bps", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mikrotik_traffic_samples_router_id"), "mikrotik_traffic_samples", ["router_id"], unique=False)
    op.create_index(op.f("ix_mikrotik_traffic_samples_interface_name"), "mikrotik_traffic_samples", ["interface_name"], unique=False)
    op.create_index(op.f("ix_mikrotik_traffic_samples_captured_at"), "mikrotik_traffic_samples", ["captured_at"], unique=False)
    op.create_index("ix_mikrotik_traffic_samples_router_interface_captured", "mikrotik_traffic_samples", ["router_id", "interface_name", "captured_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_mikrotik_traffic_samples_router_interface_captured", table_name="mikrotik_traffic_samples")
    op.drop_index(op.f("ix_mikrotik_traffic_samples_captured_at"), table_name="mikrotik_traffic_samples")
    op.drop_index(op.f("ix_mikrotik_traffic_samples_interface_name"), table_name="mikrotik_traffic_samples")
    op.drop_index(op.f("ix_mikrotik_traffic_samples_router_id"), table_name="mikrotik_traffic_samples")
    op.drop_table("mikrotik_traffic_samples")
