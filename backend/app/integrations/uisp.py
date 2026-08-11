import json
import ssl
from dataclasses import dataclass
from urllib import error, request

from app.core.config import (
    UISP_API_TOKEN,
    UISP_ENDPOINT_URL,
    UISP_TIMEOUT_SECONDS,
    UISP_VERIFY_TLS,
)


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
        payload = self._request("/nms/api/v2.1/devices")
        if isinstance(payload, list):
            devices = payload
        elif isinstance(payload, dict):
            devices = payload.get("devices", payload.get("data"))
        else:
            devices = None
        if not isinstance(devices, list):
            raise RuntimeError("UISP devices response has an unsupported shape")
        return UISPConnectionResult(device_count=len(devices))
