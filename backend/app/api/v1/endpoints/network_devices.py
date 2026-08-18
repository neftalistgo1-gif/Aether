from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.endpoints.services import find_service_or_404
from app.db.session import get_db
from app.integrations.mikrotik import RouterOSRestClient
from app.models.mikrotik import MikrotikRouter
from app.models.network_device import DeviceStatusEvent, NetworkDevice, NetworkDeviceStatus
from app.schemas.network_device import DeviceStatusEventRead, NetworkDailySummaryRead, NetworkDeviceRead

router = APIRouter(prefix="/api/v1", tags=["network devices"])


def suspended_management_ips(db: Session) -> set[str]:
    """Return the live suspension list without treating it as UISP telemetry."""
    router_record = db.scalar(select(MikrotikRouter).order_by(MikrotikRouter.name))
    if router_record is None:
        return set()
    try:
        entries = RouterOSRestClient(router_record, monitor=True)._request(
            "GET", "/rest/ip/firewall/address-list"
        ) or []
    except RuntimeError:
        return set()
    return {
        str(entry.get("address"))
        for entry in entries
        if entry.get("list") == router_record.suspended_address_list
        and isinstance(entry.get("address"), str)
    }


@router.get("/network/devices", response_model=list[NetworkDeviceRead])
def list_network_devices(db: Session = Depends(get_db)) -> list[NetworkDeviceRead]:
    suspended_ips = suspended_management_ips(db)
    devices = list(db.scalars(select(NetworkDevice).order_by(NetworkDevice.display_name, NetworkDevice.id)))
    return [
        NetworkDeviceRead.model_validate(device).model_copy(
            update={"suspended_in_mikrotik": device.management_ip in suspended_ips}
        )
        for device in devices
    ]


@router.get("/services/{service_id}/network-device", response_model=NetworkDeviceRead)
def get_service_network_device(service_id: UUID, db: Session = Depends(get_db)) -> NetworkDevice:
    find_service_or_404(service_id, db)
    device = db.scalar(select(NetworkDevice).where(NetworkDevice.service_id == service_id))
    if device is None:
        raise HTTPException(status_code=404, detail="Network device not linked to service")
    return device


@router.get("/network/devices/{device_id}/status-events", response_model=list[DeviceStatusEventRead])
def list_device_status_events(device_id: UUID, db: Session = Depends(get_db)) -> list[DeviceStatusEvent]:
    if db.get(NetworkDevice, device_id) is None:
        raise HTTPException(status_code=404, detail="Network device not found")
    return list(db.scalars(select(DeviceStatusEvent).where(DeviceStatusEvent.device_id == device_id).order_by(DeviceStatusEvent.detected_at.desc(), DeviceStatusEvent.id.desc())))


@router.get("/network/daily-summary", response_model=NetworkDailySummaryRead)
def get_network_daily_summary(db: Session = Depends(get_db)) -> NetworkDailySummaryRead:
    now = datetime.now(UTC)
    devices = list(db.scalars(select(NetworkDevice)))
    offline = [item for item in devices if item.current_status == NetworkDeviceStatus.offline]
    return NetworkDailySummaryRead(
        generated_at=now,
        total_devices=len(devices),
        online=sum(item.current_status == NetworkDeviceStatus.online for item in devices),
        offline=len(offline),
        unknown=sum(item.current_status == NetworkDeviceStatus.unknown for item in devices),
        newly_offline_today=sum(item.offline_since is not None and item.offline_since >= now - timedelta(days=1) for item in offline),
        offline_over_24_hours=sum(item.offline_since is not None and item.offline_since <= now - timedelta(hours=24) for item in offline),
        offline_over_72_hours=sum(item.offline_since is not None and item.offline_since <= now - timedelta(hours=72) for item in offline),
    )
