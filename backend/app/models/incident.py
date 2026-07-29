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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class IncidentStatus(str, Enum):
    open = "open"
    resolved = "resolved"


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (
        CheckConstraint(
            "resolved_at IS NULL OR resolved_at >= started_at",
            name="ck_incidents_valid_period",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    title: Mapped[str] = mapped_column(String(200))
    tower_name: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
        index=True,
    )
    access_point_name: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status: Mapped[IncidentStatus] = mapped_column(
        SqlEnum(
            IncidentStatus,
            name="incident_status",
            native_enum=False,
            validate_strings=True,
        ),
        default=IncidentStatus.open,
        index=True,
    )
    cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    reported_by: Mapped[str] = mapped_column(String(150))
    responsible: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    impacts: Mapped[list["IncidentServiceImpact"]] = relationship(
        back_populates="incident",
        cascade="all, delete-orphan",
        order_by="IncidentServiceImpact.affected_from",
        lazy="selectin",
    )

    @property
    def duration_minutes(self) -> int | None:
        if self.resolved_at is None:
            return None
        return int(
            (as_utc(self.resolved_at) - as_utc(self.started_at))
            .total_seconds()
            // 60
        )


class IncidentServiceImpact(Base):
    __tablename__ = "incident_service_impacts"
    __table_args__ = (
        CheckConstraint(
            "restored_at IS NULL OR restored_at >= affected_from",
            name="ck_incident_impacts_valid_period",
        ),
        CheckConstraint(
            "compensation_amount >= 0",
            name="ck_incident_impacts_nonnegative_compensation",
        ),
        UniqueConstraint(
            "incident_id",
            "service_id",
            name="uq_incident_service_impacts_incident_service",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    incident_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        index=True,
    )
    service_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("services.id", ondelete="RESTRICT"),
        index=True,
    )
    customer_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        index=True,
    )
    affected_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    restored_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    compensation_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=Decimal("0.00"),
    )
    compensation_movement_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("credit_movements.id", ondelete="RESTRICT"),
        unique=True,
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    incident: Mapped[Incident] = relationship(back_populates="impacts")

    @property
    def duration_minutes(self) -> int | None:
        if self.restored_at is None:
            return None
        return int(
            (as_utc(self.restored_at) - as_utc(self.affected_from))
            .total_seconds()
            // 60
        )
