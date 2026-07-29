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
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ChargeType(str, Enum):
    installation = "installation"
    monthly = "monthly"
    address_change = "address_change"
    equipment_sale = "equipment_sale"
    additional_service = "additional_service"
    adjustment = "adjustment"
    other = "other"


class ChargeStatus(str, Enum):
    pending = "pending"
    partial = "partial"
    paid = "paid"
    cancelled = "cancelled"


class Charge(Base):
    __tablename__ = "charges"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_charges_positive_amount"),
        CheckConstraint(
            "outstanding_balance >= 0 AND outstanding_balance <= amount",
            name="ck_charges_valid_balance",
        ),
        UniqueConstraint(
            "service_id",
            "charge_type",
            "billing_period",
            name="uq_charges_service_type_period",
        ),
        Index(
            "ix_charges_service_due_date",
            "service_id",
            "due_date",
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
    service_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("services.id", ondelete="RESTRICT"),
        index=True,
    )
    charge_type: Mapped[ChargeType] = mapped_column(
        SqlEnum(
            ChargeType,
            name="charge_type",
            native_enum=False,
            validate_strings=True,
        ),
        index=True,
    )
    description: Mapped[str] = mapped_column(String(250))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    outstanding_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    due_date: Mapped[date] = mapped_column(Date, index=True)
    billing_period: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[ChargeStatus] = mapped_column(
        SqlEnum(
            ChargeStatus,
            name="charge_status",
            native_enum=False,
            validate_strings=True,
        ),
        default=ChargeStatus.pending,
        index=True,
    )
    generated_by: Mapped[str] = mapped_column(String(150))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cancelled_by: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )
    cancellation_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
