from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.endpoints.services import find_service_or_404
from app.db.session import get_db
from app.models.charge import Charge, ChargeStatus, ChargeType
from app.models.customer import Customer
from app.models.service import Service, ServiceHolder, ServiceStatus
from app.schemas.charge import (
    ChargeCancel,
    ChargeCreate,
    ChargeRead,
    MonthlyChargeCreate,
    ServiceBalanceRead,
)

router = APIRouter(prefix="/api/v1", tags=["charges"])

OPEN_CHARGE_STATUSES = {
    ChargeStatus.pending,
    ChargeStatus.partial,
}


def month_start(value: date) -> date:
    return value.replace(day=1)


def next_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def find_charge_or_404(charge_id: UUID, db: Session) -> Charge:
    charge = db.get(Charge, charge_id)
    if charge is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Charge not found",
        )
    return charge


def responsible_customer_id(
    service: Service,
    responsibility_date: date,
) -> UUID:
    holder = next(
        (
            item
            for item in service.holders
            if item.start_date <= responsibility_date
            and (
                item.end_date is None
                or item.end_date >= responsibility_date
            )
        ),
        None,
    )
    if holder is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No service holder exists for the charge date",
        )
    return holder.customer_id


def commit_charge(db: Session, conflict_detail: str) -> None:
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=conflict_detail,
        ) from error


@router.post(
    "/services/{service_id}/charges",
    response_model=ChargeRead,
    status_code=status.HTTP_201_CREATED,
)
def create_charge(
    service_id: UUID,
    charge_data: ChargeCreate,
    db: Session = Depends(get_db),
) -> Charge:
    service = find_service_or_404(service_id, db)
    if charge_data.charge_type == ChargeType.monthly:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Use the monthly charge endpoint for monthly billing",
        )
    if service.status == ServiceStatus.cancelled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="New charges cannot be added to a cancelled service",
        )

    charge = Charge(
        customer_id=responsible_customer_id(
            service,
            charge_data.due_date,
        ),
        service_id=service.id,
        outstanding_balance=charge_data.amount,
        status=ChargeStatus.pending,
        **charge_data.model_dump(),
    )
    db.add(charge)
    commit_charge(db, "Charge could not be created")
    db.refresh(charge)
    return charge


@router.post(
    "/services/{service_id}/charges/monthly",
    response_model=ChargeRead,
    status_code=status.HTTP_201_CREATED,
)
def create_monthly_charge(
    service_id: UUID,
    charge_data: MonthlyChargeCreate,
    db: Session = Depends(get_db),
) -> Charge:
    service = find_service_or_404(service_id, db)
    period = charge_data.billing_period
    if period > month_start(date.today()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Future monthly charges cannot be generated",
        )
    if service.activation_date is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Service must be activated before monthly billing",
        )
    first_period = next_month(month_start(service.activation_date))
    if period < first_period:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Billing period precedes the first monthly charge",
                "first_allowed_period": first_period.isoformat(),
            },
        )

    due_date = period.replace(day=service.payment_day)
    if (
        service.cancellation_date is not None
        and due_date > service.cancellation_date
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Billing period is after the effective cancellation",
        )

    charge = Charge(
        customer_id=responsible_customer_id(service, due_date),
        service_id=service.id,
        charge_type=ChargeType.monthly,
        description=(
            charge_data.description
            or f"Monthly service {period:%Y-%m}"
        ),
        amount=service.monthly_price,
        outstanding_balance=service.monthly_price,
        due_date=due_date,
        billing_period=period,
        status=ChargeStatus.pending,
        generated_by=charge_data.generated_by,
        notes=charge_data.notes,
    )
    db.add(charge)
    commit_charge(
        db,
        "Monthly charge already exists for this service and period",
    )
    db.refresh(charge)
    return charge


@router.get(
    "/services/{service_id}/charges",
    response_model=list[ChargeRead],
)
def list_service_charges(
    service_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    charge_status: ChargeStatus | None = None,
    charge_type: ChargeType | None = None,
) -> list[Charge]:
    find_service_or_404(service_id, db)
    statement = select(Charge).where(Charge.service_id == service_id)
    if charge_status is not None:
        statement = statement.where(Charge.status == charge_status)
    if charge_type is not None:
        statement = statement.where(Charge.charge_type == charge_type)
    statement = statement.order_by(
        Charge.due_date,
        Charge.generated_at,
        Charge.id,
    )
    return list(db.scalars(statement))


@router.get(
    "/customers/{customer_id}/charges",
    response_model=list[ChargeRead],
)
def list_customer_charges(
    customer_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    charge_status: ChargeStatus | None = None,
) -> list[Charge]:
    if db.get(Customer, customer_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )
    statement = select(Charge).where(Charge.customer_id == customer_id)
    if charge_status is not None:
        statement = statement.where(Charge.status == charge_status)
    return list(
        db.scalars(
            statement.order_by(
                Charge.due_date,
                Charge.generated_at,
                Charge.id,
            )
        )
    )


@router.get("/charges/{charge_id}", response_model=ChargeRead)
def get_charge(
    charge_id: UUID,
    db: Session = Depends(get_db),
) -> Charge:
    return find_charge_or_404(charge_id, db)


@router.post(
    "/charges/{charge_id}/cancel",
    response_model=ChargeRead,
)
def cancel_charge(
    charge_id: UUID,
    cancellation: ChargeCancel,
    db: Session = Depends(get_db),
) -> Charge:
    charge = find_charge_or_404(charge_id, db)
    if charge.status == ChargeStatus.cancelled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Charge is already cancelled",
        )
    if charge.outstanding_balance != charge.amount:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A charge with payment allocations cannot be cancelled",
        )
    charge.status = ChargeStatus.cancelled
    charge.outstanding_balance = Decimal("0.00")
    charge.cancelled_at = datetime.now(UTC)
    charge.cancelled_by = cancellation.cancelled_by
    charge.cancellation_reason = cancellation.reason
    db.commit()
    db.refresh(charge)
    return charge


@router.get(
    "/services/{service_id}/balance",
    response_model=ServiceBalanceRead,
)
def get_service_balance(
    service_id: UUID,
    db: Session = Depends(get_db),
    as_of: Annotated[date, Query()] = date.today(),
) -> ServiceBalanceRead:
    find_service_or_404(service_id, db)
    open_filter = (
        Charge.service_id == service_id,
        Charge.status.in_(OPEN_CHARGE_STATUSES),
    )
    outstanding = db.scalar(
        select(func.coalesce(func.sum(Charge.outstanding_balance), 0)).where(
            *open_filter
        )
    )
    overdue = db.scalar(
        select(func.coalesce(func.sum(Charge.outstanding_balance), 0)).where(
            *open_filter,
            Charge.due_date < as_of,
        )
    )
    open_charges = db.scalar(
        select(func.count()).select_from(Charge).where(*open_filter)
    )
    return ServiceBalanceRead(
        service_id=service_id,
        as_of=as_of,
        outstanding_balance=Decimal(outstanding or 0),
        overdue_balance=Decimal(overdue or 0),
        open_charges=int(open_charges or 0),
    )
