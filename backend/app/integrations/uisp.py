import json
import ssl
from datetime import UTC, datetime
from dataclasses import dataclass
from urllib import error, request

from app.core.config import (
    UISP_API_TOKEN,
    UISP_ENDPOINT_URL,
    UISP_TIMEOUT_SECONDS,
    UISP_VERIFY_TLS,
)
from app.models.network_device import (
    DeviceStatusEvent,
    NetworkDevice,
    NetworkDeviceStatus,
    NetworkDeviceType,
)
from sqlalchemy import select


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


def sync_devices(db, devices: list[dict]) -> dict[str, int]:
    created = updated = status_events = 0
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
        item.device_type = device_type; item.display_name = identity.get("displayName") or identity.get("name") or item.display_name; item.management_ip = (source.get("ipAddress") or "").split("/")[0] or None; item.mac_address = identity.get("mac"); item.current_status = next_status; item.last_seen_at = last_seen; item.last_synced_at = now; item.observed_details = details; item.offline_since = item.offline_since if next_status == NetworkDeviceStatus.offline else None
        if next_status == NetworkDeviceStatus.offline and item.offline_since is None: item.offline_since = now
    db.commit()
    return {"created": created, "updated": updated, "status_events": status_events}
