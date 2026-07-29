from datetime import datetime
from decimal import Decimal
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.incident import IncidentStatus
from app.schemas.payment_allocation import CreditMovementRead


class IncidentCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    tower_name: str | None = Field(default=None, min_length=2, max_length=150)
    access_point_name: str | None = Field(
        default=None,
        min_length=2,
        max_length=150,
    )
    started_at: datetime
    reported_by: str = Field(min_length=2, max_length=150)
    service_ids: list[UUID] = Field(default_factory=list, max_length=1000)
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def require_scope(self) -> Self:
        if not self.service_ids and not self.tower_name and not self.access_point_name:
            raise ValueError(
                "At least one service, tower, or access point is required"
            )
        if len(set(self.service_ids)) != len(self.service_ids):
            raise ValueError("service_ids cannot contain duplicates")
        return self


class IncidentImpactAdd(BaseModel):
    service_id: UUID
    affected_from: datetime
    notes: str | None = Field(default=None, max_length=1000)


class IncidentResolve(BaseModel):
    resolved_at: datetime
    cause: str = Field(min_length=3, max_length=2000)
    responsible: str = Field(min_length=2, max_length=150)


class IncidentImpactRestore(BaseModel):
    restored_at: datetime


class IncidentCompensationCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    authorized_by: str = Field(min_length=2, max_length=150)
    reason: str = Field(min_length=3, max_length=1000)


class IncidentServiceImpactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    service_id: UUID
    customer_id: UUID
    affected_from: datetime
    restored_at: datetime | None
    duration_minutes: int | None
    compensation_amount: Decimal
    compensation_movement_id: UUID | None
    notes: str | None


class IncidentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    tower_name: str | None
    access_point_name: str | None
    started_at: datetime
    resolved_at: datetime | None
    duration_minutes: int | None
    status: IncidentStatus
    cause: str | None
    reported_by: str
    responsible: str | None
    notes: str | None
    registered_at: datetime
    impacts: list[IncidentServiceImpactRead]


class IncidentCompensationRead(BaseModel):
    impact: IncidentServiceImpactRead
    credit_movement: CreditMovementRead
