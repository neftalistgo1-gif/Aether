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
    notification_id: UUID
    performed_by: str = Field(min_length=2, max_length=150)
    mikrotik_result: NetworkOperationResult
    mikrotik_details: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_notification(self) -> Self:
        if self.scheduled_for > date.today():
            raise ValueError(
                "scheduled_for cannot be in the future when executing suspension"
            )
        return self


class SuspensionRead(SuspensionCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    service_id: UUID
    network_command_id: UUID | None
    notification_id: UUID | None = None
    notification_sent: bool
    notification_sent_at: datetime | None
    executed_at: datetime
    debt_snapshot: list[dict[str, object]]


class CoordinatedSuspensionCreate(BaseModel):
    scheduled_for: date
    reason: str = Field(min_length=3, max_length=500)
    debt_amount: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    grace_period_elapsed: bool
    extension_checked: bool
    has_active_extension: bool
    notification_id: UUID
    performed_by: str = Field(min_length=2, max_length=150)
    idempotency_key: str = Field(min_length=8, max_length=100)
    dry_run: bool = True
    preflight_command_id: UUID | None = None

    @model_validator(mode="after")
    def validate_notification(self) -> Self:
        if self.scheduled_for > date.today():
            raise ValueError(
                "scheduled_for cannot be in the future when executing suspension"
            )
        if self.dry_run and self.preflight_command_id is not None:
            raise ValueError("Dry-run operations cannot reference a preflight")
        if not self.dry_run and self.preflight_command_id is None:
            raise ValueError("Live operations require a preflight command")
        return self


class CoordinatedSuspensionRead(BaseModel):
    command: NetworkControlCommandRead
    suspension: SuspensionRead | None


class ReactivationCreate(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
    authorized_by: str = Field(min_length=2, max_length=150)
    performed_by: str = Field(min_length=2, max_length=150)
    debt_amount: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    extension_id: UUID | None = None
    payment_agreement_id: UUID | None = None
    mikrotik_result: NetworkOperationResult
    mikrotik_details: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_authorization_basis(self) -> Self:
        basis_count = sum(
            value is not None
            for value in (
                self.extension_id,
                self.payment_agreement_id,
            )
        )
        if self.debt_amount > 0 and basis_count != 1:
            raise ValueError(
                "Debt reactivation requires exactly one active "
                "extension or payment agreement"
            )
        if self.debt_amount == 0 and basis_count != 0:
            raise ValueError(
                "Settled balance reactivation cannot use a debt agreement"
            )
        return self


class ReactivationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    reason: str
    authorized_by: str
    performed_by: str
    debt_amount: Decimal
    extension_id: UUID | None
    payment_agreement_id: UUID | None
    mikrotik_result: NetworkOperationResult
    mikrotik_details: str | None
    id: UUID
    suspension_id: UUID
    network_command_id: UUID | None
    executed_at: datetime


class CoordinatedReactivationCreate(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
    authorized_by: str = Field(min_length=2, max_length=150)
    performed_by: str = Field(min_length=2, max_length=150)
    debt_amount: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    extension_id: UUID | None = None
    payment_agreement_id: UUID | None = None
    idempotency_key: str = Field(min_length=8, max_length=100)
    dry_run: bool = True
    preflight_command_id: UUID | None = None

    @model_validator(mode="after")
    def validate_authorization_basis(self) -> Self:
        basis_count = sum(
            value is not None
            for value in (
                self.extension_id,
                self.payment_agreement_id,
            )
        )
        if self.debt_amount > 0 and basis_count != 1:
            raise ValueError(
                "Debt reactivation requires exactly one active "
                "extension or payment agreement"
            )
        if self.debt_amount == 0 and basis_count != 0:
            raise ValueError(
                "Settled balance reactivation cannot use a debt agreement"
            )
        if self.dry_run and self.preflight_command_id is not None:
            raise ValueError("Dry-run operations cannot reference a preflight")
        if not self.dry_run and self.preflight_command_id is None:
            raise ValueError("Live operations require a preflight command")
        return self


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
