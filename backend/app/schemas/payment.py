from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.payment import PaymentMethod, PaymentStatus


class PaymentCreate(BaseModel):
    customer_id: UUID
    service_id: UUID | None = None
    declared_amount: Decimal = Field(
        gt=0,
        max_digits=12,
        decimal_places=2,
    )
    declared_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )
    method: PaymentMethod
    reference: str | None = Field(default=None, max_length=150)
    proof_reference: str | None = Field(default=None, max_length=500)
    origin_account_holder: str | None = Field(default=None, max_length=150)
    received_by: str = Field(min_length=2, max_length=150)
    notes: str | None = Field(default=None, max_length=1000)


class PaymentVerify(BaseModel):
    confirmed_amount: Decimal = Field(
        gt=0,
        max_digits=12,
        decimal_places=2,
    )
    verified_by: str = Field(min_length=2, max_length=150)
    notes: str | None = Field(default=None, max_length=1000)


class PaymentDecision(BaseModel):
    performed_by: str = Field(min_length=2, max_length=150)
    reason: str = Field(min_length=3, max_length=1000)


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    service_id: UUID | None
    declared_amount: Decimal
    confirmed_amount: Decimal | None
    declared_at: datetime
    received_at: datetime
    method: PaymentMethod
    reference: str | None
    has_proof: bool
    origin_account_holder: str | None
    status: PaymentStatus
    received_by: str
    verified_by: str | None
    verified_at: datetime | None
    verification_notes: str | None
    applied_at: datetime | None
    applied_by: str | None
    application_notes: str | None
    notes: str | None


class PaymentStatusEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    payment_id: UUID
    from_status: PaymentStatus | None
    to_status: PaymentStatus
    performed_by: str
    reason: str
    occurred_at: datetime
