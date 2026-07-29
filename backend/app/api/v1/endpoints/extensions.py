from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.endpoints.services import find_service_or_404
from app.db.session import get_db
from app.models.charge import Charge, ChargeStatus
from app.models.extension import Extension, ExtensionStatus
from app.models.service import ServiceStatus
from app.schemas.extension import ExtensionCreate, ExtensionRead, ExtensionResolve
from app.services.audit import record_audit_event

router = APIRouter(prefix="/api/v1/services", tags=["payment extensions"])


def find_active_extension(
    service_id: UUID,
    db: Session,
    on_date: date | None = None,
) -> Extension | None:
    extension = db.scalar(
        select(Extension).where(
            Extension.service_id == service_id,
            Extension.status == ExtensionStatus.active,
        )
    )
    comparison_date = on_date or date.today()
    if extension is not None and extension.promised_date < comparison_date:
        previous_status = extension.status
        extension.status = ExtensionStatus.expired
        extension.resolved_at = datetime.now(UTC)
        extension.resolution_reason = "Promised payment date elapsed"
        record_audit_event(
            db,
            actor="system",
            action="extension.expired",
            entity_type="Extension",
            entity_id=extension.id,
            reason=extension.resolution_reason,
            before_data={"status": previous_status},
            after_data={"status": extension.status},
        )
        return None
    return extension


@router.post(
    "/{service_id}/extensions",
    response_model=ExtensionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_extension(
    service_id: UUID,
    extension_data: ExtensionCreate,
    db: Session = Depends(get_db),
) -> Extension:
    service = find_service_or_404(service_id, db)
    if service.status not in {ServiceStatus.active, ServiceStatus.suspended}:
        raise HTTPException(status_code=409, detail="Only active or suspended services can receive extensions")
    if find_active_extension(service_id, db) is not None:
        raise HTTPException(status_code=409, detail="Service already has an active extension")
    balance = db.scalar(
        select(func.coalesce(func.sum(Charge.outstanding_balance), 0)).where(
            Charge.service_id == service_id,
            Charge.status.in_({ChargeStatus.pending, ChargeStatus.partial}),
        )
    )
    if Decimal(balance or 0) <= 0:
        raise HTTPException(status_code=409, detail="An extension requires outstanding debt")
    extension = Extension(
        customer_id=service.current_customer_id,
        service_id=service.id,
        status=ExtensionStatus.active,
        **extension_data.model_dump(),
    )
    db.add(extension)
    try:
        db.flush()
        record_audit_event(
            db,
            actor=extension_data.authorized_by,
            action="extension.created",
            entity_type="Extension",
            entity_id=extension.id,
            reason=extension_data.reason,
            after_data={
                "service_id": service.id,
                "original_due_date": extension.original_due_date,
                "promised_date": extension.promised_date,
                "status": extension.status,
            },
        )
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="Service already has an active extension") from error
    db.refresh(extension)
    return extension


@router.get("/{service_id}/extensions", response_model=list[ExtensionRead])
def list_extensions(service_id: UUID, db: Session = Depends(get_db)) -> list[Extension]:
    find_service_or_404(service_id, db)
    find_active_extension(service_id, db)
    db.commit()
    return list(db.scalars(select(Extension).where(Extension.service_id == service_id).order_by(Extension.authorized_at, Extension.id)))


def resolve_extension(
    service_id: UUID,
    extension_id: UUID,
    resolution: ExtensionResolve,
    target: ExtensionStatus,
    db: Session,
) -> Extension:
    find_service_or_404(service_id, db)
    extension = db.scalar(select(Extension).where(Extension.id == extension_id, Extension.service_id == service_id))
    if extension is None:
        raise HTTPException(status_code=404, detail="Extension not found")
    if extension.status != ExtensionStatus.active:
        raise HTTPException(status_code=409, detail="Only an active extension can be resolved")
    previous_status = extension.status
    extension.status = target
    extension.resolved_at = datetime.now(UTC)
    extension.resolved_by = resolution.performed_by
    extension.resolution_reason = resolution.reason
    record_audit_event(
        db,
        actor=resolution.performed_by,
        action=f"extension.{target.value}",
        entity_type="Extension",
        entity_id=extension.id,
        reason=resolution.reason,
        before_data={"status": previous_status},
        after_data={"status": extension.status},
    )
    db.commit()
    db.refresh(extension)
    return extension


@router.post("/{service_id}/extensions/{extension_id}/fulfill", response_model=ExtensionRead)
def fulfill_extension(service_id: UUID, extension_id: UUID, resolution: ExtensionResolve, db: Session = Depends(get_db)) -> Extension:
    return resolve_extension(service_id, extension_id, resolution, ExtensionStatus.fulfilled, db)


@router.post("/{service_id}/extensions/{extension_id}/cancel", response_model=ExtensionRead)
def cancel_extension(service_id: UUID, extension_id: UUID, resolution: ExtensionResolve, db: Session = Depends(get_db)) -> Extension:
    return resolve_extension(service_id, extension_id, resolution, ExtensionStatus.cancelled, db)
