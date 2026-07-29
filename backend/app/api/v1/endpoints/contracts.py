from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.v1.endpoints.services import find_service_or_404
from app.db.session import get_db
from app.models.contract import Contract, ContractStatus
from app.models.service import ServiceStatus
from app.schemas.contract import (
    ContractCreate,
    ContractRead,
    ContractSign,
    ContractTerminate,
    ContractVoid,
)
from app.services.audit import record_audit_event

router = APIRouter(prefix="/api/v1/services", tags=["contracts"])


def contract_query():
    return select(Contract).options(selectinload(Contract.amendments))


def find_contract_or_404(
    service_id: UUID,
    contract_id: UUID,
    db: Session,
    for_update: bool = False,
) -> Contract:
    statement = contract_query().where(
        Contract.id == contract_id,
        Contract.service_id == service_id,
    )
    if for_update:
        statement = statement.with_for_update()
    contract = db.scalar(statement)
    if contract is None:
        raise HTTPException(status_code=404, detail="Contract not found")
    return contract


def commit_contract(db: Session, detail: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=detail) from exc


@router.post(
    "/{service_id}/contracts",
    response_model=ContractRead,
    status_code=status.HTTP_201_CREATED,
)
def create_contract(
    service_id: UUID,
    data: ContractCreate,
    db: Session = Depends(get_db),
) -> Contract:
    service = find_service_or_404(service_id, db)
    if service.status == ServiceStatus.cancelled:
        raise HTTPException(
            status_code=409,
            detail="Cancelled services cannot receive new contracts",
        )
    if service.current_customer_id != data.customer_id:
        raise HTTPException(
            status_code=409,
            detail="Contract customer must be the current service holder",
        )
    contract = Contract(
        folio=f"CTR-{date.today():%Y%m%d}-{uuid4().hex[:8].upper()}",
        customer_id=data.customer_id,
        service_id=service.id,
        version=data.version.strip(),
        start_date=data.start_date,
        status=ContractStatus.draft,
        address_snapshot=service.address,
        plan_name_snapshot=service.plan_name,
        monthly_price_snapshot=service.monthly_price,
        payment_day_snapshot=service.payment_day,
        created_by=data.created_by,
        notes=data.notes,
    )
    db.add(contract)
    try:
        db.flush()
        record_audit_event(
            db,
            actor=data.created_by,
            action="contract.created",
            entity_type="Contract",
            entity_id=contract.id,
            reason="Contract draft created",
            after_data={
                "folio": contract.folio,
                "customer_id": contract.customer_id,
                "service_id": contract.service_id,
                "version": contract.version,
                "status": contract.status,
            },
        )
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Contract folio already exists",
        ) from exc
    commit_contract(db, "Contract folio already exists")
    return find_contract_or_404(service.id, contract.id, db)


@router.get(
    "/{service_id}/contracts",
    response_model=list[ContractRead],
)
def list_contracts(
    service_id: UUID,
    contract_status: ContractStatus | None = None,
    db: Session = Depends(get_db),
) -> list[Contract]:
    find_service_or_404(service_id, db)
    statement = contract_query().where(Contract.service_id == service_id)
    if contract_status is not None:
        statement = statement.where(Contract.status == contract_status)
    return list(
        db.scalars(
            statement.order_by(Contract.created_at, Contract.id)
        ).unique()
    )


@router.get(
    "/{service_id}/contracts/{contract_id}",
    response_model=ContractRead,
)
def get_contract(
    service_id: UUID,
    contract_id: UUID,
    db: Session = Depends(get_db),
) -> Contract:
    return find_contract_or_404(service_id, contract_id, db)


