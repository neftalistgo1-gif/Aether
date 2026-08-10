"""Create network access point monitoring inventory.

Revision ID: 20260810_01
Revises: 20260807_01
Create Date: 2026-08-10
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260810_01"
down_revision: str | None = "20260807_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "network_access_points",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("router_id", sa.Uuid(), sa.ForeignKey("mikrotik_routers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=False),
        sa.Column("mac_address", sa.String(length=17), nullable=True),
        sa.Column("interface_name", sa.String(length=150), nullable=True),
        sa.Column("platform", sa.String(length=150), nullable=True),
        sa.Column("source_note", sa.String(length=250), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("router_id", "ip_address", name="uq_network_access_points_router_ip"),
    )
    op.create_index(op.f("ix_network_access_points_router_id"), "network_access_points", ["router_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_network_access_points_router_id"), table_name="network_access_points")
    op.drop_table("network_access_points")
