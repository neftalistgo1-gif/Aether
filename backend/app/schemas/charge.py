from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.charge import ChargeStatus, ChargeType


class ChargeCreate(BaseModel):
    charge_type: ChargeType
    description: str = Field(min_length=3, max_length=250)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    due_date: date
    generated_by: str = Field(min_length=2, max_length=150)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("description", "generated_by")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        return value.strip()


class MonthlyChargeCreate(BaseModel):
    billing_period: date
    generated_by: str = Field(min_length=2, max_length=150)
    description: str | None = Field(default=None, max_length=250)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("billing_period")
    @classmethod
    def require_month_start(cls, value: date) -> date:
        if value.day != 1:
            raise ValueError("billing_period must be the first day of the month")
        return value


class ChargeCancel(BaseModel):
    cancelled_by: str = Field(min_length=2, max_length=150)
    reason: str = Field(min_length=3, max_length=1000)


class ChargeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    service_id: UUID
    charge_type: ChargeType
    description: str
    amount: Decimal
    outstanding_balance: Decimal
    generated_at: datetime
    due_date: date
    billing_period: date | None
    status: ChargeStatus
    generated_by: str
    notes: str | None
    cancelled_at: datetime | None
    cancelled_by: str | None
    cancellation_reason: str | None


class ServiceBalanceRead(BaseModel):
    service_id: UUID
    as_of: date
    outstanding_balance: Decimal
    overdue_balance: Decimal
    open_charges: int
