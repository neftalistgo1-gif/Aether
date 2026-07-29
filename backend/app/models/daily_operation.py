from datetime import UTC, date, datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, Enum as SqlEnum, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DailyOperationStatus(str, Enum):
    completed = "completed"


class DailyOperationRun(Base):
    __tablename__ = "daily_operation_runs"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    run_date: Mapped[date] = mapped_column(Date, unique=True, index=True)
    status: Mapped[DailyOperationStatus] = mapped_column(
        SqlEnum(
            DailyOperationStatus,
            name="daily_operation_status",
            native_enum=False,
            validate_strings=True,
        )
    )
    monthly_charges_created: Mapped[int] = mapped_column(Integer)
    extensions_expired: Mapped[int] = mapped_column(Integer)
    executed_by: Mapped[str] = mapped_column(String(150))
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
