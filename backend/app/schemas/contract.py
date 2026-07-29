from datetime import date, datetime
from decimal import Decimal
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.contract import (
    ContractAmendmentType,
    ContractStatus,
    EvidenceKind,
)


class ContractCreate(BaseModel):
    customer_id: UUID
    version: str = Field(min_length=1, max_length=50)
    start_date: date
    created_by: str = Field(min_length=2, max_length=150)
    notes: str | None = Field(default=None, max_length=2000)


class EvidenceData(BaseModel):
    evidence_kind: EvidenceKind
    document_reference: str = Field(min_length=3, max_length=500)
    document_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-fA-F]{64}$",
    )

    @model_validator(mode="after")
    def require_hash_for_digital_evidence(self) -> Self:
        if (
            self.evidence_kind == EvidenceKind.private_digital
            and self.document_sha256 is None
        ):
            raise ValueError(
                "document_sha256 is required for private digital evidence"
            )
        return self


class ContractSign(EvidenceData):
    signed_on: date
    signed_by: str = Field(min_length=2, max_length=150)


class ContractTerminate(EvidenceData):
    terminated_on: date = Field(default_factory=date.today)
    terminated_by: str = Field(min_length=2, max_length=150)
    reason: str = Field(min_length=3, max_length=1000)


class ContractVoid(BaseModel):
    voided_by: str = Field(min_length=2, max_length=150)
    reason: str = Field(min_length=3, max_length=1000)


class ContractAmendmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    contract_id: UUID
    amendment_type: ContractAmendmentType
    effective_date: date
    before_data: dict[str, object]
    after_data: dict[str, object]
    evidence_reference: str
    amended_by: str
    reason: str
    created_at: datetime


class ContractRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    folio: str
    customer_id: UUID
    service_id: UUID
    version: str
    start_date: date
    signed_on: date | None
    signed_by: str | None
    evidence_kind: EvidenceKind | None
    document_sha256: str | None
    has_document: bool
    status: ContractStatus
    address_snapshot: str
    plan_name_snapshot: str
    monthly_price_snapshot: Decimal
    payment_day_snapshot: int
    created_by: str
    created_at: datetime
    notes: str | None
    terminated_on: date | None
    termination_folio: str | None
    termination_reason: str | None
    terminated_by: str | None
    termination_evidence_kind: EvidenceKind | None
    termination_document_sha256: str | None
    has_termination_document: bool
    voided_at: datetime | None
    voided_by: str | None
    void_reason: str | None
    amendments: list[ContractAmendmentRead]
