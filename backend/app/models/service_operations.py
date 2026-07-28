from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Date,
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


class NetworkOperationResult(str, Enum):
    success = "success"
    failed = "failed"
    manual = "manual"


class EquipmentRecoveryStatus(str, Enum):
    pending = "pending"
    scheduled = "scheduled"
    partial = "partial"
    complete = "complete"
    unrecoverable = "unrecoverable"


class CancellationStatus(str, Enum):
    scheduled = "scheduled"
    executed = "executed"


class Suspension(Base):
    __tablename__ = "suspensions"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    service_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("services.id", ondelete="CASCADE"),
        index=True,
    )
    scheduled_for: Mapped[date] = mapped_column(Date)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    reason: Mapped[str] = mapped_column(Text)
    debt_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    grace_period_elapsed: Mapped[bool] = mapped_column(Boolean)
    extension_checked: Mapped[bool] = mapped_column(Boolean)
    has_active_extension: Mapped[bool] = mapped_column(Boolean)
    notification_sent: Mapped[bool] = mapped_column(Boolean)
    notification_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    performed_by: Mapped[str] = mapped_column(String(150))
    mikrotik_result: Mapped[NetworkOperationResult] = mapped_column(
        SqlEnum(
            NetworkOperationResult,
            name="network_operation_result",
            native_enum=False,
            validate_strings=True,
        )
    )
    mikrotik_details: Mapped[str | None] = mapped_column(Text, nullable=True)

    service: Mapped["Service"] = relationship(back_populates="suspensions")
    reactivations: Mapped[list["Reactivation"]] = relationship(
        back_populates="suspension",
        cascade="all, delete-orphan",
        order_by="Reactivation.executed_at",
        lazy="selectin",
    )


class Reactivation(Base):
    __tablename__ = "reactivations"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    suspension_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("suspensions.id", ondelete="CASCADE"),
        index=True,
    )
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    reason: Mapped[str] = mapped_column(Text)
    authorized_by: Mapped[str] = mapped_column(String(150))
    performed_by: Mapped[str] = mapped_column(String(150))
    debt_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    mikrotik_result: Mapped[NetworkOperationResult] = mapped_column(
        SqlEnum(
            NetworkOperationResult,
            name="network_operation_result",
            native_enum=False,
            validate_strings=True,
        )
    )
    mikrotik_details: Mapped[str | None] = mapped_column(Text, nullable=True)

    suspension: Mapped[Suspension] = relationship(
        back_populates="reactivations"
    )


class Cancellation(Base):
    __tablename__ = "cancellations"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    service_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("services.id", ondelete="RESTRICT"),
        unique=True,
        index=True,
    )
    requester_customer_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        index=True,
    )
    requested_at: Mapped[date] = mapped_column(Date)
    effective_date: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(Text)
    folio: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    pending_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    credit_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    equipment_recovery_status: Mapped[
        EquipmentRecoveryStatus
    ] = mapped_column(
        SqlEnum(
            EquipmentRecoveryStatus,
            name="equipment_recovery_status",
            native_enum=False,
            validate_strings=True,
        ),
        default=EquipmentRecoveryStatus.pending,
    )
    equipment_pending_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    registered_by: Mapped[str] = mapped_column(String(150))
    status: Mapped[CancellationStatus] = mapped_column(
        SqlEnum(
            CancellationStatus,
            name="cancellation_status",
            native_enum=False,
            validate_strings=True,
        )
    )
    executed_by: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )
    executed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    service: Mapped["Service"] = relationship(back_populates="cancellation")


from app.models.service import Service
