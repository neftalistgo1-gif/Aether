from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import String, cast, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models.customer import Customer
from app.models.service import (
    Service,
    ServiceEvent,
    ServiceEventType,
    ServiceHolder,
    ServiceStatus,
)
from app.schemas.service import (
    ServiceCreate,
    ServiceEventRead,
    ServiceRead,
    ServiceTransitionCreate,
    ServiceUpdate,
)

router = APIRouter(prefix="/api/v1/services", tags=["services"])

ALLOWED_STATUS_TRANSITIONS = {
    ServiceStatus.pending: {
        ServiceStatus.active,
        ServiceStatus.cancelled,
    },
    ServiceStatus.active: {
        ServiceStatus.suspended,
        ServiceStatus.cancelled,
    },
    ServiceStatus.suspended: {
        ServiceStatus.active,
        ServiceStatus.cancelled,
    },
    ServiceStatus.cancelled: set(),
}


def service_query():
    return select(Service).options(selectinload(Service.holders))


def find_service_or_404(service_id: UUID, db: Session) -> Service:
    service = db.scalar(service_query().where(Service.id == service_id))
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found",
        )
    return service


@router.post("", response_model=ServiceRead, status_code=status.HTTP_201_CREATED)
def create_service(
    service: ServiceCreate,
    db: Session = Depends(get_db),
) -> Service:
    if db.get(Customer, service.customer_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )

    service_data = service.model_dump(exclude={"customer_id"})
    new_service = Service(**service_data)
    new_service.holders.append(ServiceHolder(customer_id=service.customer_id))
    new_service.events.append(
        ServiceEvent(
            event_type=ServiceEventType.registered,
            from_status=None,
            to_status=ServiceStatus.pending,
            reason="Service registered",
        )
    )
    db.add(new_service)

    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="AMR code is already assigned to a current service",
        ) from error

    db.refresh(new_service)
    return find_service_or_404(new_service.id, db)


@router.get("", response_model=list[ServiceRead])
def list_services(
    db: Annotated[Session, Depends(get_db)],
    q: Annotated[
        str | None,
        Query(
            min_length=2,
            max_length=150,
            description="AMR code, address or plan",
        ),
    ] = None,
    customer_id: UUID | None = None,
    service_status: ServiceStatus | None = None,
) -> list[Service]:
    statement = service_query()

    if q:
        escaped_query = (
            q.strip()
            .replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        pattern = f"%{escaped_query}%"
        statement = statement.where(
            or_(
                Service.amr_code.ilike(pattern, escape="\\"),
                Service.address.ilike(pattern, escape="\\"),
                Service.plan_name.ilike(pattern, escape="\\"),
                cast(Service.monthly_price, String).ilike(pattern, escape="\\"),
            )
        )

    if customer_id is not None:
        statement = statement.join(Service.holders).where(
            ServiceHolder.customer_id == customer_id,
            ServiceHolder.end_date.is_(None),
        )

    if service_status is not None:
        statement = statement.where(Service.status == service_status)

    statement = statement.order_by(Service.amr_code, Service.registered_at)
    return list(db.scalars(statement).unique())


@router.get("/{service_id}", response_model=ServiceRead)
def get_service(
    service_id: UUID,
    db: Session = Depends(get_db),
) -> Service:
    return find_service_or_404(service_id, db)


def json_value(value: object) -> object:
    if isinstance(value, (date, Decimal, Enum)):
        return str(value.value if isinstance(value, Enum) else value)
    return value


@router.patch("/{service_id}", response_model=ServiceRead)
def update_service(
    service_id: UUID,
    update: ServiceUpdate,
    db: Session = Depends(get_db),
) -> Service:
    service = find_service_or_404(service_id, db)
    update_data = update.model_dump(exclude_unset=True, exclude={"reason"})
    changes: dict[str, object] = {}

    for field_name, new_value in update_data.items():
        old_value = getattr(service, field_name)
        if old_value == new_value:
            continue
        changes[field_name] = {
            "from": json_value(old_value),
            "to": json_value(new_value),
        }
        setattr(service, field_name, new_value)

    if not changes:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The update does not change any service value",
        )

    service.events.append(
        ServiceEvent(
            event_type=ServiceEventType.details_updated,
            changes=changes,
            reason=update.reason,
        )
    )
    db.commit()
    db.refresh(service)
    return find_service_or_404(service.id, db)


@router.post(
    "/{service_id}/status-transitions",
    response_model=ServiceRead,
)
def transition_service_status(
    service_id: UUID,
    transition: ServiceTransitionCreate,
    db: Session = Depends(get_db),
) -> Service:
    service = find_service_or_404(service_id, db)
    previous_status = service.status
    allowed_targets = ALLOWED_STATUS_TRANSITIONS[previous_status]

    if transition.target_status not in allowed_targets:
        allowed_values = sorted(item.value for item in allowed_targets)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": (
                    f"Cannot transition from {previous_status.value} "
                    f"to {transition.target_status.value}"
                ),
                "allowed_targets": allowed_values,
            },
        )

    service.status = transition.target_status
    if transition.target_status == ServiceStatus.active:
        service.activation_date = service.activation_date or date.today()
    elif transition.target_status == ServiceStatus.cancelled:
        service.cancellation_date = date.today()

    service.events.append(
        ServiceEvent(
            event_type=ServiceEventType.status_changed,
            from_status=previous_status,
            to_status=transition.target_status,
            reason=transition.reason,
        )
    )
    db.commit()
    db.refresh(service)
    return find_service_or_404(service.id, db)


@router.get(
    "/{service_id}/events",
    response_model=list[ServiceEventRead],
)
def list_service_events(
    service_id: UUID,
    db: Session = Depends(get_db),
) -> list[ServiceEvent]:
    find_service_or_404(service_id, db)
    statement = (
        select(ServiceEvent)
        .where(ServiceEvent.service_id == service_id)
        .order_by(ServiceEvent.occurred_at, ServiceEvent.id)
    )
    return list(db.scalars(statement))
