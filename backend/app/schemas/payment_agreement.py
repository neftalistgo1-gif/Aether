from datetime import date, datetime
from decimal import Decimal
from typing import Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.models.payment_agreement import PaymentAgreementStatus


class PaymentAgreementCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    terms: str = Field(min_length=3, max_length=2000)
    promised_amount: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=12,
        decimal_places=2,
    )
    promised_date: date | None = None
    installment_count: int | None = Field(default=None, ge=1, le=60)
    authorized_by: str = Field(min_length=2, max_length=150)
    evidence_reference: str | None = Field(
        default=None,
        min_length=3,
        max_length=500,
    )
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("terms", "authorized_by")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value cannot be blank")
        return value

    @model_validator(mode="after")
    def validate_optional_terms(self) -> Self:
        if (
            self.promised_date is not None
            and self.promised_date < date.today()
        ):
            raise ValueError("promised_date cannot be in the past")
        return self


class PaymentAgreementResolve(BaseModel):
    model_config = ConfigDict(extra="forbid")

    performed_by: str = Field(min_length=2, max_length=150)
    reason: str = Field(min_length=3, max_length=1000)

    @field_validator("performed_by", "reason")
    @classmethod
    def strip_resolution_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value cannot be blank")
        return value


class PaymentAgreementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    folio: str
    customer_id: UUID
    service_id: UUID
    terms: str
    promised_amount: Decimal | None
    promised_date: date | None
    installment_count: int | None
    authorized_by: str
    has_evidence: bool
    notes: str | None
    status: PaymentAgreementStatus
    created_at: datetime
    resolved_at: datetime | None
    resolved_by: str | None
    resolution_reason: str | None
