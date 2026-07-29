import os
import re
from datetime import datetime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.models.mikrotik import NetworkCommandStatus, NetworkControlAction


class MikrotikRouterCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    endpoint_url: str = Field(min_length=8, max_length=500)
    suspended_address_list: str = Field(min_length=1, max_length=100)
    credential_key: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{1,49}$")
    enabled: bool = False
    verify_tls: bool = True

    @field_validator("endpoint_url")
    @classmethod
    def require_https(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        if not normalized.lower().startswith("https://"):
            raise ValueError("endpoint_url must use HTTPS")
        return normalized


class MikrotikRouterRead(MikrotikRouterCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    credentials_configured: bool
    created_at: datetime
    updated_at: datetime


class MikrotikRouterUpdate(BaseModel):
    endpoint_url: str | None = Field(default=None, min_length=8, max_length=500)
    suspended_address_list: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    credential_key: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z][A-Za-z0-9_]{1,49}$",
    )
    enabled: bool | None = None
    verify_tls: bool | None = None

    @field_validator("endpoint_url")
    @classmethod
    def require_https(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().rstrip("/")
        if not normalized.lower().startswith("https://"):
            raise ValueError("endpoint_url must use HTTPS")
        return normalized


class NetworkControlRequest(BaseModel):
    requested_by: str = Field(min_length=2, max_length=150)
    idempotency_key: str = Field(min_length=8, max_length=100)
    dry_run: bool = True
    preflight_command_id: UUID | None = None

    @model_validator(mode="after")
    def require_preflight_for_live_execution(self):
        if self.dry_run and self.preflight_command_id is not None:
            raise ValueError("Dry-run commands cannot reference a preflight")
        if not self.dry_run and self.preflight_command_id is None:
            raise ValueError("Live commands require a preflight command")
        return self


class NetworkControlRetry(BaseModel):
    requested_by: str = Field(min_length=2, max_length=150)
    dry_run: bool = False


class NetworkControlCommandRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    idempotency_key: str
    service_id: UUID
    preflight_command_id: UUID | None
    network_assignment_id: UUID
    router_id: UUID
    action: NetworkControlAction
    target_ip: str
    desired_blocked: bool
    dry_run: bool
    status: NetworkCommandStatus
    attempts: int
    requested_by: str
    requested_at: datetime
    executed_at: datetime | None
    verified_at: datetime | None
    changed_router: bool | None
    result_details: dict[str, object] | None
    error_message: str | None


def credentials_configured(credential_key: str) -> bool:
    prefix = re.sub(r"[^A-Za-z0-9_]", "_", credential_key).upper()
    return bool(
        os.getenv(f"MIKROTIK_{prefix}_USERNAME")
        and os.getenv(f"MIKROTIK_{prefix}_PASSWORD")
    )
