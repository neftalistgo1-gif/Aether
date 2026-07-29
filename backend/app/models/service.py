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
    SmallInteger,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ServiceStatus(str, Enum):
    pending = "pending"
    active = "active"
    suspended = "suspended"
    cancelled = "cancelled"


class ServiceEventType(str, Enum):
    registered = "registered"
    details_updated = "details_updated"
    status_changed = "status_changed"


class Service(Base):
    __tablename__ = "services"
    __table_args__ = (
        CheckConstraint(
            "payment_day BETWEEN 1 AND 28",
            name="ck_services_payment_day",
        ),
        CheckConstraint(
            "grace_days BETWEEN 0 AND 30",
            name="ck_services_grace_days",
        ),
        Index(
            "uq_services_current_amr_code",
            "amr_code",
            unique=True,
            postgresql_where=text("status <> 'cancelled'"),
            sqlite_where=text("status <> 'cancelled'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    amr_code: Mapped[str] = mapped_column(String(9), index=True)
    plan_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("plans.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    address: Mapped[str] = mapped_column(String(250))
    plan_name: Mapped[str] = mapped_column(String(100))
    monthly_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    payment_day: Mapped[int] = mapped_column(SmallInteger)
    grace_days: Mapped[int] = mapped_column(SmallInteger, default=5)
    status: Mapped[ServiceStatus] = mapped_column(
        SqlEnum(
            ServiceStatus,
            name="service_status",
            native_enum=False,
            validate_strings=True,
        ),
        default=ServiceStatus.pending,
    )
    activation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    cancellation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    holders: Mapped[list["ServiceHolder"]] = relationship(
        back_populates="service",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    events: Mapped[list["ServiceEvent"]] = relationship(
        back_populates="service",
        cascade="all, delete-orphan",
        order_by="ServiceEvent.occurred_at",
    )
    suspensions: Mapped[list["Suspension"]] = relationship(
        back_populates="service",
        cascade="all, delete-orphan",
        order_by="Suspension.executed_at",
        lazy="selectin",
    )
    cancellation: Mapped["Cancellation | None"] = relationship(
        back_populates="service",
        uselist=False,
    )

    @property
    def current_customer_id(self) -> UUID | None:
        current_holder = next(
            (holder for holder in self.holders if holder.end_date is None),
            None,
        )
        return current_holder.customer_id if current_holder else None


class ServiceHolder(Base):
    __tablename__ = "service_holders"
    __table_args__ = (
        Index(
            "uq_service_holders_current_service",
            "service_id",
            unique=True,
            postgresql_where=text("end_date IS NULL"),
            sqlite_where=text("end_date IS NULL"),
        ),
    )

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
    customer_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        index=True,
    )
    start_date: Mapped[date] = mapped_column(Date, default=date.today)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    service: Mapped[Service] = relationship(back_populates="holders")


class ServiceEvent(Base):
    __tablename__ = "service_events"

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
    event_type: Mapped[ServiceEventType] = mapped_column(
        SqlEnum(
            ServiceEventType,
            name="service_event_type",
            native_enum=False,
            validate_strings=True,
        )
    )
    from_status: Mapped[ServiceStatus | None] = mapped_column(
        SqlEnum(
            ServiceStatus,
            name="service_status",
            native_enum=False,
            validate_strings=True,
        ),
        nullable=True,
    )
    to_status: Mapped[ServiceStatus | None] = mapped_column(
        SqlEnum(
            ServiceStatus,
            name="service_status",
            native_enum=False,
            validate_strings=True,
        ),
        nullable=True,
    )
    changes: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    service: Mapped[Service] = relationship(back_populates="events")


from app.models.service_operations import Cancellation, Suspension
