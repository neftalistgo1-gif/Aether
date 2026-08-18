from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.network_device import NetworkDeviceStatus, NetworkDeviceType


class NetworkDeviceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    uisp_device_id: str
    service_id: UUID | None
    access_point_id: UUID | None
    device_type: NetworkDeviceType
    display_name: str
    management_ip: str | None
    mac_address: str | None
    current_status: NetworkDeviceStatus
    last_seen_at: datetime | None
    offline_since: datetime | None
    last_synced_at: datetime | None
    observed_details: dict[str, object] | None
    suspended_in_mikrotik: bool = False


class DeviceStatusEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    device_id: UUID
    previous_status: NetworkDeviceStatus | None
    new_status: NetworkDeviceStatus
    detected_at: datetime
    source: str


class NetworkDailySummaryRead(BaseModel):
    generated_at: datetime
    total_devices: int
    online: int
    offline: int
    unknown: int
    newly_offline_today: int
    offline_over_24_hours: int
    offline_over_72_hours: int
