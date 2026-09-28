from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from hashlib import sha256
import logging
from pathlib import Path
import subprocess
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.v1.endpoints.services import find_service_or_404
from app.db.session import get_db
from app.models.contract import Contract, ContractStatus
from app.models.asset import Asset, AssetAssignment
from app.models.charge import Charge, ChargeStatus, ChargeType
from app.models.customer import Customer
from app.models.installation import Installation
from app.models.network_device import NetworkDevice
from app.models.service import ServiceStatus
from app.schemas.contract import (
    ContractCreate,
    ContractGenerate,
    ContractGenerationReadiness,
    ContractRead,
    ContractSign,
    ContractTerminate,
    ContractVoid,
)
from app.services.audit import record_audit_event
from app.core.config import CONTRACT_DOCUMENTS_PATH, CONTRACT_TEMPLATE_PATH
from app.services.contract_docx import parse_service_address, render_contract

router = APIRouter(prefix="/api/v1/services", tags=["contracts"])
logger = logging.getLogger(__name__)
CONTRACT_TEMPLATE_VERSION = "Machote Word v5 - paginación del anexo"
SPANISH_MONTHS = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


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


def find_contract_asset(db: Session, service_id: UUID) -> Asset | None:
    """Prefer UISP inventory, then fall back to a current manual assignment."""
    asset = db.scalar(
        select(Asset)
        .join(NetworkDevice, NetworkDevice.asset_id == Asset.id)
        .where(NetworkDevice.service_id == service_id)
        .order_by(NetworkDevice.updated_at.desc())
        .limit(1)
    )
    if asset is not None:
        return asset
    return db.scalar(
        select(Asset)
        .join(AssetAssignment, AssetAssignment.asset_id == Asset.id)
        .where(
            AssetAssignment.service_id == service_id,
            AssetAssignment.returned_at.is_(None),
        )
        .order_by(AssetAssignment.assigned_at.desc())
        .limit(1)
    )


def spanish_date(value: date) -> str:
    return f"{value.day} de {SPANISH_MONTHS[value.month - 1]} de {value.year}"


def contract_money(value: Decimal, *, multiline: bool = False) -> str:
    amount = f"${value:,.2f}"
    return f"{amount}\nM.N." if multiline else f"{amount} M.N."


def attach_installation_charge(
    db: Session,
    contract: Contract,
    data: ContractGenerate,
) -> None:
    if (
        not data.create_installation_charge
        or data.installation_cost <= 0
        or contract.installation_charge_id is not None
    ):
        return
    charge = Charge(
        customer_id=contract.customer_id,
        service_id=contract.service_id,
        charge_type=ChargeType.installation,
        description=f"Costo de instalación - contrato {contract.folio}",
        amount=data.installation_cost,
        outstanding_balance=data.installation_cost,
        due_date=data.contract_date,
        status=ChargeStatus.pending,
        generated_by=data.requested_by,
        notes=f"Cargo elegido al generar el contrato {contract.id}",
    )
    db.add(charge)
    db.flush()
    contract.installation_charge_id = charge.id


@router.get(
    "/{service_id}/contracts/generation-readiness",
    response_model=ContractGenerationReadiness,
)
def contract_generation_readiness(
    service_id: UUID,
    customer_id: UUID,
    db: Session = Depends(get_db),
) -> ContractGenerationReadiness:
    """Never allow a future PDF renderer to silently print incomplete data."""
    service = find_service_or_404(service_id, db)
    if service.current_customer_id != customer_id:
        raise HTTPException(
            status_code=409,
            detail="El cliente ya no es el titular actual de este servicio",
        )
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")

    missing_fields: list[str] = []
    if service.status == ServiceStatus.cancelled:
        missing_fields.append("El servicio está cancelado")
    if not customer.full_name.strip():
        missing_fields.append("Nombre completo del cliente")
    if not all((customer.given_names, customer.paternal_surname, customer.maternal_surname)):
        missing_fields.append("Nombre(s) y apellidos del cliente")
    if not any(phone.strip() for phone in customer.phones or []):
        missing_fields.append("Teléfono de contacto")
    # A UISP antenna label is never valid evidence of a contractual address.
    if not service.address_is_manual or "pendiente" in service.address.lower():
        missing_fields.append("Domicilio de servicio confirmado")
    if not service.plan_name.strip() or service.monthly_price is None:
        missing_fields.append("Plan contratado y mensualidad")
    if service.payment_day is None:
        missing_fields.append("Día de pago")
    if service.activation_date is None:
        missing_fields.append("Fecha de instalación")

    asset = find_contract_asset(db, service.id)
    if asset is None:
        missing_fields.append("Equipo instalado")
    elif not (asset.model or "").strip():
        missing_fields.append("Modelo del equipo instalado")

    latest_installation = db.scalar(
        select(Installation)
        .where(Installation.service_id == service.id)
        .order_by(Installation.completed_at.desc(), Installation.registered_at.desc())
        .limit(1)
    )
    return ContractGenerationReadiness(
        service_id=service.id,
        customer_id=customer.id,
        can_generate=not missing_fields,
        missing_fields=missing_fields,
        suggested_installation_cost=(latest_installation.cost if latest_installation else None),
    )


