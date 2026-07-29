from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.asset import Asset
from app.models.equipment_recovery import EquipmentRecovery


class InspectionResult(str, Enum):
    ready_for_reuse = "ready_for_reuse"
    needs_repair = "needs_repair"
    defective = "defective"
    discarded = "discarded"


class MaintenanceInspection(Base):
    __tablename__ = "maintenance_inspections"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    equipment_recovery_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("equipment_recoveries.id", ondelete="CASCADE"),
        index=True,
    )
    asset_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assets.id", ondelete="RESTRICT"),
        index=True,
    )
    equipment_name: Mapped[str] = mapped_column(String(150), index=True)
    technician: Mapped[str] = mapped_column(String(150))
    inspected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    serial_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    mac_address: Mapped[str | None] = mapped_column(
        String(17),
        nullable=True,
    )
    model: Mapped[str | None] = mapped_column(String(150), nullable=True)
    cleaning_performed: Mapped[bool]
    cleaning_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    tests: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    repairs_performed: Mapped[list[str]] = mapped_column(JSON)
    evidence_references: Mapped[list[str]] = mapped_column(JSON)
    result: Mapped[InspectionResult] = mapped_column(
        SqlEnum(
            InspectionResult,
            name="maintenance_inspection_result",
            native_enum=False,
            validate_strings=True,
        )
    )
    decision_reason: Mapped[str] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    equipment_recovery: Mapped[EquipmentRecovery] = relationship()
    asset: Mapped[Asset] = relationship()
