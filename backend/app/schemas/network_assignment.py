from datetime import datetime
from decimal import Decimal
from ipaddress import ip_address
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class NetworkAssignmentCreate(BaseModel):
    router_name: str = Field(min_length=2, max_length=100)
    ip_address: str = Field(min_length=7, max_length=45)
    tower_name: str = Field(min_length=2, max_length=150)
    access_point_name: str = Field(min_length=2, max_length=150)
    antenna_name: str = Field(min_length=2, max_length=150)
    frequency_mhz: Decimal | None = Field(
        default=None,
        gt=0,
        le=100000,
        max_digits=8,
        decimal_places=3,
    )
    signal_dbm: Decimal | None = Field(
        default=None,
        ge=-150,
        le=0,
        max_digits=6,
        decimal_places=2,
    )
    technician: str = Field(min_length=2, max_length=150)
    change_reason: str = Field(min_length=3, max_length=1000)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator(
        "router_name",
        "tower_name",
        "access_point_name",
        "antenna_name",
        "technician",
        "change_reason",
    )
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("notes")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("ip_address")
    @classmethod
    def normalize_ip_address(cls, value: str) -> str:
        try:
            parsed = ip_address(value.strip())
        except ValueError as error:
            raise ValueError("ip_address must be a valid IPv4 or IPv6 address") from error
        return str(parsed)


class NetworkAssignmentRead(NetworkAssignmentCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    service_id: UUID
    started_at: datetime
    ended_at: datetime | None