@router.post("/{service_id}/contracts/generate", response_model=ContractRead, status_code=201)
def generate_contract(service_id: UUID, data: ContractGenerate, db: Session = Depends(get_db)) -> Contract:
    ready = contract_generation_readiness(service_id, data.customer_id, db)
    if not ready.can_generate or not CONTRACT_TEMPLATE_PATH.is_file():
        raise HTTPException(status_code=409, detail="El expediente o el machote no están listos")
    service = find_service_or_404(service_id, db)
    customer = db.get(Customer, data.customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    if service.status == ServiceStatus.cancelled:
        raise HTTPException(
            status_code=409,
            detail="Cancelled services cannot receive new contracts",
        )
    asset = find_contract_asset(db, service.id)
    if asset is None or not (asset.model or "").strip():
        raise HTTPException(status_code=409, detail="El modelo del equipo no está disponible en Inventario")

    # One row per service/date remains idempotent, but the PDF is regenerated
    # so corrected customer, inventory, plan and installation data are applied.
    existing = db.scalar(
        select(Contract).where(
            Contract.service_id == service.id,
            Contract.start_date == data.contract_date,
        )
    )
    contract_day = service.payment_day
    number = service.amr_code.removeprefix("AMR")
    filename = (
        f"contrato_{service.amr_code}_{data.contract_date.isoformat()}_"
        f"{uuid4().hex[:8]}.pdf"
    )
    output = CONTRACT_DOCUMENTS_PATH / filename
    previous_document = existing.document_reference if existing else None
    address = parse_service_address(service.address)
    try:
        render_contract(
            CONTRACT_TEMPLATE_PATH,
            output,
            {
                "customer_name": customer.full_name,
                "given_names": customer.given_names or customer.full_name,
                "paternal_surname": customer.paternal_surname or "",
                "maternal_surname": customer.maternal_surname or "",
                "phone": next((phone.strip() for phone in customer.phones or [] if phone.strip()), ""),
                "address": service.address,
                "street": address.street,
                "exterior": address.exterior,
                "interior": address.interior,
                "settlement": address.settlement,
                "city": address.city,
                "state": address.state,
                "postal_code": address.postal_code,
                "plan_name": service.plan_name,
                "monthly_price": contract_money(service.monthly_price, multiline=True),
                "payment_day": f"Día {contract_day} de cada mes",
                "equipment_brand": asset.brand or "Ubiquiti",
                "equipment_model": asset.model or "",
                "equipment_serial": asset.serial_number or "N/A",
                "service_code": service.amr_code,
                "installation_cost": contract_money(data.installation_cost),
                "contract_date": data.contract_date.strftime("%d/%m/%Y"),
                "contract_date_long": spanish_date(data.contract_date),
                "annex_date": (
                    f"{data.contract_date.day} días del mes de "
                    f"{SPANISH_MONTHS[data.contract_date.month - 1]} del año {data.contract_date.year}"
                ),
                "contract_number": number,
            },
        )
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        logger.exception(
            "Contract PDF generation failed for service %s",
            service.amr_code,
        )
        raise HTTPException(
            status_code=503,
            detail="No fue posible generar el PDF del contrato. Intenta nuevamente.",
        ) from exc

    if existing:
        before_data = {
            "version": existing.version,
            "document_reference": existing.document_reference,
            "payment_day_snapshot": existing.payment_day_snapshot,
        }
        existing.version = CONTRACT_TEMPLATE_VERSION
        existing.document_reference = filename
        existing.document_sha256 = sha256(output.read_bytes()).hexdigest()
        existing.address_snapshot = service.address
        existing.plan_name_snapshot = service.plan_name
        existing.monthly_price_snapshot = service.monthly_price
        existing.payment_day_snapshot = contract_day
        existing.installation_cost_snapshot = data.installation_cost
        attach_installation_charge(db, existing, data)
        record_audit_event(
            db,
            actor=data.requested_by,
            action="contract.regenerated",
            entity_type="Contract",
            entity_id=existing.id,
            reason="Contract PDF regenerated from current verified data",
            before_data=before_data,
            after_data={
                "version": existing.version,
                "document_reference": existing.document_reference,
                "payment_day_snapshot": existing.payment_day_snapshot,
            },
        )
        try:
            db.commit()
        except Exception:
            db.rollback()
            output.unlink(missing_ok=True)
            raise
        if previous_document and previous_document != filename:
            (CONTRACT_DOCUMENTS_PATH / Path(previous_document).name).unlink(
                missing_ok=True
            )
        db.refresh(existing)
        return existing
    contract = Contract(
        folio=f"CTR-{number}-{data.contract_date:%Y%m%d}",
        customer_id=customer.id,
        service_id=service.id,
        version=CONTRACT_TEMPLATE_VERSION,
        start_date=data.contract_date,
        status=ContractStatus.draft,
        address_snapshot=service.address,
        plan_name_snapshot=service.plan_name,
        monthly_price_snapshot=service.monthly_price,
        payment_day_snapshot=contract_day,
        installation_cost_snapshot=data.installation_cost,
        created_by=data.requested_by,
        document_reference=filename,
        document_sha256=sha256(output.read_bytes()).hexdigest(),
    )
    db.add(contract)
    db.flush()
    attach_installation_charge(db, contract, data)
    record_audit_event(
        db,
        actor=data.requested_by,
        action="contract.generated",
        entity_type="Contract",
        entity_id=contract.id,
        reason="Contract PDF generated from verified service data",
        after_data={
            "folio": contract.folio,
            "service_id": contract.service_id,
            "customer_id": contract.customer_id,
            "document_reference": contract.document_reference,
            "payment_day_snapshot": contract.payment_day_snapshot,
        },
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        output.unlink(missing_ok=True)
        raise
    db.refresh(contract)
    return contract


@router.get("/{service_id}/contracts/{contract_id}/document")
def download_generated_contract(service_id: UUID, contract_id: UUID, db: Session = Depends(get_db)) -> FileResponse:
    contract = find_contract_or_404(service_id, contract_id, db); path = CONTRACT_DOCUMENTS_PATH / (contract.document_reference or "")
    if not contract.document_reference or not path.is_file(): raise HTTPException(status_code=404, detail="Documento no encontrado")
    return FileResponse(path, media_type="application/pdf", filename=path.name)


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
