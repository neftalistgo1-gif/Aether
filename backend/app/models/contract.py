from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Index,
    JSON,
    Numeric,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ContractStatus(str, Enum):
    draft = "draft"
    active = "active"
    terminated = "terminated"
    void = "void"


class EvidenceKind(str, Enum):
    physical = "physical"
    private_digital = "private_digital"


class ContractAmendmentType(str, Enum):
    address_change = "address_change"
    plan_change = "plan_change"


class Contract(Base):
    __tablename__ = "contracts"
    __table_args__ = (
        Index(
            "uq_contracts_active_service",
            "service_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
        CheckConstraint(
            (
                "status <> 'terminated' OR "
                "(terminated_on IS NOT NULL AND termination_folio IS NOT NULL)"
            ),
            name="ck_contracts_terminated_data",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    folio: Mapped[str] = mapped_column(
        String(40),
        unique=True,
        index=True,
    )
    customer_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        index=True,
    )
    service_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("services.id", ondelete="RESTRICT"),
        index=True,
    )
    version: Mapped[str] = mapped_column(String(50))
    start_date: Mapped[date] = mapped_column(Date)
    signed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    signed_by: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )
    evidence_kind: Mapped[EvidenceKind | None] = mapped_column(
        SqlEnum(
            EvidenceKind,
            name="contract_evidence_kind",
            native_enum=False,
            validate_strings=True,
        ),
        nullable=True,
    )
    document_reference: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    document_sha256: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    status: Mapped[ContractStatus] = mapped_column(
        SqlEnum(
            ContractStatus,
            name="contract_status",
            native_enum=False,
            validate_strings=True,
        ),
        default=ContractStatus.draft,
        index=True,
    )
    address_snapshot: Mapped[str] = mapped_column(String(250))
    plan_name_snapshot: Mapped[str] = mapped_column(String(100))
    monthly_price_snapshot: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    payment_day_snapshot: Mapped[int] = mapped_column()
    created_by: Mapped[str] = mapped_column(String(150))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    terminated_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    termination_folio: Mapped[str | None] = mapped_column(
        String(40),
        unique=True,
        nullable=True,
    )
    termination_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    terminated_by: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )
    termination_evidence_kind: Mapped[EvidenceKind | None] = mapped_column(
        SqlEnum(
            EvidenceKind,
            name="contract_evidence_kind",
            native_enum=False,
            validate_strings=True,
        ),
        nullable=True,
    )
    termination_document_reference: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    termination_document_sha256: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    voided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    voided_by: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    amendments: Mapped[list["ContractAmendment"]] = relationship(
        back_populates="contract",
        cascade="all, delete-orphan",
        order_by="ContractAmendment.created_at",
        lazy="selectin",
    )

    @property
    def has_document(self) -> bool:
        return self.document_reference is not None

    @property
    def has_termination_document(self) -> bool:
        return self.termination_document_reference is not None


class ContractAmendment(Base):
    __tablename__ = "contract_amendments"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    contract_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("contracts.id", ondelete="RESTRICT"),
        index=True,
    )
    amendment_type: Mapped[ContractAmendmentType] = mapped_column(
        SqlEnum(
            ContractAmendmentType,
            name="contract_amendment_type",
            native_enum=False,
            validate_strings=True,
        )
    )
    effective_date: Mapped[date] = mapped_column(Date)
    before_data: Mapped[dict[str, object]] = mapped_column(JSON)
    after_data: Mapped[dict[str, object]] = mapped_column(JSON)
    evidence_reference: Mapped[str] = mapped_column(String(500))
    amended_by: Mapped[str] = mapped_column(String(150))
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    contract: Mapped[Contract] = relationship(back_populates="amendments")
