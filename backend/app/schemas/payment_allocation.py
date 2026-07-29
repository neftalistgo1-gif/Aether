from datetime import datetime
from decimal import Decimal
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.payment_allocation import CreditMovementType


class PaymentApply(BaseModel):
    applied_by: str = Field(min_length=2, max_length=150)
    charge_ids: list[UUID] | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def require_reason_for_directed_application(self) -> Self:
        if self.charge_ids and not self.reason:
            raise ValueError(
                "reason is required when selecting specific charges"
            )
        if self.charge_ids and len(set(self.charge_ids)) != len(self.charge_ids):
            raise ValueError("charge_ids cannot contain duplicates")
        return self


class PaymentAllocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    payment_id: UUID
    charge_id: UUID
    amount: Decimal
    applied_at: datetime
    applied_by: str


class PaymentApplicationRead(BaseModel):
    payment_id: UUID
    confirmed_amount: Decimal
    allocated_amount: Decimal
    credit_generated: Decimal
    allocations: list[PaymentAllocationRead]


class CreditMovementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    service_id: UUID | None
    payment_id: UUID | None
    charge_id: UUID | None
    movement_type: CreditMovementType
    amount: Decimal
    occurred_at: datetime
    performed_by: str
    reason: str


class CreditBalanceRead(BaseModel):
    customer_id: UUID
    balance: Decimal


class CreditRefundCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    service_id: UUID | None = None
    performed_by: str = Field(min_length=2, max_length=150)
    reason: str = Field(min_length=3, max_length=1000)
