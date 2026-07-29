from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_authenticated_user
from app.db.session import get_db
from app.models.auth import OperatorUser
from app.models.daily_operation import DailyOperationRun
from app.schemas.daily_operation import (
    DailyOperationCreate,
    DailyOperationRead,
)
from app.services.daily_operations import execute_daily_operations

router = APIRouter(prefix="/api/v1/operations", tags=["daily operations"])


@router.post("/daily", response_model=DailyOperationRead)
def run_daily_operations(
    data: DailyOperationCreate,
    user: OperatorUser = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
) -> DailyOperationRead:
    return execute_daily_operations(
        data.run_date,
        data.dry_run,
        user.display_name,
        db,
    )


@router.get("/daily", response_model=list[DailyOperationRead])
def list_daily_operations(
    db: Session = Depends(get_db),
) -> list[DailyOperationRead]:
    runs = db.scalars(
        select(DailyOperationRun).order_by(
            DailyOperationRun.run_date.desc()
        )
    )
    return [
        DailyOperationRead.model_validate(run).model_copy(
            update={"dry_run": False}
        )
        for run in runs
    ]
