"""Track the network identity of physical assets.

Revision ID: 20260813_01
Revises: 20260811_04
Create Date: 2026-08-13
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260813_01"
down_revision: str | None = "20260811_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("assets", sa.Column("device_name", sa.String(length=150), nullable=True))
    op.add_column("assets", sa.Column("management_ip", sa.String(length=45), nullable=True))
    op.create_index(op.f("ix_assets_management_ip"), "assets", ["management_ip"], unique=False)
    op.execute("UPDATE assets SET device_name = description WHERE device_name IS NULL")
    op.create_table(
        "asset_network_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("previous_device_name", sa.String(length=150), nullable=True),
        sa.Column("new_device_name", sa.String(length=150), nullable=True),
        sa.Column("previous_management_ip", sa.String(length=45), nullable=True),
        sa.Column("new_management_ip", sa.String(length=45), nullable=True),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_asset_network_history_asset_id"), "asset_network_history", ["asset_id"], unique=False)
    op.create_index(op.f("ix_asset_network_history_changed_at"), "asset_network_history", ["changed_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_asset_network_history_changed_at"), table_name="asset_network_history")
    op.drop_index(op.f("ix_asset_network_history_asset_id"), table_name="asset_network_history")
    op.drop_table("asset_network_history")
    op.drop_index(op.f("ix_assets_management_ip"), table_name="assets")
    op.drop_column("assets", "management_ip")
    op.drop_column("assets", "device_name")
