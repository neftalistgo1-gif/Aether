from datetime import date, datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.extension import ExtensionStatus


class ExtensionCreate(BaseModel):
    original_due_date: date
    promised_date: date
    reason: str = Field(min_length=3, max_length=1000)
    authorized_by: str = Field(min_length=2, max_length=150)
    evidence_reference: str = Field(min_length=3, max_length=500)
    notes: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        if self.promised_date <= self.original_due_date:
            raise ValueError("promised_date must be after original_due_date")
        if self.promised_date < date.today():
            raise ValueError("promised_date cannot be in the past")
        return self


class ExtensionResolve(BaseModel):
    performed_by: str = Field(min_length=2, max_length=150)
    reason: str = Field(min_length=3, max_length=1000)


class ExtensionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    service_id: UUID
    original_due_date: date
    promised_date: date
    reason: str
    authorized_by: str
    evidence_reference: str
    authorized_at: datetime
    status: ExtensionStatus
    resolved_at: datetime | None
    resolved_by: str | None
    resolution_reason: str | None
    notes: str | None
