import json
import re
import ssl
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from dataclasses import dataclass
from urllib import error, request

from app.core.config import (
    UISP_API_TOKEN,
    UISP_ENDPOINT_URL,
    UISP_TIMEOUT_SECONDS,
    UISP_VERIFY_TLS,
    UISP_SERVICE_REFERENCE_PATH,
)
from app.models.network_device import (
    DeviceStatusEvent,
    NetworkDevice,
    NetworkDeviceStatus,
    NetworkDeviceType,
)
from app.models.access_point import NetworkAccessPoint
from app.models.asset import Asset, AssetOwner, AssetStatus, AssetType
from app.models.service import Service, ServiceEvent, ServiceEventType, ServiceStatus
from app.models.plan import Plan
from sqlalchemy import select
from uuid import uuid4


@dataclass(frozen=True)
class UISPConnectionResult:
    device_count: int


class UISPReadClient:
    """Small read-only client for the UISP Network API.

    Device persistence is intentionally separate: UISP response fields must be
    validated against the AMR instance before they are mapped to Aether.
    """

    def __init__(self) -> None:
        if not UISP_ENDPOINT_URL or not UISP_API_TOKEN:
            raise RuntimeError("UISP credentials are not configured")
        self.endpoint_url = UISP_ENDPOINT_URL.rstrip("/")
        if not self.endpoint_url.lower().startswith("https://"):
            raise RuntimeError("UISP endpoint must use HTTPS")
        self.ssl_context = ssl.create_default_context()
        if not UISP_VERIFY_TLS:
            self.ssl_context.check_hostname = False
            self.ssl_context.verify_mode = ssl.CERT_NONE

    def _request(self, path: str):
        call = request.Request(
            f"{self.endpoint_url}{path}",
            headers={
                "Accept": "application/json",
                "x-auth-token": UISP_API_TOKEN,
            },
            method="GET",
        )
        try:
            with request.urlopen(
                call,
                timeout=UISP_TIMEOUT_SECONDS,
                context=self.ssl_context,
            ) as response:
                return json.loads(response.read().decode("utf-8"))
        except (error.URLError, TimeoutError, ValueError) as exc:
            raise RuntimeError(f"UISP request failed: {type(exc).__name__}") from exc

    def test_connection(self) -> UISPConnectionResult:
        devices = self.list_devices()
        return UISPConnectionResult(device_count=len(devices))

    def list_devices(self) -> list[dict]:
        payload = self._request("/nms/api/v2.1/devices")
        if isinstance(payload, list):
            devices = payload
        elif isinstance(payload, dict):
            devices = payload.get("devices", payload.get("data"))
        else:
            devices = None
        if not isinstance(devices, list):
            raise RuntimeError("UISP devices response has an unsupported shape")
        return devices


def parse_uisp_datetime(value) -> datetime | None:
    if not isinstance(value, str):
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


AMR_CODE_PATTERN = re.compile(r"\b(AMR\d{3,6})\b", re.IGNORECASE)


