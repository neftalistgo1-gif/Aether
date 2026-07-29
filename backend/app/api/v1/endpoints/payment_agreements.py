from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.endpoints.services import find_service_or_404
from app.db.session import get_db
from app.models.charge import Charge, ChargeStatus
from app.models.payment_agreement import (
    PaymentAgreement,
    PaymentAgreementStatus,
)
from app.models.service import ServiceStatus
from app.schemas.payment_agreement import (
    PaymentAgreementCreate,
    PaymentAgreementRead,
    PaymentAgreementResolve,
)
from app.services.audit import record_audit_event

router = APIRouter(
    prefix="/api/v1/services",
    tags=["payment agreements"],
)


def find_payment_agreement_or_404(
    service_id: UUID,
    agreement_id: UUID,
    db: Session,
    for_update: bool = False,
) -> PaymentAgreement:
    statement = select(PaymentAgreement).where(
        PaymentAgreement.id == agreement_id,
        PaymentAgreement.service_id == service_id,
    )
    if for_update:
        statement = statement.with_for_update()
    agreement = db.scalar(statement)
    if agreement is None:
        raise HTTPException(
            status_code=404,
            detail="Payment agreement not found",
        )
    return agreement


def service_outstanding_balance(service_id: UUID, db: Session) -> Decimal:
    balance = db.scalar(
        select(
            func.coalesce(func.sum(Charge.outstanding_balance), 0)
        ).where(
            Charge.service_id == service_id,
            Charge.status.in_(
                {ChargeStatus.pending, ChargeStatus.partial}
            ),
            Charge.outstanding_balance > 0,
        )
    )
    return Decimal(balance or 0)


@router.post(
    "/{service_id}/payment-agreements",
    response_model=PaymentAgreementRead,
    status_code=status.HTTP_201_CREATED,
)
def create_payment_agreement(
    service_id: UUID,
    data: PaymentAgreementCreate,
    db: Session = Depends(get_db),
) -> PaymentAgreement:
    service = find_service_or_404(service_id, db)
    if service.status not in {
        ServiceStatus.active,
        ServiceStatus.suspended,
    }:
        raise HTTPException(
            status_code=409,
            detail=(
                "Only active or suspended services can receive "
                "payment agreements"
            ),
        )
    balance = service_outstanding_balance(service_id, db)
    if balance <= 0:
        raise HTTPException(
            status_code=409,
            detail="A payment agreement requires outstanding debt",
        )
    if data.promised_amount is not None and data.promised_amount > balance:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Promised amount exceeds Aether balance",
                "promised_amount": str(data.promised_amount),
                "outstanding_balance": str(balance),
            },
        )
    agreement = PaymentAgreement(
        folio=f"AGR-{datetime.now(UTC):%Y%m%d}-{uuid4().hex[:8].upper()}",
        customer_id=service.current_customer_id,
        service_id=service.id,
        status=PaymentAgreementStatus.active,
        **data.model_dump(),
    )
    db.add(agreement)
    try:
        db.flush()
        record_audit_event(
            db,
            actor=data.authorized_by,
            action="payment_agreement.created",
            entity_type="PaymentAgreement",
            entity_id=agreement.id,
            reason=data.terms,
            after_data={
                "folio": agreement.folio,
                "customer_id": agreement.customer_id,
                "service_id": agreement.service_id,
                "promised_amount": agreement.promised_amount,
                "promised_date": agreement.promised_date,
                "installment_count": agreement.installment_count,
                "has_evidence": agreement.has_evidence,
                "status": agreement.status,
            },
        )
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Payment agreement folio already exists",
        ) from error
    db.refresh(agreement)
    return agreement


@router.get(
    "/{service_id}/payment-agreements",
    response_model=list[PaymentAgreementRead],
)
def list_payment_agreements(
    service_id: UUID,
    agreement_status: PaymentAgreementStatus | None = None,
    db: Session = Depends(get_db),
) -> list[PaymentAgreement]:
    find_service_or_404(service_id, db)
    statement = select(PaymentAgreement).where(
        PaymentAgreement.service_id == service_id
    )
    if agreement_status is not None:
        statement = statement.where(
            PaymentAgreement.status == agreement_status
        )
    return list(
        db.scalars(
            statement.order_by(
                PaymentAgreement.created_at,
                PaymentAgreement.id,
            )
        )
    )


def resolve_payment_agreement(
    service_id: UUID,
    agreement_id: UUID,
    data: PaymentAgreementResolve,
    target: PaymentAgreementStatus,
    db: Session,
) -> PaymentAgreement:
    agreement = find_payment_agreement_or_404(
        service_id,
        agreement_id,
        db,
        for_update=True,
    )
    if agreement.status != PaymentAgreementStatus.active:
        raise HTTPException(
            status_code=409,
            detail="Only an active payment agreement can be resolved",
        )
    previous_status = agreement.status
    agreement.status = target
    agreement.resolved_at = datetime.now(UTC)
    agreement.resolved_by = data.performed_by
    agreement.resolution_reason = data.reason
    record_audit_event(
        db,
        actor=data.performed_by,
        action=f"payment_agreement.{target.value}",
        entity_type="PaymentAgreement",
        entity_id=agreement.id,
        reason=data.reason,
        before_data={"status": previous_status},
        after_data={"status": agreement.status},
    )
    db.commit()
    db.refresh(agreement)
    return agreement


@router.post(
    "/{service_id}/payment-agreements/{agreement_id}/fulfill",
    response_model=PaymentAgreementRead,
)
def fulfill_payment_agreement(
    service_id: UUID,
    agreement_id: UUID,
    data: PaymentAgreementResolve,
    db: Session = Depends(get_db),
) -> PaymentAgreement:
    return resolve_payment_agreement(
        service_id,
        agreement_id,
        data,
        PaymentAgreementStatus.fulfilled,
        db,
    )


@router.post(
    "/{service_id}/payment-agreements/{agreement_id}/cancel",
    response_model=PaymentAgreementRead,
)
def cancel_payment_agreement(
    service_id: UUID,
    agreement_id: UUID,
    data: PaymentAgreementResolve,
    db: Session = Depends(get_db),
) -> PaymentAgreement:
    return resolve_payment_agreement(
        service_id,
        agreement_id,
        data,
        PaymentAgreementStatus.cancelled,
        db,
    )
