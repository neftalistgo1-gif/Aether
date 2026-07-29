from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.contract import (
    Contract,
    ContractAmendment,
    ContractAmendmentType,
    ContractStatus,
)
from app.services.audit import record_audit_event


def active_contract_for_service(
    service_id: UUID,
    db: Session,
    for_update: bool = False,
) -> Contract | None:
    statement = select(Contract).where(
        Contract.service_id == service_id,
        Contract.status == ContractStatus.active,
    )
    if for_update:
        statement = statement.with_for_update()
    return db.scalar(statement)


def amend_active_contract(
    *,
    service,
    amendment_type: ContractAmendmentType,
    before_data: dict[str, object],
    after_data: dict[str, object],
    evidence_reference: str,
    amended_by: str,
    reason: str,
    effective_date: date,
    db: Session,
) -> ContractAmendment | None:
    contract = active_contract_for_service(
        service.id,
        db,
        for_update=True,
    )
    if contract is None:
        return None
    amendment = ContractAmendment(
        contract_id=contract.id,
        amendment_type=amendment_type,
        effective_date=effective_date,
        before_data=before_data,
        after_data=after_data,
        evidence_reference=evidence_reference,
        amended_by=amended_by,
        reason=reason,
    )
    contract.amendments.append(amendment)
    if amendment_type == ContractAmendmentType.address_change:
        contract.address_snapshot = service.address
    elif amendment_type == ContractAmendmentType.plan_change:
        contract.plan_name_snapshot = service.plan_name
        contract.monthly_price_snapshot = service.monthly_price
    db.flush()
    record_audit_event(
        db,
        actor=amended_by,
        action="contract.amended",
        entity_type="Contract",
        entity_id=contract.id,
        reason=reason,
        before_data={
            "amendment_type": amendment_type,
            "values": before_data,
        },
        after_data={
            "amendment_id": amendment.id,
            "values": after_data,
        },
    )
    return amendment
