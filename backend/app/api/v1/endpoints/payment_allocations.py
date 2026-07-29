from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.endpoints.payments import find_payment_or_404
from app.db.session import get_db
from app.models.charge import Charge, ChargeStatus
from app.models.customer import Customer
from app.models.payment import Payment, PaymentStatus
from app.models.payment_allocation import (
    CreditMovement,
    CreditMovementType,
    PaymentAllocation,
)
from app.models.service import Service, ServiceHolder
from app.schemas.payment_allocation import (
    CreditBalanceRead,
    CreditMovementRead,
    CreditRefundCreate,
    PaymentAllocationRead,
    PaymentApplicationRead,
    PaymentApply,
)
from app.services.billing import customer_credit_balance

router = APIRouter(prefix="/api/v1", tags=["payment allocations"])

OPEN_CHARGE_STATUSES = {
    ChargeStatus.pending,
    ChargeStatus.partial,
}


def eligible_charges_statement(payment: Payment):
    statement = select(Charge).where(
        Charge.customer_id == payment.customer_id,
        Charge.status.in_(OPEN_CHARGE_STATUSES),
        Charge.outstanding_balance > 0,
    )
    if payment.service_id is not None:
        statement = statement.where(Charge.service_id == payment.service_id)
    return statement


@router.post(
    "/payments/{payment_id}/apply",
    response_model=PaymentApplicationRead,
)
def apply_payment(
    payment_id: UUID,
    application: PaymentApply,
    db: Session = Depends(get_db),
) -> PaymentApplicationRead:
    payment = db.scalar(
        select(Payment)
        .where(Payment.id == payment_id)
        .with_for_update()
    )
    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )
    if payment.status != PaymentStatus.verified:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a verified payment can be applied",
        )
    if payment.applied_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Payment has already been applied",
        )
    if payment.confirmed_amount is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Verified payment has no confirmed amount",
        )

    statement = eligible_charges_statement(payment)
    if application.charge_ids:
        charges_by_id = {
            charge.id: charge
            for charge in db.scalars(
                statement.where(Charge.id.in_(application.charge_ids))
                .with_for_update()
            )
        }
        if set(application.charge_ids) != set(charges_by_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Selected charges must be open and belong to the payment "
                    "customer and service"
                ),
            )
        charges = [
            charges_by_id[charge_id]
            for charge_id in application.charge_ids
        ]
    else:
        charges = list(
            db.scalars(
                statement.order_by(
                    Charge.due_date,
                    Charge.generated_at,
                    Charge.id,
                ).with_for_update()
            )
        )

    remaining = payment.confirmed_amount
    allocations: list[PaymentAllocation] = []
    for charge in charges:
        if remaining <= 0:
            break
        amount = min(remaining, charge.outstanding_balance)
        allocation = PaymentAllocation(
            payment_id=payment.id,
            charge_id=charge.id,
            amount=amount,
            applied_by=application.applied_by,
        )
        db.add(allocation)
        allocations.append(allocation)
        charge.outstanding_balance -= amount
        charge.status = (
            ChargeStatus.paid
            if charge.outstanding_balance == 0
            else ChargeStatus.partial
        )
        remaining -= amount

    credit_generated = remaining
    if credit_generated > 0:
        db.add(
            CreditMovement(
                customer_id=payment.customer_id,
                service_id=payment.service_id,
                payment_id=payment.id,
                movement_type=CreditMovementType.payment_excess,
                amount=credit_generated,
                performed_by=application.applied_by,
                reason="Excess from verified payment",
            )
        )

    payment.applied_at = datetime.now(UTC)
    payment.applied_by = application.applied_by
    payment.application_notes = application.reason
    db.commit()
    for allocation in allocations:
        db.refresh(allocation)
    return PaymentApplicationRead(
        payment_id=payment.id,
        confirmed_amount=payment.confirmed_amount,
        allocated_amount=payment.confirmed_amount - credit_generated,
        credit_generated=credit_generated,
        allocations=allocations,
    )


@router.get(
    "/payments/{payment_id}/allocations",
    response_model=list[PaymentAllocationRead],
)
def list_payment_allocations(
    payment_id: UUID,
    db: Session = Depends(get_db),
) -> list[PaymentAllocation]:
    find_payment_or_404(payment_id, db)
    return list(
        db.scalars(
            select(PaymentAllocation)
            .where(PaymentAllocation.payment_id == payment_id)
            .order_by(
                PaymentAllocation.applied_at,
                PaymentAllocation.id,
            )
        )
    )


@router.get(
    "/charges/{charge_id}/allocations",
    response_model=list[PaymentAllocationRead],
)
def list_charge_allocations(
    charge_id: UUID,
    db: Session = Depends(get_db),
) -> list[PaymentAllocation]:
    if db.get(Charge, charge_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Charge not found",
        )
    return list(
        db.scalars(
            select(PaymentAllocation)
            .where(PaymentAllocation.charge_id == charge_id)
            .order_by(
                PaymentAllocation.applied_at,
                PaymentAllocation.id,
            )
        )
    )


@router.get(
    "/customers/{customer_id}/credit-movements",
    response_model=list[CreditMovementRead],
)
def list_credit_movements(
    customer_id: UUID,
    db: Session = Depends(get_db),
) -> list[CreditMovement]:
    if db.get(Customer, customer_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )
    return list(
        db.scalars(
            select(CreditMovement)
            .where(CreditMovement.customer_id == customer_id)
            .order_by(
                CreditMovement.occurred_at,
                CreditMovement.id,
            )
        )
    )


@router.get(
    "/customers/{customer_id}/credit-balance",
    response_model=CreditBalanceRead,
)
def get_credit_balance(
    customer_id: UUID,
    db: Session = Depends(get_db),
) -> CreditBalanceRead:
    if db.get(Customer, customer_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )
    return CreditBalanceRead(
        customer_id=customer_id,
        balance=customer_credit_balance(customer_id, db),
    )


@router.post(
    "/customers/{customer_id}/credit-refunds",
    response_model=CreditMovementRead,
    status_code=status.HTTP_201_CREATED,
)
def refund_credit(
    customer_id: UUID,
    refund: CreditRefundCreate,
    db: Session = Depends(get_db),
) -> CreditMovement:
    if db.get(Customer, customer_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )
    if refund.service_id is not None:
        if db.get(Service, refund.service_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service not found",
            )
        relationship_exists = db.scalar(
            select(ServiceHolder.id).where(
                ServiceHolder.service_id == refund.service_id,
                ServiceHolder.customer_id == customer_id,
            )
        )
        if relationship_exists is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Customer has no holder history for this service",
            )
    balance = customer_credit_balance(customer_id, db)
    if refund.amount > balance:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Refund exceeds available credit balance",
        )
    movement = CreditMovement(
        customer_id=customer_id,
        service_id=refund.service_id,
        movement_type=CreditMovementType.refund,
        amount=-refund.amount,
        performed_by=refund.performed_by,
        reason=refund.reason,
    )
    db.add(movement)
    db.commit()
    db.refresh(movement)
    return movement
