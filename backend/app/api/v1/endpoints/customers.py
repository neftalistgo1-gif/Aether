from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import String, cast, or_, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.customer import Customer
from app.schemas.customer import CustomerCreate, CustomerRead, CustomerUpdate
from app.services.audit import record_audit_event

router = APIRouter(prefix="/api/v1/customers", tags=["customers"])


def find_customer_or_404(customer_id: UUID, db: Session) -> Customer:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )
    return customer


@router.post("", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
def create_customer(
    customer: CustomerCreate,
    db: Session = Depends(get_db),
) -> Customer:
    new_customer = Customer(**customer.model_dump())
    db.add(new_customer)
    db.flush()
    record_audit_event(
        db,
        actor="system",
        action="customer.created",
        entity_type="Customer",
        entity_id=new_customer.id,
        reason="Customer registration",
        after_data={
            "full_name": new_customer.full_name,
            "phones": new_customer.phones,
            "email": new_customer.email,
        },
    )
    db.commit()
    db.refresh(new_customer)
    return new_customer


@router.get("", response_model=list[CustomerRead])
def list_customers(
    db: Annotated[Session, Depends(get_db)],
    q: Annotated[
        str | None,
        Query(min_length=2, max_length=150, description="Name or phone"),
    ] = None,
) -> list[Customer]:
    statement = select(Customer)

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
                Customer.full_name.ilike(pattern, escape="\\"),
                cast(Customer.phones, String).ilike(pattern, escape="\\"),
            )
        )

    statement = statement.order_by(Customer.registered_at, Customer.id)
    return list(db.scalars(statement))


@router.get("/{customer_id}", response_model=CustomerRead)
def get_customer(
    customer_id: UUID,
    db: Session = Depends(get_db),
) -> Customer:
    return find_customer_or_404(customer_id, db)


@router.patch("/{customer_id}", response_model=CustomerRead)
def update_customer(
    customer_id: UUID,
    update: CustomerUpdate,
    db: Session = Depends(get_db),
) -> Customer:
    customer = find_customer_or_404(customer_id, db)
    requested_changes = update.model_dump(
        exclude_unset=True,
        exclude={"reason"},
    )
    changes = {
        field_name: value
        for field_name, value in requested_changes.items()
        if getattr(customer, field_name) != value
    }
    if not changes:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No customer data changed",
        )
    before_data = {
        field_name: getattr(customer, field_name)
        for field_name in changes
    }
    for field_name, value in changes.items():
        setattr(customer, field_name, value)
    record_audit_event(
        db,
        actor="system",
        action="customer.updated",
        entity_type="Customer",
        entity_id=customer.id,
        reason=update.reason,
        before_data=before_data,
        after_data={
            field_name: getattr(customer, field_name)
            for field_name in changes
        },
    )
    db.commit()
    db.refresh(customer)
    return customer
