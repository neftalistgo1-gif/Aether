from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.models.service import ServiceEventType, ServiceStatus


class ServiceCreate(BaseModel):
    customer_id: UUID
    amr_code: str = Field(pattern=r"^AMR\d{3,6}$")
    address: str = Field(min_length=5, max_length=250)
    plan_name: str = Field(min_length=2, max_length=100)
    monthly_price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    payment_day: int = Field(ge=1, le=28)
    grace_days: int = Field(default=5, ge=0, le=30)

    @field_validator("amr_code", mode="before")
    @classmethod
    def normalize_amr_code(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value


class ServiceUpdate(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
    address: str | None = Field(default=None, min_length=5, max_length=250)
    plan_name: str | None = Field(default=None, min_length=2, max_length=100)
    monthly_price: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=10,
        decimal_places=2,
    )
    payment_day: int | None = Field(default=None, ge=1, le=28)
    grace_days: int | None = Field(default=None, ge=0, le=30)

    @model_validator(mode="after")
    def validate_partial_update(self) -> Self:
        changed_fields = self.model_fields_set - {"reason"}
        if not changed_fields:
            raise ValueError("At least one service field must be provided")

        for field_name in changed_fields:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")

        return self


class ServiceTransitionCreate(BaseModel):
    target_status: ServiceStatus
    reason: str = Field(min_length=3, max_length=500)


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


class ServiceEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_type: ServiceEventType
    from_status: ServiceStatus | None
    to_status: ServiceStatus | None
    changes: dict[str, object] | None
    reason: str
    occurred_at: datetime
