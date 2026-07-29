from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models.customer import Customer
from app.models.payment import Payment, PaymentStatus, PaymentStatusEvent
from app.models.service import Service, ServiceHolder
from app.schemas.payment import (
    PaymentCreate,
    PaymentDecision,
    PaymentRead,
    PaymentStatusEventRead,
    PaymentVerify,
)

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])


def payment_query():
    return select(Payment).options(selectinload(Payment.events))


def find_payment_or_404(payment_id: UUID, db: Session) -> Payment:
    payment = db.scalar(
        payment_query().where(Payment.id == payment_id)
    )
    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )
    return payment


def ensure_pending(payment: Payment) -> None:
    if payment.status != PaymentStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a pending payment can receive this decision",
        )


def add_status_event(
    payment: Payment,
    target_status: PaymentStatus,
    performed_by: str,
    reason: str,
) -> None:
    previous_status = payment.status
    payment.status = target_status
    payment.events.append(
        PaymentStatusEvent(
            from_status=previous_status,
            to_status=target_status,
            performed_by=performed_by,
            reason=reason,
        )
    )


@router.post(
    "",
    response_model=PaymentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_payment(
    payment_data: PaymentCreate,
    db: Session = Depends(get_db),
) -> Payment:
    if db.get(Customer, payment_data.customer_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )
    if payment_data.service_id is not None:
        service = db.get(Service, payment_data.service_id)
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service not found",
            )
        relationship_exists = db.scalar(
            select(ServiceHolder.id).where(
                ServiceHolder.service_id == service.id,
                ServiceHolder.customer_id == payment_data.customer_id,
            )
        )
        if relationship_exists is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Customer has no holder history for this service",
            )

    payment = Payment(
        status=PaymentStatus.pending,
        **payment_data.model_dump(),
    )
    payment.events.append(
        PaymentStatusEvent(
            from_status=None,
            to_status=PaymentStatus.pending,
            performed_by=payment_data.received_by,
            reason="Payment received pending verification",
        )
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return find_payment_or_404(payment.id, db)


@router.get("", response_model=list[PaymentRead])
def list_payments(
    db: Annotated[Session, Depends(get_db)],
    customer_id: UUID | None = None,
    service_id: UUID | None = None,
    payment_status: PaymentStatus | None = None,
    q: Annotated[
        str | None,
        Query(min_length=2, max_length=150, description="Payment reference"),
    ] = None,
) -> list[Payment]:
    statement = payment_query()
    if customer_id is not None:
        statement = statement.where(Payment.customer_id == customer_id)
    if service_id is not None:
        statement = statement.where(Payment.service_id == service_id)
    if payment_status is not None:
        statement = statement.where(Payment.status == payment_status)
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
                Payment.reference.ilike(pattern, escape="\\"),
                Payment.origin_account_holder.ilike(pattern, escape="\\"),
            )
        )
    statement = statement.order_by(
        Payment.received_at,
        Payment.id,
    )
    return list(db.scalars(statement).unique())


@router.get("/{payment_id}", response_model=PaymentRead)
def get_payment(
    payment_id: UUID,
    db: Session = Depends(get_db),
) -> Payment:
    return find_payment_or_404(payment_id, db)


@router.post("/{payment_id}/verify", response_model=PaymentRead)
def verify_payment(
    payment_id: UUID,
    verification: PaymentVerify,
    db: Session = Depends(get_db),
) -> Payment:
    payment = find_payment_or_404(payment_id, db)
    ensure_pending(payment)
    if (
        verification.confirmed_amount != payment.declared_amount
        and not verification.notes
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Verification notes are required when confirmed and "
                "declared amounts differ"
            ),
        )
    payment.confirmed_amount = verification.confirmed_amount
    payment.verified_by = verification.verified_by
    payment.verified_at = datetime.now(UTC)
    payment.verification_notes = verification.notes
    add_status_event(
        payment,
        PaymentStatus.verified,
        verification.verified_by,
        verification.notes or "Payment amount verified",
    )
    db.commit()
    db.refresh(payment)
    return find_payment_or_404(payment.id, db)


def decide_pending_payment(
    payment_id: UUID,
    decision: PaymentDecision,
    target_status: PaymentStatus,
    db: Session,
) -> Payment:
    payment = find_payment_or_404(payment_id, db)
    ensure_pending(payment)
    add_status_event(
        payment,
        target_status,
        decision.performed_by,
        decision.reason,
    )
    db.commit()
    db.refresh(payment)
    return find_payment_or_404(payment.id, db)


@router.post("/{payment_id}/reject", response_model=PaymentRead)
def reject_payment(
    payment_id: UUID,
    decision: PaymentDecision,
    db: Session = Depends(get_db),
) -> Payment:
    return decide_pending_payment(
        payment_id,
        decision,
        PaymentStatus.rejected,
        db,
    )


@router.post("/{payment_id}/cancel", response_model=PaymentRead)
def cancel_payment(
    payment_id: UUID,
    decision: PaymentDecision,
    db: Session = Depends(get_db),
) -> Payment:
    return decide_pending_payment(
        payment_id,
        decision,
        PaymentStatus.cancelled,
        db,
    )


@router.get(
    "/{payment_id}/events",
    response_model=list[PaymentStatusEventRead],
)
def list_payment_events(
    payment_id: UUID,
    db: Session = Depends(get_db),
) -> list[PaymentStatusEvent]:
    return find_payment_or_404(payment_id, db).events
