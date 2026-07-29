from datetime import date, datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.service_operations import EquipmentRecoveryStatus


def normalize_equipment_list(items: list[str]) -> list[str]:
    normalized = [item.strip() for item in items]
    if any(not item for item in normalized):
        raise ValueError("Equipment names cannot be empty")
    if len(set(item.casefold() for item in normalized)) != len(normalized):
        raise ValueError("Equipment names cannot be duplicated")
    return normalized


class EquipmentRecoveryCreate(BaseModel):
    scheduled_for: date
    assigned_technician: str = Field(min_length=2, max_length=150)
    expected_equipment: list[str] = Field(min_length=1, max_length=20)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("expected_equipment")
    @classmethod
    def validate_expected_equipment(cls, items: list[str]) -> list[str]:
        return normalize_equipment_list(items)


class EquipmentRecoveryComplete(BaseModel):
    performed_by: str = Field(min_length=2, max_length=150)
    recovered_equipment: list[str] = Field(default_factory=list, max_length=20)
    missing_equipment: list[str] = Field(default_factory=list, max_length=20)
    condition_notes: str = Field(min_length=3, max_length=2000)
    evidence_references: list[str] = Field(
        default_factory=list,
        max_length=20,
    )
    receipt_reference: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("recovered_equipment", "missing_equipment")
    @classmethod
    def validate_equipment(cls, items: list[str]) -> list[str]:
        return normalize_equipment_list(items)

    @model_validator(mode="after")
    def validate_classification(self) -> Self:
        recovered = {item.casefold() for item in self.recovered_equipment}
        missing = {item.casefold() for item in self.missing_equipment}
        if recovered & missing:
            raise ValueError(
                "An equipment item cannot be both recovered and missing"
            )
        if not recovered and not missing:
            raise ValueError("At least one equipment item must be classified")
        return self


class EquipmentRecoveryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    cancellation_id: UUID
    scheduled_for: date
    assigned_technician: str
    expected_equipment: list[str]
    status: EquipmentRecoveryStatus
    performed_at: datetime | None
    performed_by: str | None
    recovered_equipment: list[str] | None
    missing_equipment: list[str] | None
    condition_notes: str | None
    evidence_references: list[str] | None
    receipt_reference: str | None
    notes: str | None
    created_at: datetime
