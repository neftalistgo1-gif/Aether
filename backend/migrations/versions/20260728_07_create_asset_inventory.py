"""Create asset inventory and assignment history.

Revision ID: 20260728_07
Revises: 20260728_06
Create Date: 2026-07-28
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision: str = "20260728_07"
down_revision: str | None = "20260728_06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def enum(
    *values: str,
    name: str,
) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False)


def infer_asset_type(equipment_name: str) -> str:
    normalized = equipment_name.casefold()
    if "antena" in normalized:
        return "antenna"
    if "modem" in normalized or "módem" in normalized or "router" in normalized:
        return "router_modem"
    if "poe" in normalized:
        return "poe"
    if "fuente" in normalized:
        return "power_supply"
    if "tubo" in normalized or "mástil" in normalized or "mastil" in normalized:
        return "mast"
    if "ethernet" in normalized or "cable" in normalized:
        return "ethernet_cable"
    return "other"


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("internal_code", sa.String(length=30), nullable=False),
        sa.Column(
            "asset_type",
            enum(
                "antenna",
                "router_modem",
                "poe",
                "power_supply",
                "mast",
                "ethernet_cable",
                "other",
                name="asset_type",
            ),
            nullable=False,
        ),
        sa.Column("description", sa.String(length=150), nullable=False),
        sa.Column("brand", sa.String(length=100), nullable=True),
        sa.Column("model", sa.String(length=150), nullable=True),
        sa.Column("serial_number", sa.String(length=100), nullable=True),
        sa.Column("mac_address", sa.String(length=17), nullable=True),
        sa.Column(
            "owner",
            enum("amr", "customer", name="asset_owner"),
            nullable=False,
        ),
        sa.Column(
            "status",
            enum(
                "available",
                "quarantine",
                "needs_repair",
                "defective",
                "ready_for_reuse",
                "assigned",
                "discarded",
                "not_recovered",
                "sold_to_customer",
                name="asset_status",
            ),
            nullable=False,
        ),
        sa.Column("acquired_on", sa.Date(), nullable=True),
        sa.Column("latest_recovery_id", sa.Uuid(), nullable=True),
        sa.Column(
            "recovery_equipment_name",
            sa.String(length=150),
            nullable=True,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["latest_recovery_id"],
            ["equipment_recoveries.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mac_address"),
        sa.UniqueConstraint("serial_number"),
        sa.UniqueConstraint(
            "latest_recovery_id",
            "recovery_equipment_name",
            name="uq_assets_latest_recovery_equipment",
        ),
    )
    op.create_index(
        op.f("ix_assets_internal_code"),
        "assets",
        ["internal_code"],
        unique=True,
    )
    op.create_index(
        op.f("ix_assets_latest_recovery_id"),
        "assets",
        ["latest_recovery_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_assets_status"),
        "assets",
        ["status"],
        unique=False,
    )

    assets_table = sa.table(
        "assets",
        sa.column("id", sa.Uuid()),
        sa.column("internal_code", sa.String()),
        sa.column("asset_type", sa.String()),
        sa.column("description", sa.String()),
        sa.column("owner", sa.String()),
        sa.column("status", sa.String()),
        sa.column("latest_recovery_id", sa.Uuid()),
        sa.column("recovery_equipment_name", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    connection = op.get_bind()
    recoveries = connection.execute(
        sa.text(
            "SELECT id, recovered_equipment, created_at "
            "FROM equipment_recoveries "
            "WHERE recovered_equipment IS NOT NULL"
        )
    ).mappings()
    asset_ids: dict[tuple[str, str], object] = {}
    for recovery in recoveries:
        timestamp = recovery["created_at"] or datetime.now(UTC)
        for equipment_name in recovery["recovered_equipment"] or []:
            asset_id = uuid4()
            connection.execute(
                assets_table.insert().values(
                    id=asset_id,
                    internal_code=f"AST-{uuid4().hex[:12].upper()}",
                    asset_type=infer_asset_type(equipment_name),
                    description=equipment_name,
                    owner="amr",
                    status="quarantine",
                    latest_recovery_id=recovery["id"],
                    recovery_equipment_name=equipment_name,
                    created_at=timestamp,
                    updated_at=timestamp,
                )
            )
            asset_ids[
                (str(recovery["id"]), equipment_name.casefold())
            ] = asset_id

    op.add_column(
        "maintenance_inspections",
        sa.Column("asset_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_maintenance_inspections_asset_id_assets",
        "maintenance_inspections",
        "assets",
        ["asset_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        op.f("ix_maintenance_inspections_asset_id"),
        "maintenance_inspections",
        ["asset_id"],
        unique=False,
    )

    inspections = connection.execute(
        sa.text(
            "SELECT id, equipment_recovery_id, equipment_name "
            "FROM maintenance_inspections"
        )
    ).mappings()
    for inspection in inspections:
        asset_id = asset_ids.get(
            (
                str(inspection["equipment_recovery_id"]),
                inspection["equipment_name"].casefold(),
            )
        )
        if asset_id is None:
            raise RuntimeError(
                "Maintenance inspection has no matching recovered asset"
            )
        connection.execute(
            sa.text(
                "UPDATE maintenance_inspections "
                "SET asset_id = :asset_id WHERE id = :inspection_id"
            ),
            {
                "asset_id": asset_id,
                "inspection_id": inspection["id"],
            },
        )
    op.alter_column(
        "maintenance_inspections",
        "asset_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )

    op.create_table(
        "asset_assignments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("assigned_by", sa.String(length=150), nullable=False),
        sa.Column("condition_on_delivery", sa.Text(), nullable=False),
        sa.Column(
            "ownership",
            enum("amr", "customer", name="asset_owner"),
            nullable=False,
        ),
        sa.Column(
            "returned_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("returned_by", sa.String(length=150), nullable=True),
        sa.Column("condition_on_return", sa.Text(), nullable=True),
        sa.Column(
            "return_outcome",
            enum(
                "recovered",
                "not_recovered",
                "sold_to_customer",
                name="asset_return_outcome",
            ),
            nullable=True,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["assets.id"],
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
        op.f("ix_asset_assignments_asset_id"),
        "asset_assignments",
        ["asset_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_asset_assignments_service_id"),
        "asset_assignments",
        ["service_id"],
        unique=False,
    )
    op.create_index(
        "uq_asset_assignments_active_asset",
        "asset_assignments",
        ["asset_id"],
        unique=True,
        postgresql_where=sa.text("returned_at IS NULL"),
        sqlite_where=sa.text("returned_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_asset_assignments_active_asset",
        table_name="asset_assignments",
    )
    op.drop_index(
        op.f("ix_asset_assignments_service_id"),
        table_name="asset_assignments",
    )
    op.drop_index(
        op.f("ix_asset_assignments_asset_id"),
        table_name="asset_assignments",
    )
    op.drop_table("asset_assignments")
    op.drop_index(
        op.f("ix_maintenance_inspections_asset_id"),
        table_name="maintenance_inspections",
    )
    op.drop_constraint(
        "fk_maintenance_inspections_asset_id_assets",
        "maintenance_inspections",
        type_="foreignkey",
    )
    op.drop_column("maintenance_inspections", "asset_id")
    op.drop_index(op.f("ix_assets_status"), table_name="assets")
    op.drop_index(
        op.f("ix_assets_latest_recovery_id"),
        table_name="assets",
    )
    op.drop_index(op.f("ix_assets_internal_code"), table_name="assets")
    op.drop_table("assets")
