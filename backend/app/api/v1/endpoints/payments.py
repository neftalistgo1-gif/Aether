from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.api.v1.endpoints.mikrotik import control_service_network
from app.models.customer import Customer
from app.models.mikrotik import NetworkControlAction
from app.models.payment import Payment, PaymentStatus, PaymentStatusEvent
from app.models.service import Service, ServiceHolder, ServiceStatus
from app.schemas.payment import (
    PaymentCreate,
    PaymentDecision,
    PaymentRead,
    PaymentStatusEventRead,
    PaymentVerify,
)
from app.schemas.mikrotik import NetworkControlRequest
from app.services.audit import record_audit_event
from app.services.payment_proofs import payment_proof_path, payment_proof_directory

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


def ensure_proof_file_name(filename: str) -> str:
    safe_name = Path(filename).name.strip()
    if not safe_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Receipt file must have a name",
        )
    if len(safe_name) > 150:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Receipt file name is too long",
        )
    return safe_name


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


def trigger_payment_network_action(
    payment: Payment,
    target_status: PaymentStatus,
    performed_by: str,
    db: Session,
) -> None:
    if payment.service_id is None:
        return
    service = db.get(Service, payment.service_id)
    if service is None:
        return
    if target_status == PaymentStatus.verified:
        if service.status != ServiceStatus.suspended:
            return
        action = NetworkControlAction.reactivate
    elif target_status == PaymentStatus.rejected:
        if service.status != ServiceStatus.active:
            return
        action = NetworkControlAction.suspend
    else:
        return
    preflight = control_service_network(
        service.id,
        action,
        NetworkControlRequest(
            requested_by=performed_by,
            idempotency_key=f"payment:{payment.id}:{action.value}:dry-run",
            dry_run=True,
        ),
        db,
    )
    control_service_network(
        service.id,
        action,
        NetworkControlRequest(
            requested_by=performed_by,
            idempotency_key=f"payment:{payment.id}:{action.value}:live",
            dry_run=False,
            preflight_command_id=preflight.id,
        ),
        db,
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
    db.flush()
    record_audit_event(
        db,
        actor=payment_data.received_by,
        action="payment.received",
        entity_type="Payment",
        entity_id=payment.id,
        reason="Payment received pending verification",
        after_data={
            "customer_id": payment.customer_id,
            "service_id": payment.service_id,
            "declared_amount": payment.declared_amount,
            "status": payment.status,
            "method": payment.method,
        },
    )
    db.commit()
    db.refresh(payment)
    return find_payment_or_404(payment.id, db)


@router.post(
    "/receipts",
    response_model=PaymentRead,
    status_code=status.HTTP_201_CREATED,
)
def receive_payment_receipt(
    customer_id: UUID = Form(),
    service_id: UUID | None = Form(default=None),
    declared_amount: str = Form(),
    declared_at: datetime = Form(),
    method: str = Form(),
    reference: str | None = Form(default=None),
    origin_account_holder: str | None = Form(default=None),
    received_by: str = Form(),
    notes: str | None = Form(default=None),
    proof_file: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
) -> Payment:
    payment_data = PaymentCreate(
        customer_id=customer_id,
        service_id=service_id,
        declared_amount=declared_amount,
        declared_at=declared_at,
        method=method,
        reference=reference,
        proof_reference=None,
        origin_account_holder=origin_account_holder,
        received_by=received_by,
        notes=notes,
    )
    payment = create_payment(payment_data, db)

    if proof_file is not None:
        filename = ensure_proof_file_name(proof_file.filename or "")
        proof_directory = payment_proof_directory(payment.id)
        proof_directory.mkdir(parents=True, exist_ok=True)
        target_path = payment_proof_path(payment.id, filename)
        with target_path.open("wb") as target_file:
            target_file.write(proof_file.file.read())
        payment.proof_reference = str(target_path.relative_to(proof_directory.parent))
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


@router.get("/{payment_id}/proof")
def download_payment_proof(
    payment_id: UUID,
    db: Session = Depends(get_db),
):
    payment = find_payment_or_404(payment_id, db)
    if not payment.proof_reference:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment proof not found",
        )
    proof_path = payment_proof_directory(payment.id) / Path(payment.proof_reference).name
    if not proof_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment proof file is missing",
        )
    return FileResponse(proof_path)


@router.post("/{payment_id}/verify", response_model=PaymentRead)
def verify_payment(
    payment_id: UUID,
    verification: PaymentVerify,
    db: Session = Depends(get_db),
) -> Payment:
    payment = find_payment_or_404(payment_id, db)
    ensure_pending(payment)
    before_data = {
        "status": payment.status,
        "declared_amount": payment.declared_amount,
        "confirmed_amount": payment.confirmed_amount,
    }
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
    record_audit_event(
        db,
        actor=verification.verified_by,
        action="payment.verified",
        entity_type="Payment",
        entity_id=payment.id,
        reason=verification.notes or "Payment amount verified",
        before_data=before_data,
        after_data={
            "status": payment.status,
            "declared_amount": payment.declared_amount,
            "confirmed_amount": payment.confirmed_amount,
        },
    )
    trigger_payment_network_action(
        payment,
        PaymentStatus.verified,
        verification.verified_by,
        db,
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
    previous_status = payment.status
    add_status_event(
        payment,
        target_status,
        decision.performed_by,
        decision.reason,
    )
    record_audit_event(
        db,
        actor=decision.performed_by,
        action=f"payment.{target_status.value}",
        entity_type="Payment",
        entity_id=payment.id,
        reason=decision.reason,
        before_data={"status": previous_status},
        after_data={"status": payment.status},
    )
    trigger_payment_network_action(
        payment,
        target_status,
        decision.performed_by,
        db,
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
