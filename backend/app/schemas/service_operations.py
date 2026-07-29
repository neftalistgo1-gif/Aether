from datetime import date, datetime
from decimal import Decimal
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.service_operations import (
    CancellationStatus,
    EquipmentRecoveryStatus,
    NetworkOperationResult,
)
from app.schemas.mikrotik import NetworkControlCommandRead


class SuspensionCreate(BaseModel):
    scheduled_for: date
    reason: str = Field(min_length=3, max_length=500)
    debt_amount: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    grace_period_elapsed: bool
    extension_checked: bool
    has_active_extension: bool
    notification_sent: bool
    notification_sent_at: datetime | None = None
    performed_by: str = Field(min_length=2, max_length=150)
    mikrotik_result: NetworkOperationResult
    mikrotik_details: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_notification(self) -> Self:
        if self.scheduled_for > date.today():
            raise ValueError(
                "scheduled_for cannot be in the future when executing suspension"
            )
        if self.notification_sent and self.notification_sent_at is None:
            raise ValueError(
                "notification_sent_at is required when notification was sent"
            )
        return self


class SuspensionRead(SuspensionCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    service_id: UUID
    network_command_id: UUID | None
    executed_at: datetime
    debt_snapshot: list[dict[str, object]]


class CoordinatedSuspensionCreate(BaseModel):
    scheduled_for: date
    reason: str = Field(min_length=3, max_length=500)
    debt_amount: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    grace_period_elapsed: bool
    extension_checked: bool
    has_active_extension: bool
    notification_sent: bool
    notification_sent_at: datetime | None = None
    performed_by: str = Field(min_length=2, max_length=150)
    idempotency_key: str = Field(min_length=8, max_length=100)
    dry_run: bool = True

    @model_validator(mode="after")
    def validate_notification(self) -> Self:
        if self.scheduled_for > date.today():
            raise ValueError(
                "scheduled_for cannot be in the future when executing suspension"
            )
        if self.notification_sent and self.notification_sent_at is None:
            raise ValueError(
                "notification_sent_at is required when notification was sent"
            )
        return self


class CoordinatedSuspensionRead(BaseModel):
    command: NetworkControlCommandRead
    suspension: SuspensionRead | None


class ReactivationCreate(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
    authorized_by: str = Field(min_length=2, max_length=150)
    performed_by: str = Field(min_length=2, max_length=150)
    debt_amount: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    mikrotik_result: NetworkOperationResult
    mikrotik_details: str | None = Field(default=None, max_length=1000)


class ReactivationRead(ReactivationCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    suspension_id: UUID
    network_command_id: UUID | None
    executed_at: datetime


class CoordinatedReactivationCreate(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
    authorized_by: str = Field(min_length=2, max_length=150)
    performed_by: str = Field(min_length=2, max_length=150)
    debt_amount: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    idempotency_key: str = Field(min_length=8, max_length=100)
    dry_run: bool = True


class CoordinatedReactivationRead(BaseModel):
    command: NetworkControlCommandRead
    reactivation: ReactivationRead | None


class CancellationCreate(BaseModel):
    requester_customer_id: UUID
    requested_at: date = Field(default_factory=date.today)
    effective_date: date
    reason: str = Field(min_length=3, max_length=500)
    pending_balance: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    credit_balance: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    equipment_pending_notes: str | None = Field(
        default=None,
        max_length=1000,
    )
    registered_by: str = Field(min_length=2, max_length=150)
    notes: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        if self.effective_date < self.requested_at:
            raise ValueError(
                "effective_date cannot be before requested_at"
            )
        return self


class CancellationExecute(BaseModel):
    performed_by: str = Field(min_length=2, max_length=150)


class CancellationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    service_id: UUID
    requester_customer_id: UUID
    requested_at: date
    effective_date: date
    reason: str
    folio: str
    pending_balance: Decimal
    credit_balance: Decimal
    equipment_recovery_status: EquipmentRecoveryStatus
    equipment_pending_notes: str | None
    registered_by: str
    status: CancellationStatus
    executed_by: str | None
    executed_at: datetime | None
    notes: str | None
