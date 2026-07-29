from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import (
    Date,
    DateTime,
    Boolean,
    CheckConstraint,
    Enum as SqlEnum,
    ForeignKey,
    JSON,
    Index,
    Numeric,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class InstallationType(str, Enum):
    installation = "installation"
    reinstallation = "reinstallation"
    address_change = "address_change"


class CoverageResult(str, Enum):
    viable = "viable"
    special_equipment = "special_equipment"
    out_of_coverage = "out_of_coverage"


class InstallationStatus(str, Enum):
    scheduled = "scheduled"
    completed = "completed"
    cancelled = "cancelled"


class Installation(Base):
    __tablename__ = "installations"
    __table_args__ = (
        CheckConstraint("cost >= 0", name="ck_installations_nonnegative_cost"),
        Index(
            "uq_installations_scheduled_service",
            "service_id",
            unique=True,
            postgresql_where=text("status = 'scheduled'"),
            sqlite_where=text("status = 'scheduled'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    service_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("services.id", ondelete="RESTRICT"),
        index=True,
    )
    charge_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("charges.id", ondelete="RESTRICT"),
        unique=True,
        nullable=True,
    )
    installation_type: Mapped[InstallationType] = mapped_column(
        SqlEnum(InstallationType, name="installation_type", native_enum=False)
    )
    coverage_result: Mapped[CoverageResult] = mapped_column(
        SqlEnum(CoverageResult, name="coverage_result", native_enum=False)
    )
    coverage_checked_by: Mapped[str] = mapped_column(String(150))
    coverage_checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    special_equipment_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_for: Mapped[date | None] = mapped_column(Date, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status: Mapped[InstallationStatus] = mapped_column(
        SqlEnum(InstallationStatus, name="installation_status", native_enum=False),
        index=True,
    )
    cost: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    technicians: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    antenna_photos: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    modem_photos: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    navigation_confirmed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    navigation_confirmed_by: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )
    new_address: Mapped[str | None] = mapped_column(String(250), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    registered_by: Mapped[str] = mapped_column(String(150))
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    schedule_changes: Mapped[list["InstallationScheduleChange"]] = relationship(
        back_populates="installation",
        cascade="all, delete-orphan",
        order_by="InstallationScheduleChange.changed_at",
        lazy="selectin",
    )

    @property
    def antenna_photo_count(self) -> int:
        return len(self.antenna_photos or [])

    @property
    def modem_photo_count(self) -> int:
        return len(self.modem_photos or [])


class InstallationScheduleChange(Base):
    __tablename__ = "installation_schedule_changes"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    installation_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("installations.id", ondelete="CASCADE"),
        index=True,
    )
    previous_date: Mapped[date] = mapped_column(Date)
    new_date: Mapped[date] = mapped_column(Date)
    changed_by: Mapped[str] = mapped_column(String(150))
    reason: Mapped[str] = mapped_column(Text)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    installation: Mapped[Installation] = relationship(back_populates="schedule_changes")
