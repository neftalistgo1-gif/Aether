from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import (
    Date,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PaymentAgreementStatus(str, Enum):
    active = "active"
    fulfilled = "fulfilled"
    cancelled = "cancelled"


class PaymentAgreement(Base):
    __tablename__ = "payment_agreements"

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
    terms: Mapped[str] = mapped_column(Text)
    promised_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    promised_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
    installment_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    authorized_by: Mapped[str] = mapped_column(String(150))
    evidence_reference: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[PaymentAgreementStatus] = mapped_column(
        SqlEnum(
            PaymentAgreementStatus,
            name="payment_agreement_status",
            native_enum=False,
            validate_strings=True,
        ),
        default=PaymentAgreementStatus.active,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    resolved_by: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )
    resolution_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    @property
    def has_evidence(self) -> bool:
        return bool(self.evidence_reference)
