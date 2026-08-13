import re
from datetime import date, datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.asset import (
    AssetOwner,
    AssetReturnOutcome,
    AssetStatus,
    AssetType,
)


def normalize_mac_address(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    compact = re.sub(r"[^0-9A-Fa-f]", "", value)
    if len(compact) != 12:
        raise ValueError("mac_address must contain 12 hexadecimal digits")
    return ":".join(
        compact[index : index + 2].upper()
        for index in range(0, 12, 2)
    )


class AssetCreate(BaseModel):
    asset_type: AssetType
    description: str = Field(min_length=2, max_length=150)
    brand: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=150)
    serial_number: str | None = Field(default=None, max_length=100)
    mac_address: str | None = Field(default=None, max_length=17)
    owner: AssetOwner = AssetOwner.amr
    acquired_on: date | None = None
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: str) -> str:
        return value.strip()

    @field_validator("brand", "model", "serial_number", "notes")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("mac_address")
    @classmethod
    def validate_mac_address(cls, value: str | None) -> str | None:
        return normalize_mac_address(value)


class AssetUpdate(BaseModel):
    description: str | None = Field(default=None, min_length=2, max_length=150)
    brand: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=150)
    serial_number: str | None = Field(default=None, max_length=100)
    mac_address: str | None = Field(default=None, max_length=17)
    acquired_on: date | None = None
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("mac_address")
    @classmethod
    def validate_mac_address(cls, value: str | None) -> str | None:
        return normalize_mac_address(value)

    @field_validator("description")
    @classmethod
    def strip_required_description(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("description cannot be null")
        return value.strip()

    @field_validator("brand", "model", "serial_number", "notes")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def validate_partial_update(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        return self


class AssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    internal_code: str
    asset_type: AssetType
    description: str
    device_name: str | None
    management_ip: str | None
    brand: str | None
    model: str | None
    serial_number: str | None
    mac_address: str | None
    owner: AssetOwner
    status: AssetStatus
    acquired_on: date | None
    latest_recovery_id: UUID | None
    recovery_equipment_name: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class AssetNetworkHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    asset_id: UUID
    previous_device_name: str | None
    new_device_name: str | None
    previous_management_ip: str | None
    new_management_ip: str | None
    source: str
    changed_at: datetime


class AssetAssignmentCreate(BaseModel):
    asset_id: UUID
    assigned_by: str = Field(min_length=2, max_length=150)
    condition_on_delivery: str = Field(min_length=3, max_length=2000)
    notes: str | None = Field(default=None, max_length=1000)


class AssetAssignmentReturn(BaseModel):
    returned_by: str = Field(min_length=2, max_length=150)
    condition_on_return: str = Field(min_length=3, max_length=2000)
    outcome: AssetReturnOutcome
    notes: str | None = Field(default=None, max_length=1000)


class AssetAssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    asset_id: UUID
    service_id: UUID
    assigned_at: datetime
    assigned_by: str
    condition_on_delivery: str
    ownership: AssetOwner
    returned_at: datetime | None
    returned_by: str | None
    condition_on_return: str | None
    return_outcome: AssetReturnOutcome | None
    notes: str | None
