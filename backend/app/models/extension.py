from datetime import UTC, date, datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, Enum as SqlEnum, ForeignKey, Index, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ExtensionStatus(str, Enum):
    active = "active"
    fulfilled = "fulfilled"
    expired = "expired"
    cancelled = "cancelled"


class Extension(Base):
    __tablename__ = "extensions"
    __table_args__ = (
        Index(
            "uq_extensions_active_service",
            "service_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    customer_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("customers.id", ondelete="RESTRICT"), index=True
    )
    service_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("services.id", ondelete="RESTRICT"), index=True
    )
    original_due_date: Mapped[date] = mapped_column(Date)
    promised_date: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(Text)
    authorized_by: Mapped[str] = mapped_column(String(150))
    evidence_reference: Mapped[str] = mapped_column(String(500))
    authorized_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    status: Mapped[ExtensionStatus] = mapped_column(
        SqlEnum(
            ExtensionStatus,
            name="extension_status",
            native_enum=False,
            validate_strings=True,
        ),
        default=ExtensionStatus.active,
        index=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(150), nullable=True)
    resolution_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    @property
    def has_evidence(self) -> bool:
        return bool(self.evidence_reference)
