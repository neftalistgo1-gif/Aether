from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.v1.endpoints.services import find_service_or_404
from app.db.session import get_db
from app.models.charge import Charge, ChargeStatus, ChargeType
from app.models.installation import (
    CoverageResult,
    Installation,
    InstallationScheduleChange,
    InstallationStatus,
    InstallationType,
)
from app.models.service import (
    ServiceEvent,
    ServiceEventType,
    ServiceStatus,
)
from app.schemas.installation import (
    InstallationCancel,
    InstallationComplete,
    InstallationCreate,
    InstallationRead,
    InstallationReschedule,
)
from app.services.audit import record_audit_event

router = APIRouter(prefix="/api/v1/services", tags=["installations"])


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def installation_query():
    return select(Installation).options(
        selectinload(Installation.schedule_changes)
    )


def find_installation_or_404(
    service_id: UUID,
    installation_id: UUID,
    db: Session,
    for_update: bool = False,
) -> Installation:
    statement = installation_query().where(
        Installation.id == installation_id,
        Installation.service_id == service_id,
    )
    if for_update:
        statement = statement.with_for_update()
    installation = db.scalar(statement)
    if installation is None:
        raise HTTPException(status_code=404, detail="Installation not found")
    return installation


@router.post(
    "/{service_id}/installations",
    response_model=InstallationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_installation(
    service_id: UUID,
    data: InstallationCreate,
    db: Session = Depends(get_db),
) -> Installation:
    service = find_service_or_404(service_id, db)
    if service.status == ServiceStatus.cancelled:
        raise HTTPException(
            status_code=409,
            detail="Cancelled services cannot receive installation work",
        )
    if as_utc(data.coverage_checked_at) > datetime.now(UTC):
        raise HTTPException(
            status_code=409,
            detail="Coverage check cannot be in the future",
        )
    if data.scheduled_for is not None and data.scheduled_for < date.today():
        raise HTTPException(
            status_code=409,
            detail="Installation cannot be scheduled in the past",
        )
    if (
        data.installation_type == InstallationType.installation
        and service.status != ServiceStatus.pending
    ):
        raise HTTPException(
            status_code=409,
            detail="Initial installation requires a pending service",
        )
    if (
        data.installation_type
        in {InstallationType.reinstallation, InstallationType.address_change}
        and service.status != ServiceStatus.active
    ):
        raise HTTPException(
            status_code=409,
            detail="This work type requires an active service",
        )

    rejected = data.coverage_result == CoverageResult.out_of_coverage
    installation = Installation(
        service_id=service.id,
        status=(
            InstallationStatus.cancelled
            if rejected
            else InstallationStatus.scheduled
        ),
        cancellation_reason=(
            "Coverage assessment was not viable" if rejected else None
        ),
        cancelled_at=datetime.now(UTC) if rejected else None,
        **data.model_dump(),
    )
    db.add(installation)
    try:
        db.flush()
        if not rejected and data.cost > 0:
            charge = Charge(
                customer_id=service.current_customer_id,
                service_id=service.id,
                charge_type=(
                    ChargeType.address_change
                    if data.installation_type == InstallationType.address_change
                    else ChargeType.installation
                ),
                description=f"{data.installation_type.value} work",
                amount=data.cost,
                outstanding_balance=data.cost,
                due_date=data.scheduled_for,
                status=ChargeStatus.pending,
                generated_by=data.registered_by,
                notes=f"Installation {installation.id}",
            )
            db.add(charge)
            db.flush()
            installation.charge_id = charge.id
        record_audit_event(
            db,
            actor=data.registered_by,
            action="installation.assessed",
            entity_type="Installation",
            entity_id=installation.id,
            reason=data.notes or data.coverage_result.value,
            after_data={
                "service_id": service.id,
                "type": data.installation_type,
                "coverage_result": data.coverage_result,
                "scheduled_for": data.scheduled_for,
                "cost": data.cost,
                "status": installation.status,
                "charge_id": installation.charge_id,
            },
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Service already has scheduled installation work",
        ) from exc
    return find_installation_or_404(service.id, installation.id, db)


@router.get(
    "/{service_id}/installations",
    response_model=list[InstallationRead],
)
def list_installations(
    service_id: UUID,
    db: Session = Depends(get_db),
) -> list[Installation]:
    find_service_or_404(service_id, db)
    return list(
        db.scalars(
            installation_query()
            .where(Installation.service_id == service_id)
            .order_by(Installation.registered_at, Installation.id)
        ).unique()
    )


@router.post(
    "/{service_id}/installations/{installation_id}/reschedule",
    response_model=InstallationRead,
)
def reschedule_installation(
    service_id: UUID,
    installation_id: UUID,
    data: InstallationReschedule,
    db: Session = Depends(get_db),
) -> Installation:
    installation = find_installation_or_404(
        service_id, installation_id, db, for_update=True
    )
    if installation.status != InstallationStatus.scheduled:
        raise HTTPException(
            status_code=409,
            detail="Only scheduled work can be rescheduled",
        )
    if data.new_date < date.today():
        raise HTTPException(status_code=409, detail="New date cannot be in the past")
    if data.new_date == installation.scheduled_for:
        raise HTTPException(
            status_code=409,
            detail="Installation date has not changed",
        )
    previous_date = installation.scheduled_for
    installation.schedule_changes.append(
        InstallationScheduleChange(
            previous_date=previous_date,
            new_date=data.new_date,
            changed_by=data.changed_by,
            reason=data.reason,
        )
    )
    installation.scheduled_for = data.new_date
    if installation.charge_id is not None:
        db.get(Charge, installation.charge_id).due_date = data.new_date
    record_audit_event(
        db,
        actor=data.changed_by,
        action="installation.rescheduled",
        entity_type="Installation",
        entity_id=installation.id,
        reason=data.reason,
        before_data={"scheduled_for": previous_date},
        after_data={"scheduled_for": data.new_date},
    )
    db.commit()
    return find_installation_or_404(service_id, installation.id, db)


@router.post(
    "/{service_id}/installations/{installation_id}/complete",
    response_model=InstallationRead,
)
def complete_installation(
    service_id: UUID,
    installation_id: UUID,
    data: InstallationComplete,
    db: Session = Depends(get_db),
) -> Installation:
    service = find_service_or_404(service_id, db)
    installation = find_installation_or_404(
        service_id, installation_id, db, for_update=True
    )
    if installation.status != InstallationStatus.scheduled:
        raise HTTPException(
            status_code=409,
            detail="Only scheduled work can be completed",
        )
    if as_utc(data.completed_at) > datetime.now(UTC):
        raise HTTPException(
            status_code=409,
            detail="Completion cannot be in the future",
        )
    if not data.navigation_confirmed:
        raise HTTPException(
            status_code=409,
            detail="Customer navigation confirmation is required",
        )
    if installation.charge_id is not None:
        charge = db.get(Charge, installation.charge_id)
        if charge.status != ChargeStatus.paid:
            raise HTTPException(
                status_code=409,
                detail="Installation charge must be fully paid",
            )
    previous_service_status = service.status
    previous_address = service.address
    installation.status = InstallationStatus.completed
    installation.completed_at = data.completed_at
    installation.technicians = data.technicians
    installation.antenna_photos = data.antenna_photos
    installation.modem_photos = data.modem_photos
    installation.navigation_confirmed = True
    installation.navigation_confirmed_by = data.navigation_confirmed_by
    installation.notes = data.notes or installation.notes
    if installation.installation_type == InstallationType.installation:
        service.status = ServiceStatus.active
        service.activation_date = data.completed_at.date()
        service.events.append(
            ServiceEvent(
                event_type=ServiceEventType.status_changed,
                from_status=previous_service_status,
                to_status=ServiceStatus.active,
                changes={"installation_id": str(installation.id)},
                reason="Installation completed with navigation confirmed",
            )
        )
    elif installation.installation_type == InstallationType.address_change:
        service.address = installation.new_address
        service.events.append(
            ServiceEvent(
                event_type=ServiceEventType.details_updated,
                changes={
                    "installation_id": str(installation.id),
                    "address": {
                        "before": previous_address,
                        "after": service.address,
                    },
                },
                reason="Address change installation completed",
            )
        )
    record_audit_event(
        db,
        actor=data.performed_by,
        action="installation.completed",
        entity_type="Installation",
        entity_id=installation.id,
        reason="Navigation confirmed and charge paid",
        before_data={
            "status": InstallationStatus.scheduled,
            "service_status": previous_service_status,
            "address": previous_address,
        },
        after_data={
            "status": installation.status,
            "service_status": service.status,
            "address": service.address,
            "navigation_confirmed_by": data.navigation_confirmed_by,
        },
    )
    db.commit()
    return find_installation_or_404(service_id, installation.id, db)


@router.post(
    "/{service_id}/installations/{installation_id}/cancel",
    response_model=InstallationRead,
)
def cancel_installation(
    service_id: UUID,
    installation_id: UUID,
    data: InstallationCancel,
    db: Session = Depends(get_db),
) -> Installation:
    installation = find_installation_or_404(
        service_id, installation_id, db, for_update=True
    )
    if installation.status != InstallationStatus.scheduled:
        raise HTTPException(
            status_code=409,
            detail="Only scheduled work can be cancelled",
        )
    installation.status = InstallationStatus.cancelled
    installation.cancelled_at = datetime.now(UTC)
    installation.cancellation_reason = data.reason
    if installation.charge_id is not None:
        charge = db.get(Charge, installation.charge_id)
        if charge.outstanding_balance != charge.amount:
            raise HTTPException(
                status_code=409,
                detail="Work with an applied payment cannot be cancelled",
            )
        charge.status = ChargeStatus.cancelled
        charge.outstanding_balance = Decimal("0.00")
        charge.cancelled_at = datetime.now(UTC)
        charge.cancelled_by = data.cancelled_by
        charge.cancellation_reason = data.reason
    record_audit_event(
        db,
        actor=data.cancelled_by,
        action="installation.cancelled",
        entity_type="Installation",
        entity_id=installation.id,
        reason=data.reason,
        before_data={"status": InstallationStatus.scheduled},
        after_data={"status": installation.status},
    )
    db.commit()
    return find_installation_or_404(service_id, installation.id, db)