@router.post(
    "/{service_id}/contracts/{contract_id}/sign",
    response_model=ContractRead,
)
def sign_contract(
    service_id: UUID,
    contract_id: UUID,
    data: ContractSign,
    db: Session = Depends(get_db),
) -> Contract:
    service = find_service_or_404(service_id, db)
    contract = find_contract_or_404(
        service_id,
        contract_id,
        db,
        for_update=True,
    )
    if contract.status != ContractStatus.draft:
        raise HTTPException(status_code=409, detail="Only drafts can be signed")
    if service.current_customer_id != contract.customer_id:
        raise HTTPException(
            status_code=409,
            detail="Contract customer is no longer the current holder",
        )
    if contract.start_date > date.today():
        raise HTTPException(
            status_code=409,
            detail="Contract cannot activate before its start date",
        )
    if data.signed_on > date.today():
        raise HTTPException(
            status_code=409,
            detail="Signature date cannot be in the future",
        )
    contract.signed_on = data.signed_on
    contract.signed_by = data.signed_by
    contract.evidence_kind = data.evidence_kind
    contract.document_reference = data.document_reference.strip()
    contract.document_sha256 = (
        data.document_sha256.lower()
        if data.document_sha256 is not None
        else None
    )
    contract.status = ContractStatus.active
    record_audit_event(
        db,
        actor=data.signed_by,
        action="contract.signed",
        entity_type="Contract",
        entity_id=contract.id,
        reason="Signed contract evidence registered",
        before_data={"status": ContractStatus.draft},
        after_data={
            "status": contract.status,
            "signed_on": data.signed_on,
            "evidence_kind": data.evidence_kind,
            "document_sha256": contract.document_sha256,
        },
    )
    commit_contract(db, "Service already has an active contract")
    return find_contract_or_404(service_id, contract.id, db)


@router.post(
    "/{service_id}/contracts/{contract_id}/terminate",
    response_model=ContractRead,
)
def terminate_contract(
    service_id: UUID,
    contract_id: UUID,
    data: ContractTerminate,
    db: Session = Depends(get_db),
) -> Contract:
    contract = find_contract_or_404(
        service_id,
        contract_id,
        db,
        for_update=True,
    )
    if contract.status != ContractStatus.active:
        raise HTTPException(
            status_code=409,
            detail="Only active contracts can be terminated",
        )
    if data.terminated_on != date.today():
        raise HTTPException(
            status_code=409,
            detail="Contract termination must be recorded on its effective date",
        )
    contract.status = ContractStatus.terminated
    contract.terminated_on = data.terminated_on
    contract.termination_folio = (
        f"TER-{date.today():%Y%m%d}-{uuid4().hex[:8].upper()}"
    )
    contract.termination_reason = data.reason
    contract.terminated_by = data.terminated_by
    contract.termination_evidence_kind = data.evidence_kind
    contract.termination_document_reference = (
        data.document_reference.strip()
    )
    contract.termination_document_sha256 = (
        data.document_sha256.lower()
        if data.document_sha256 is not None
        else None
    )
    record_audit_event(
        db,
        actor=data.terminated_by,
        action="contract.terminated",
        entity_type="Contract",
        entity_id=contract.id,
        reason=data.reason,
        before_data={"status": ContractStatus.active},
        after_data={
            "status": contract.status,
            "terminated_on": contract.terminated_on,
            "termination_folio": contract.termination_folio,
            "evidence_kind": data.evidence_kind,
        },
    )
    commit_contract(db, "Contract termination folio already exists")
    return find_contract_or_404(service_id, contract.id, db)


@router.post(
    "/{service_id}/contracts/{contract_id}/void",
    response_model=ContractRead,
)
def void_contract(
    service_id: UUID,
    contract_id: UUID,
    data: ContractVoid,
    db: Session = Depends(get_db),
) -> Contract:
    contract = find_contract_or_404(
        service_id,
        contract_id,
        db,
        for_update=True,
    )
    if contract.status != ContractStatus.draft:
        raise HTTPException(
            status_code=409,
            detail="Only draft contracts can be voided",
        )
    contract.status = ContractStatus.void
    contract.voided_at = datetime.now(UTC)
    contract.voided_by = data.voided_by
    contract.void_reason = data.reason
    record_audit_event(
        db,
        actor=data.voided_by,
        action="contract.voided",
        entity_type="Contract",
        entity_id=contract.id,
        reason=data.reason,
        before_data={"status": ContractStatus.draft},
        after_data={"status": contract.status},
    )
    db.commit()
    return find_contract_or_404(service_id, contract.id, db)
