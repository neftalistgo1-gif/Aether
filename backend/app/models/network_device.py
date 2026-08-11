from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NetworkDeviceType(str, Enum):
    access_point = "access_point"
    station = "station"
    other = "other"


class NetworkDeviceStatus(str, Enum):
    online = "online"
    offline = "offline"
    unknown = "unknown"


class NetworkDevice(Base):
    __tablename__ = "network_devices"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    uisp_device_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    asset_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("assets.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    service_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("services.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    access_point_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("network_access_points.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    device_type: Mapped[NetworkDeviceType] = mapped_column(
        SqlEnum(NetworkDeviceType, name="network_device_type", native_enum=False, validate_strings=True)
    )
    display_name: Mapped[str] = mapped_column(String(150))
    management_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    mac_address: Mapped[str | None] = mapped_column(String(17), nullable=True)
    current_status: Mapped[NetworkDeviceStatus] = mapped_column(
        SqlEnum(NetworkDeviceStatus, name="network_device_status", native_enum=False, validate_strings=True),
        default=NetworkDeviceStatus.unknown,
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    offline_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    observed_details: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class DeviceStatusEvent(Base):
    __tablename__ = "device_status_events"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    device_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("network_devices.id", ondelete="RESTRICT"), index=True
    )
    previous_status: Mapped[NetworkDeviceStatus | None] = mapped_column(
        SqlEnum(NetworkDeviceStatus, name="network_device_status", native_enum=False, validate_strings=True), nullable=True
    )
    new_status: Mapped[NetworkDeviceStatus] = mapped_column(
        SqlEnum(NetworkDeviceStatus, name="network_device_status", native_enum=False, validate_strings=True)
    )
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)
    source: Mapped[str] = mapped_column(String(30), default="uisp")