def normalize_mac_address(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    compact = re.sub(r"[^0-9a-fA-F]", "", value)
    if len(compact) != 12:
        return None
    return ":".join(compact[index:index + 2].upper() for index in range(0, 12, 2))


def device_amr_code(display_name: str) -> str | None:
    match = AMR_CODE_PATTERN.search(display_name)
    return match.group(1).upper() if match else None


def inventory_asset_type(device_type: NetworkDeviceType) -> AssetType:
    return AssetType.access_point if device_type == NetworkDeviceType.access_point else AssetType.cpe


def sync_inventory_asset(db, *, item: NetworkDevice, identity: dict, device_type: NetworkDeviceType) -> bool:
    mac_address = normalize_mac_address(identity.get("mac"))
    asset = db.scalar(select(Asset).where(Asset.mac_address == mac_address)) if mac_address else None
    created = asset is None
    if asset is None:
        asset = Asset(
            internal_code=f"AST-{uuid4().hex[:12].upper()}",
            asset_type=inventory_asset_type(device_type),
            description=item.display_name,
            owner=AssetOwner.amr,
            status=AssetStatus.installed,
        )
        db.add(asset)
    asset.asset_type = inventory_asset_type(device_type)
    asset.description = item.display_name
    asset.brand = "Ubiquiti"
    asset.model = identity.get("model") or asset.model
    asset.mac_address = mac_address
    asset.status = AssetStatus.installed
    asset.notes = f"Sincronizado desde UISP: {item.uisp_device_id}"
    db.flush()
    item.asset_id = asset.id
    return created


def link_matching_service(db, item: NetworkDevice) -> bool:
    if item.device_type != NetworkDeviceType.station:
        return False
    amr_code = device_amr_code(item.display_name)
    if not amr_code:
        return False
    reference = load_service_reference().get(amr_code, {})
    service = db.scalar(select(Service).where(Service.amr_code == amr_code, Service.status != ServiceStatus.cancelled))
    if service is None:
        plan = closest_plan(db, reference.get("speed_mbps"))
        if plan is None or plan.current_price is None:
            return False
        cutoff = reference_date(reference)
        service = Service(
            amr_code=amr_code,
            plan_id=plan.id,
            plan_name=plan.name,
            monthly_price=plan.current_price,
            payment_day=cutoff.day,
            activation_date=cutoff,
            address=reference.get("address") or item.display_name,
            status=ServiceStatus.pending,
        )
        db.add(service)
        db.flush()
    elif service.status == ServiceStatus.pending and service.current_customer_id is None:
        apply_reference_to_pending_service(service, db, reference, item.display_name)
    changed = item.service_id != service.id
    item.service_id = service.id
    return changed


def load_service_reference() -> dict[str, dict]:
    try:
        source = json.loads(Path(UISP_SERVICE_REFERENCE_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return source if isinstance(source, dict) else {}


def reference_date(reference: dict) -> date:
    value = reference.get("start_date")
    try:
        return date.fromisoformat(value) if isinstance(value, str) else date(2026, 8, 1)
    except ValueError:
        return date(2026, 8, 1)


def speed_mbps(value: object) -> int | None:
    match = re.search(r"\d+", str(value or ""))
    return int(match.group()) if match else None


def closest_plan(db, desired_speed: object) -> Plan | None:
    plans = list(db.scalars(select(Plan)))
    if not plans:
        return None
    requested = speed_mbps(desired_speed) or 15
    return min(plans, key=lambda plan: abs((speed_mbps(plan.speed) or 15) - requested))


def apply_reference_to_pending_service(service: Service, db, reference: dict, fallback_address: str) -> None:
    plan = closest_plan(db, reference.get("speed_mbps"))
    if plan is not None and plan.current_price is not None:
        service.plan_id = plan.id
        service.plan_name = plan.name
        service.monthly_price = plan.current_price
    cutoff = reference_date(reference)
    service.payment_day = cutoff.day
    service.activation_date = cutoff
    if reference.get("address"):
        service.address = reference["address"]
    elif not service.address:
        service.address = fallback_address


def sync_devices(db, devices: list[dict]) -> dict[str, int]:
    created = updated = status_events = inventory_created = services_linked = 0
    now = datetime.now(UTC)
    for source in devices:
        identity = source.get("identification") or {}
        overview = source.get("overview") or {}
        device_id = identity.get("id")
        if not isinstance(device_id, str):
            continue
        role = identity.get("role")
        device_type = NetworkDeviceType.access_point if role == "ap" else NetworkDeviceType.station if role == "station" else NetworkDeviceType.other
        next_status = NetworkDeviceStatus.online if overview.get("status") == "active" else NetworkDeviceStatus.offline
        last_seen = parse_uisp_datetime(overview.get("lastSeen"))
        details = {key: overview.get(key) for key in ("signal", "signalMax", "remoteSignalMax", "frequency", "channelWidth", "linkScore", "uplinkCapacity", "downlinkCapacity", "wirelessMode") if key in overview}
        item = db.scalar(select(NetworkDevice).where(NetworkDevice.uisp_device_id == device_id))
        if item is None:
            item = NetworkDevice(uisp_device_id=device_id, device_type=device_type, display_name=identity.get("displayName") or identity.get("name") or device_id, current_status=next_status)
            db.add(item); db.flush(); created += 1
            db.add(DeviceStatusEvent(device_id=item.id, previous_status=None, new_status=next_status, source="uisp")); status_events += 1
        else:
            updated += 1
            if item.current_status != next_status:
                db.add(DeviceStatusEvent(device_id=item.id, previous_status=item.current_status, new_status=next_status, source="uisp")); status_events += 1
        item.device_type = device_type; item.display_name = identity.get("displayName") or identity.get("name") or item.display_name; item.management_ip = (source.get("ipAddress") or "").split("/")[0] or None; item.mac_address = normalize_mac_address(identity.get("mac")); item.current_status = next_status; item.last_seen_at = last_seen; item.last_synced_at = now; item.observed_details = details; item.offline_since = item.offline_since if next_status == NetworkDeviceStatus.offline else None
        if next_status == NetworkDeviceStatus.offline and item.offline_since is None: item.offline_since = now
        inventory_created += sync_inventory_asset(db, item=item, identity=identity, device_type=device_type)
        services_linked += link_matching_service(db, item)
    db.commit()
    return {"created": created, "updated": updated, "status_events": status_events, "inventory_created": inventory_created, "services_linked": services_linked}
