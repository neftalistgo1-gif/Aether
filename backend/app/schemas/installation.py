from datetime import date, datetime
from decimal import Decimal
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.installation import (
    CoverageResult,
    InstallationStatus,
    InstallationType,
)


class InstallationCreate(BaseModel):
    installation_type: InstallationType
    coverage_result: CoverageResult
    coverage_checked_by: str = Field(min_length=2, max_length=150)
    coverage_checked_at: datetime
    special_equipment_notes: str | None = Field(default=None, max_length=2000)
    scheduled_for: date | None = None
    cost: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    new_address: str | None = Field(default=None, min_length=5, max_length=250)
    registered_by: str = Field(min_length=2, max_length=150)
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_work(self) -> Self:
        if self.coverage_result == CoverageResult.out_of_coverage:
            if self.scheduled_for is not None or self.cost != 0:
                raise ValueError(
                    "Out-of-coverage work cannot be scheduled or charged"
                )
        elif self.scheduled_for is None:
            raise ValueError("scheduled_for is required for viable coverage")
        if (
            self.coverage_result == CoverageResult.special_equipment
            and not self.special_equipment_notes
        ):
            raise ValueError(
                "special_equipment_notes is required for special equipment"
            )
        if (
            self.installation_type == InstallationType.address_change
            and not self.new_address
        ):
            raise ValueError("new_address is required for an address change")
        return self


class InstallationReschedule(BaseModel):
    new_date: date
    changed_by: str = Field(min_length=2, max_length=150)
    reason: str = Field(min_length=3, max_length=1000)


class InstallationComplete(BaseModel):
    completed_at: datetime
    technicians: list[str] = Field(min_length=1, max_length=3)
    antenna_photos: list[str] = Field(min_length=2, max_length=4)
    modem_photos: list[str] = Field(min_length=1, max_length=4)
    navigation_confirmed: bool
    navigation_confirmed_by: str = Field(min_length=2, max_length=150)
    performed_by: str = Field(min_length=2, max_length=150)
    notes: str | None = Field(default=None, max_length=2000)


class InstallationCancel(BaseModel):
    cancelled_by: str = Field(min_length=2, max_length=150)
    reason: str = Field(min_length=3, max_length=1000)


class InstallationScheduleChangeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    previous_date: date
    new_date: date
    changed_by: str
    reason: str
    changed_at: datetime


class InstallationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    service_id: UUID
    charge_id: UUID | None
    installation_type: InstallationType
    coverage_result: CoverageResult
    coverage_checked_by: str
    coverage_checked_at: datetime
    special_equipment_notes: str | None
    scheduled_for: date | None
    completed_at: datetime | None
    status: InstallationStatus
    cost: Decimal
    technicians: list[str] | None
    antenna_photos: list[str] | None
    modem_photos: list[str] | None
    navigation_confirmed: bool | None
    navigation_confirmed_by: str | None
    new_address: str | None
    notes: str | None
    registered_by: str
    registered_at: datetime
    cancelled_at: datetime | None
    cancellation_reason: str | None
    schedule_changes: list[InstallationScheduleChangeRead]
