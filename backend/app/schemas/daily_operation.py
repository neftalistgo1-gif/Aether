from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.daily_operation import DailyOperationStatus


class DailyOperationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_date: date = Field(default_factory=date.today)
    dry_run: bool = True


class DailyOperationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID | None = None
    run_date: date
    status: DailyOperationStatus | None = None
    dry_run: bool = False
    monthly_charges_created: int
    extensions_expired: int
    executed_by: str
    completed_at: datetime | None = None
