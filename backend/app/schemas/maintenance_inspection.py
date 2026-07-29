import re
from datetime import UTC, datetime
from enum import Enum
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.maintenance_inspection import InspectionResult


class InspectionState(str, Enum):
    quarantine = "quarantine"
    ready_for_reuse = "ready_for_reuse"
    needs_repair = "needs_repair"
    defective = "defective"
    discarded = "discarded"


class InspectionTest(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    passed: bool
    notes: str | None = Field(default=None, max_length=1000)


class MaintenanceInspectionCreate(BaseModel):
    equipment_name: str = Field(min_length=2, max_length=150)
    technician: str = Field(min_length=2, max_length=150)
    inspected_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )
    serial_number: str | None = Field(default=None, max_length=100)
    mac_address: str | None = Field(default=None, max_length=17)
    model: str | None = Field(default=None, max_length=150)
    cleaning_performed: bool
    cleaning_notes: str | None = Field(default=None, max_length=2000)
    tests: list[InspectionTest] = Field(min_length=1, max_length=30)
    repairs_performed: list[str] = Field(default_factory=list, max_length=30)
    evidence_references: list[str] = Field(default_factory=list, max_length=20)
    result: InspectionResult
    decision_reason: str = Field(min_length=3, max_length=2000)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("equipment_name", "technician")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        return value.strip()

    @field_validator(
        "serial_number",
        "model",
        "cleaning_notes",
        "notes",
    )
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("mac_address")
    @classmethod
    def normalize_mac_address(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        compact = re.sub(r"[^0-9A-Fa-f]", "", value)
        if len(compact) != 12:
            raise ValueError("mac_address must contain 12 hexadecimal digits")
        return ":".join(
            compact[index : index + 2].upper()
            for index in range(0, 12, 2)
        )

    @field_validator("repairs_performed", "evidence_references")
    @classmethod
    def normalize_string_lists(cls, items: list[str]) -> list[str]:
        normalized = [item.strip() for item in items]
        if any(not item for item in normalized):
            raise ValueError("List items cannot be empty")
        if len(set(item.casefold() for item in normalized)) != len(normalized):
            raise ValueError("List items cannot be duplicated")
        return normalized

    @model_validator(mode="after")
    def validate_safe_release(self) -> Self:
        test_names = [test.name.strip().casefold() for test in self.tests]
        if len(set(test_names)) != len(test_names):
            raise ValueError("Test names cannot be duplicated")
        if self.result == InspectionResult.ready_for_reuse:
            if not self.cleaning_performed:
                raise ValueError(
                    "Cleaning is required before equipment can be reused"
                )
            if not all(test.passed for test in self.tests):
                raise ValueError(
                    "All tests must pass before equipment can be reused"
                )
        return self


class MaintenanceInspectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    equipment_recovery_id: UUID
    equipment_name: str
    technician: str
    inspected_at: datetime
    serial_number: str | None
    mac_address: str | None
    model: str | None
    cleaning_performed: bool
    cleaning_notes: str | None
    tests: list[InspectionTest]
    repairs_performed: list[str]
    evidence_references: list[str]
    result: InspectionResult
    decision_reason: str
    notes: str | None
    created_at: datetime


class EquipmentInspectionStatus(BaseModel):
    equipment_name: str
    state: InspectionState
    reusable: bool
    latest_inspection_id: UUID | None
    latest_inspected_at: datetime | None
