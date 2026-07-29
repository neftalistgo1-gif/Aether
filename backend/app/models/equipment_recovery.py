from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.service_operations import (
    Cancellation,
    EquipmentRecoveryStatus,
)


class EquipmentRecovery(Base):
    __tablename__ = "equipment_recoveries"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    cancellation_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("cancellations.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    scheduled_for: Mapped[date] = mapped_column(Date)
    assigned_technician: Mapped[str] = mapped_column(String(150))
    expected_equipment: Mapped[list[str]] = mapped_column(JSON)
    status: Mapped[EquipmentRecoveryStatus] = mapped_column(
        String(20),
        default=EquipmentRecoveryStatus.scheduled,
    )
    performed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    performed_by: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )
    recovered_equipment: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    missing_equipment: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    condition_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_references: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    receipt_reference: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    cancellation: Mapped[Cancellation] = relationship()
