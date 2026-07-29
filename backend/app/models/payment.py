from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PaymentMethod(str, Enum):
    cash = "cash"
    bank_transfer = "bank_transfer"
    bank_deposit = "bank_deposit"
    card = "card"
    other = "other"


class PaymentStatus(str, Enum):
    pending = "pending"
    verified = "verified"
    rejected = "rejected"
    cancelled = "cancelled"


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint(
            "declared_amount > 0",
            name="ck_payments_positive_declared_amount",
        ),
        CheckConstraint(
            "confirmed_amount IS NULL OR confirmed_amount > 0",
            name="ck_payments_positive_confirmed_amount",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    customer_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        index=True,
    )
    service_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("services.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    declared_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    confirmed_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    declared_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    method: Mapped[PaymentMethod] = mapped_column(
        SqlEnum(
            PaymentMethod,
            name="payment_method",
            native_enum=False,
            validate_strings=True,
        )
    )
    reference: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
        index=True,
    )
    proof_reference: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    origin_account_holder: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )
    status: Mapped[PaymentStatus] = mapped_column(
        SqlEnum(
            PaymentStatus,
            name="payment_status",
            native_enum=False,
            validate_strings=True,
        ),
        default=PaymentStatus.pending,
        index=True,
    )
    received_by: Mapped[str] = mapped_column(String(150))
    verified_by: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    verification_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    events: Mapped[list["PaymentStatusEvent"]] = relationship(
        back_populates="payment",
        cascade="all, delete-orphan",
        order_by="PaymentStatusEvent.occurred_at",
        lazy="selectin",
    )


class PaymentStatusEvent(Base):
    __tablename__ = "payment_status_events"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    payment_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("payments.id", ondelete="CASCADE"),
        index=True,
    )
    from_status: Mapped[PaymentStatus | None] = mapped_column(
        SqlEnum(
            PaymentStatus,
            name="payment_status",
            native_enum=False,
            validate_strings=True,
        ),
        nullable=True,
    )
    to_status: Mapped[PaymentStatus] = mapped_column(
        SqlEnum(
            PaymentStatus,
            name="payment_status",
            native_enum=False,
            validate_strings=True,
        )
    )
    performed_by: Mapped[str] = mapped_column(String(150))
    reason: Mapped[str] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    payment: Mapped[Payment] = relationship(back_populates="events")
