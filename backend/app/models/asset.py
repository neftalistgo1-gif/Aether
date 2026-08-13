from datetime import UTC, date, datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import (
    Date,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AssetType(str, Enum):
    antenna = "antenna"
    cpe = "cpe"
    access_point = "access_point"
    mikrotik = "mikrotik"
    pc = "pc"
    router_modem = "router_modem"
    poe = "poe"
    power_supply = "power_supply"
    mast = "mast"
    ethernet_cable = "ethernet_cable"
    other = "other"


class AssetOwner(str, Enum):
    amr = "amr"
    customer = "customer"


class AssetStatus(str, Enum):
    available = "available"
    quarantine = "quarantine"
    needs_repair = "needs_repair"
    defective = "defective"
    ready_for_reuse = "ready_for_reuse"
    assigned = "assigned"
    installed = "installed"
    discarded = "discarded"
    not_recovered = "not_recovered"
    sold_to_customer = "sold_to_customer"


class AssetReturnOutcome(str, Enum):
    recovered = "recovered"
    not_recovered = "not_recovered"
    sold_to_customer = "sold_to_customer"


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (
        UniqueConstraint(
            "latest_recovery_id",
            "recovery_equipment_name",
            name="uq_assets_latest_recovery_equipment",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    internal_code: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        index=True,
    )
    asset_type: Mapped[AssetType] = mapped_column(
        SqlEnum(
            AssetType,
            name="asset_type",
            native_enum=False,
            validate_strings=True,
        )
    )
    description: Mapped[str] = mapped_column(String(150))
    device_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    management_ip: Mapped[str | None] = mapped_column(String(45), nullable=True, index=True)
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(150), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(
        String(100),
        unique=True,
        nullable=True,
    )
    mac_address: Mapped[str | None] = mapped_column(
        String(17),
        unique=True,
        nullable=True,
    )
    owner: Mapped[AssetOwner] = mapped_column(
        SqlEnum(
            AssetOwner,
            name="asset_owner",
            native_enum=False,
            validate_strings=True,
        ),
        default=AssetOwner.amr,
    )
    status: Mapped[AssetStatus] = mapped_column(
        SqlEnum(
            AssetStatus,
            name="asset_status",
            native_enum=False,
            validate_strings=True,
        ),
        default=AssetStatus.available,
        index=True,
    )
    acquired_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    latest_recovery_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("equipment_recoveries.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    recovery_equipment_name: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    assignments: Mapped[list["AssetAssignment"]] = relationship(
        back_populates="asset",
        order_by="AssetAssignment.assigned_at",
        lazy="selectin",
    )
    network_history: Mapped[list["AssetNetworkHistory"]] = relationship(
        back_populates="asset",
        cascade="all, delete-orphan",
        order_by="AssetNetworkHistory.changed_at",
        lazy="selectin",
    )


class AssetNetworkHistory(Base):
    __tablename__ = "asset_network_history"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    asset_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), index=True
    )
    previous_device_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    new_device_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    previous_management_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    new_management_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    source: Mapped[str] = mapped_column(String(30), default="uisp")
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )

    asset: Mapped["Asset"] = relationship(back_populates="network_history")


class AssetAssignment(Base):
    __tablename__ = "asset_assignments"
    __table_args__ = (
        Index(
            "uq_asset_assignments_active_asset",
            "asset_id",
            unique=True,
            postgresql_where=text("returned_at IS NULL"),
            sqlite_where=text("returned_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    asset_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assets.id", ondelete="RESTRICT"),
        index=True,
    )
    service_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("services.id", ondelete="RESTRICT"),
        index=True,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    assigned_by: Mapped[str] = mapped_column(String(150))
    condition_on_delivery: Mapped[str] = mapped_column(Text)
    ownership: Mapped[AssetOwner] = mapped_column(
        SqlEnum(
            AssetOwner,
            name="asset_owner",
            native_enum=False,
            validate_strings=True,
        )
    )
    returned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    returned_by: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )
    condition_on_return: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    return_outcome: Mapped[AssetReturnOutcome | None] = mapped_column(
        SqlEnum(
            AssetReturnOutcome,
            name="asset_return_outcome",
            native_enum=False,
            validate_strings=True,
        ),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    asset: Mapped[Asset] = relationship(back_populates="assignments")
