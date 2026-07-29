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
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CreditMovementType(str, Enum):
    payment_excess = "payment_excess"
    charge_application = "charge_application"
    refund = "refund"
    authorized_adjustment = "authorized_adjustment"


class PaymentAllocation(Base):
    __tablename__ = "payment_allocations"
    __table_args__ = (
        CheckConstraint(
            "amount > 0",
            name="ck_payment_allocations_positive_amount",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    payment_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("payments.id", ondelete="RESTRICT"),
        index=True,
    )
    charge_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("charges.id", ondelete="RESTRICT"),
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    applied_by: Mapped[str] = mapped_column(String(150))


class CreditMovement(Base):
    __tablename__ = "credit_movements"
    __table_args__ = (
        CheckConstraint(
            "amount <> 0",
            name="ck_credit_movements_nonzero_amount",
        ),
        UniqueConstraint(
            "payment_id",
            name="uq_credit_movements_payment_id",
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
    payment_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("payments.id", ondelete="RESTRICT"),
        nullable=True,
    )
    charge_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("charges.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    movement_type: Mapped[CreditMovementType] = mapped_column(
        SqlEnum(
            CreditMovementType,
            name="credit_movement_type",
            native_enum=False,
            validate_strings=True,
        ),
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    performed_by: Mapped[str] = mapped_column(String(150))
    reason: Mapped[str] = mapped_column(Text)
