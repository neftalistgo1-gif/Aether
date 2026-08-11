import base64
import json
import os
import ssl
from dataclasses import dataclass
from urllib import error, parse, request

from app.models.mikrotik import MikrotikRouter


@dataclass
class RouterExecutionResult:
    blocked: bool
    changed: bool
    entry_count: int


class RouterOSRestClient:
    def __init__(self, router: MikrotikRouter, *, monitor: bool = False) -> None:
        prefix = router.credential_key.upper()
        monitor_username = os.getenv(f"MIKROTIK_{prefix}_MONITOR_USERNAME")
        monitor_password = os.getenv(f"MIKROTIK_{prefix}_MONITOR_PASSWORD")
        self.username = (
            monitor_username or "aether-monitor"
            if monitor
            else os.getenv(f"MIKROTIK_{prefix}_USERNAME")
        )
        self.password = (
            monitor_password or os.getenv(f"MIKROTIK_{prefix}_PASSWORD")
            if monitor
            else os.getenv(f"MIKROTIK_{prefix}_PASSWORD")
        )
        if not self.username or not self.password:
            raise RuntimeError("MikroTik credentials are not configured")
        self.router = router
        self.timeout = float(os.getenv("MIKROTIK_TIMEOUT_SECONDS", "10"))
        self.ssl_context = ssl.create_default_context()
        if not router.verify_tls:
            self.ssl_context.check_hostname = False
            self.ssl_context.verify_mode = ssl.CERT_NONE

    def _request(self, method: str, path: str, payload=None):
        url = f"{self.router.endpoint_url}{path}"
        token = base64.b64encode(
            f"{self.username}:{self.password}".encode()
        ).decode()
        headers = {"Authorization": f"Basic {token}"}
        data = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload).encode()
        call = request.Request(url, data=data, headers=headers, method=method)
        try:
            with request.urlopen(
                call,
                timeout=self.timeout,
                context=self.ssl_context,
            ) as response:
                body = response.read()
                if not body:
                    return None
                try:
                    return json.loads(body.decode("utf-8"))
                except UnicodeDecodeError:
                    # RouterOS installations may contain legacy comments with
                    # Latin-1 characters in otherwise JSON responses.
                    return json.loads(body.decode("latin-1"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:200]
            raise RuntimeError(
                f"MikroTik request failed: HTTP {exc.code} {detail}"
            ) from exc
        except (error.URLError, TimeoutError, ValueError) as exc:
            raise RuntimeError(
                f"MikroTik request failed: {type(exc).__name__}"
            ) from exc

    def _matching_entries(self, target_ip: str) -> list[dict]:
        entries = self._request(
            "GET",
            "/rest/ip/firewall/address-list",
        )
        return [
            item
            for item in (entries or [])
            if item.get("list") == self.router.suspended_address_list
            and item.get("address") == target_ip
        ]

    def set_blocked(
        self,
        target_ip: str,
        desired_blocked: bool,
        comment: str,
    ) -> RouterExecutionResult:
        existing = self._matching_entries(target_ip)
        changed = False
        if desired_blocked and not existing:
            self._request(
                "PUT",
                "/rest/ip/firewall/address-list",
                {
                    "list": self.router.suspended_address_list,
                    "address": target_ip,
                    "comment": comment,
                },
            )
            changed = True
        elif not desired_blocked and existing:
            for item in existing:
                entry_id = parse.quote(str(item[".id"]), safe="")
                self._request(
                    "DELETE",
                    f"/rest/ip/firewall/address-list/{entry_id}",
                )
            changed = True

        verified = self._matching_entries(target_ip)
        blocked = bool(verified)
        if blocked != desired_blocked:
            raise RuntimeError("MikroTik verification did not match request")
        return RouterExecutionResult(
            blocked=blocked,
            changed=changed,
            entry_count=len(verified),
        )

    def inspect_blocked(self, target_ip: str) -> RouterExecutionResult:
        entries = self._matching_entries(target_ip)
        return RouterExecutionResult(
            blocked=bool(entries),
            changed=False,
            entry_count=len(entries),
        )

    def list_neighbors(self) -> list[dict]:
        return self._request("GET", "/rest/ip/neighbor") or []

    def get_interface_stats(self, interface_name: str) -> dict:
        interfaces = self._request(
            "POST",
            "/rest/interface/print",
            {".proplist": "name,rx-byte,tx-byte"},
        ) or []
        item = next(
            (entry for entry in interfaces if entry.get("name") == interface_name),
            None,
        )
        if item is None:
            raise RuntimeError(f"MikroTik interface not found: {interface_name}")
        return item
