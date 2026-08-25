from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_authenticated_user
from app.db.session import get_db
from app.models.auth import OperatorUser
from app.models.charge import Charge, ChargeStatus
from app.models.customer import Customer
from app.models.daily_operation import DailyOperationRun
from app.models.extension import Extension, ExtensionStatus
from app.models.network_assignment import NetworkAssignment
from app.models.notification import (
    CustomerNotification,
    NotificationPurpose,
    NotificationStatus,
)
from app.models.service import Service, ServiceStatus
from app.schemas.daily_operation import (
    DailyOperationCreate,
    DailyOperationRead,
    SuspensionCandidateRead,
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


@router.get("/suspension-candidates", response_model=list[SuspensionCandidateRead])
def list_suspension_candidates(
    db: Session = Depends(get_db),
) -> list[SuspensionCandidateRead]:
    """Services that fulfil every commercial prerequisite for a cut today."""
    today = date.today()
    delivered_warning = exists().where(
        CustomerNotification.service_id == Service.id,
        CustomerNotification.customer_id == Charge.customer_id,
        CustomerNotification.purpose == NotificationPurpose.suspension_warning,
        CustomerNotification.status == NotificationStatus.delivered,
    )
    active_extension = exists().where(
        Extension.service_id == Service.id,
        Extension.status == ExtensionStatus.active,
        Extension.promised_date >= today,
    )
    current_assignment = (
        select(NetworkAssignment.ip_address)
        .where(
            NetworkAssignment.service_id == Service.id,
            NetworkAssignment.ended_at.is_(None),
        )
        .limit(1)
        .scalar_subquery()
    )
    rows = db.execute(
        select(
            Service.id,
            Charge.customer_id,
            Customer.full_name,
            Service.amr_code,
            current_assignment.label("ip_address"),
            Charge.due_date,
            Charge.outstanding_balance,
        )
        .join(Charge, Charge.service_id == Service.id)
        .join(Customer, Customer.id == Charge.customer_id)
        .where(
            Service.status == ServiceStatus.active,
            Charge.status.in_({ChargeStatus.pending, ChargeStatus.partial}),
            Charge.outstanding_balance > 0,
            Charge.due_date + Service.grace_days <= today,
            delivered_warning,
            ~active_extension,
        )
        .order_by(Charge.due_date, Service.amr_code)
    ).all()
    return [
        SuspensionCandidateRead(
            service_id=row.id,
            customer_id=row.customer_id,
            customer_name=row.full_name,
            amr_code=row.amr_code,
            ip_address=row.ip_address,
            due_date=row.due_date,
            outstanding_balance=row.outstanding_balance,
        )
        for row in rows
    ]
