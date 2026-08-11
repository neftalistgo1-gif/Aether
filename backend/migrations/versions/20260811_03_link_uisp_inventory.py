"""Link UISP telemetry records to inventory assets.

Revision ID: 20260811_03
Revises: 20260811_02
Create Date: 2026-08-11
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260811_03"
down_revision: str | None = "20260811_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("network_devices", sa.Column("asset_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_network_devices_asset_id_assets", "network_devices", "assets", ["asset_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_index(op.f("ix_network_devices_asset_id"), "network_devices", ["asset_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_network_devices_asset_id"), table_name="network_devices")
    op.drop_constraint("fk_network_devices_asset_id_assets", "network_devices", type_="foreignkey")
    op.drop_column("network_devices", "asset_id")
