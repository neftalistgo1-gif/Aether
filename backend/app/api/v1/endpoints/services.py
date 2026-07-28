from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import String, cast, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models.customer import Customer
from app.models.service import Service, ServiceHolder, ServiceStatus
from app.schemas.service import ServiceCreate, ServiceRead

router = APIRouter(prefix="/api/v1/services", tags=["services"])


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
