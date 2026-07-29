from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.plan import PlanStatus


class PlanCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    speed: str = Field(min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    monthly_price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    valid_from: date
    created_by: str = Field(min_length=2, max_length=150)
    reason: str = Field(default="Initial plan price", min_length=3, max_length=1000)


class PlanPriceChange(BaseModel):
    monthly_price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    effective_from: date
    changed_by: str = Field(min_length=2, max_length=150)
    reason: str = Field(min_length=3, max_length=1000)


class PlanDeactivate(BaseModel):
    deactivated_by: str = Field(min_length=2, max_length=150)
    reason: str = Field(min_length=3, max_length=1000)


class PlanPriceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    monthly_price: Decimal
    valid_from: date
    valid_until: date | None
    changed_by: str
    reason: str
    created_at: datetime


class PlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    speed: str
    description: str | None
    status: PlanStatus
    current_price: Decimal | None
    prices: list[PlanPriceRead]
    created_at: datetime
    deactivated_at: datetime | None
    deactivated_by: str | None
    deactivation_reason: str | None
