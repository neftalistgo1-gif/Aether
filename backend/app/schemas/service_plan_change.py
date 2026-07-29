from datetime import date, datetime
from decimal import Decimal
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ServicePlanChangeCreate(BaseModel):
    plan_id: UUID
    agreed_monthly_price: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=10,
        decimal_places=2,
    )
    requested_on: date = Field(default_factory=date.today)
    requested_by: str = Field(min_length=2, max_length=150)
    applied_by: str = Field(min_length=2, max_length=150)
    reason: str = Field(min_length=3, max_length=1000)
    custom_price_reason: str | None = Field(
        default=None,
        min_length=3,
        max_length=1000,
    )

    @model_validator(mode="after")
    def require_reason_for_explicit_price(self) -> Self:
        if (
            self.agreed_monthly_price is not None
            and not self.custom_price_reason
        ):
            raise ValueError(
                "custom_price_reason is required for an agreed price"
            )
        return self


class ServicePlanChangeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    service_id: UUID
    previous_plan_id: UUID | None
    new_plan_id: UUID
    previous_plan_name: str
    new_plan_name: str
    previous_monthly_price: Decimal
    new_monthly_price: Decimal
    requested_on: date
    billing_effective_period: date
    requested_by: str
    applied_by: str
    reason: str
    custom_price_reason: str | None
    changed_at: datetime
