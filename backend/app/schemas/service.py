from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.service import ServiceStatus


class ServiceCreate(BaseModel):
    customer_id: UUID
    amr_code: str = Field(pattern=r"^AMR\d{3,6}$")
    address: str = Field(min_length=5, max_length=250)
    plan_name: str = Field(min_length=2, max_length=100)
    monthly_price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    payment_day: int = Field(ge=1, le=28)
    grace_days: int = Field(default=5, ge=0, le=30)
    status: ServiceStatus = ServiceStatus.pending
    activation_date: date | None = None

    @field_validator("amr_code", mode="before")
    @classmethod
    def normalize_amr_code(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value


class ServiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    current_customer_id: UUID
    amr_code: str
    address: str
    plan_name: str
    monthly_price: Decimal
    payment_day: int
    grace_days: int
    status: ServiceStatus
    activation_date: date | None
    cancellation_date: date | None
    registered_at: datetime
