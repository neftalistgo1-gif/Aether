from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import String, cast, or_, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.customer import Customer
from app.schemas.customer import CustomerCreate, CustomerRead, CustomerUpdate

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

    for field_name, value in update.model_dump(exclude_unset=True).items():
        setattr(customer, field_name, value)

    db.commit()
    db.refresh(customer)
    return customer
