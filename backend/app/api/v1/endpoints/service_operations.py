from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.endpoints.services import find_service_or_404
from app.db.session import get_db
from app.models.service import (
    Service,
    ServiceEvent,
    ServiceEventType,
    ServiceStatus,
)
from app.models.service_operations import (
    Cancellation,
    CancellationStatus,
    NetworkOperationResult,
    Reactivation,
    Suspension,
)
from app.schemas.service_operations import (
    CancellationCreate,
    CancellationExecute,
    CancellationRead,
    ReactivationCreate,
    ReactivationRead,
    SuspensionCreate,
    SuspensionRead,
)

router = APIRouter(prefix="/api/v1/services", tags=["service operations"])

SUCCESSFUL_NETWORK_RESULTS = {
    NetworkOperationResult.success,
    NetworkOperationResult.manual,
}


def add_status_event(
    service: Service,
    previous_status: ServiceStatus,
    target_status: ServiceStatus,
    reason: str,
    operation_id: UUID,
) -> None:
    service.events.append(
        ServiceEvent(
            event_type=ServiceEventType.status_changed,
            from_status=previous_status,
            to_status=target_status,
            changes={"operation_id": str(operation_id)},
            reason=reason,
        )
    )


@router.post(
    "/{service_id}/suspensions",
    response_model=SuspensionRead,
    status_code=status.HTTP_201_CREATED,
)
def suspend_service(
    service_id: UUID,
    suspension_data: SuspensionCreate,
    db: Session = Depends(get_db),
) -> Suspension:
    service = find_service_or_404(service_id, db)
    if service.status != ServiceStatus.active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only an active service can be suspended",
        )
    if not suspension_data.grace_period_elapsed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The grace period has not elapsed",
        )
    if not suspension_data.extension_checked:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Active extensions must be checked before suspension",
        )
    if suspension_data.has_active_extension:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A service with an active extension cannot be suspended",
        )
    if not suspension_data.notification_sent:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Prior notification is required before suspension",
        )

    suspension = Suspension(
        service_id=service.id,
        **suspension_data.model_dump(),
    )
    db.add(suspension)
    db.flush()

    if suspension.mikrotik_result in SUCCESSFUL_NETWORK_RESULTS:
        previous_status = service.status
        service.status = ServiceStatus.suspended
        add_status_event(
            service,
            previous_status,
            ServiceStatus.suspended,
            suspension.reason,
            suspension.id,
        )

    db.commit()
    db.refresh(suspension)
    return suspension


@router.get(
    "/{service_id}/suspensions",
    response_model=list[SuspensionRead],
)
def list_suspensions(
    service_id: UUID,
    db: Session = Depends(get_db),
) -> list[Suspension]:
    find_service_or_404(service_id, db)
    statement = (
        select(Suspension)
        .where(Suspension.service_id == service_id)
        .order_by(Suspension.executed_at, Suspension.id)
    )
    return list(db.scalars(statement))


@router.post(
    "/{service_id}/reactivations",
    response_model=ReactivationRead,
    status_code=status.HTTP_201_CREATED,
)
def reactivate_service(
    service_id: UUID,
    reactivation_data: ReactivationCreate,
    db: Session = Depends(get_db),
) -> Reactivation:
    service = find_service_or_404(service_id, db)
    if service.status != ServiceStatus.suspended:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a suspended service can be reactivated",
        )

    effective_suspension = next(
        (
            item
            for item in reversed(service.suspensions)
            if item.mikrotik_result in SUCCESSFUL_NETWORK_RESULTS
            and not any(
                attempt.mikrotik_result in SUCCESSFUL_NETWORK_RESULTS
                for attempt in item.reactivations
            )
        ),
        None,
    )
    if effective_suspension is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No open successful suspension was found",
        )

    reactivation = Reactivation(
        suspension_id=effective_suspension.id,
        **reactivation_data.model_dump(),
    )
    db.add(reactivation)
    db.flush()

    if reactivation.mikrotik_result in SUCCESSFUL_NETWORK_RESULTS:
        previous_status = service.status
        service.status = ServiceStatus.active
        add_status_event(
            service,
            previous_status,
            ServiceStatus.active,
            reactivation.reason,
            reactivation.id,
        )

    db.commit()
    db.refresh(reactivation)
    return reactivation


@router.get(
    "/{service_id}/reactivations",
    response_model=list[ReactivationRead],
)
def list_reactivations(
    service_id: UUID,
    db: Session = Depends(get_db),
) -> list[Reactivation]:
    find_service_or_404(service_id, db)
    statement = (
        select(Reactivation)
        .join(Suspension)
        .where(Suspension.service_id == service_id)
        .order_by(Reactivation.executed_at, Reactivation.id)
    )
    return list(db.scalars(statement))


def execute_cancellation(
    service: Service,
    cancellation: Cancellation,
    performed_by: str,
) -> None:
    previous_status = service.status
    service.status = ServiceStatus.cancelled
    service.cancellation_date = cancellation.effective_date
    cancellation.status = CancellationStatus.executed
    cancellation.executed_by = performed_by
    cancellation.executed_at = datetime.now(UTC)
    add_status_event(
        service,
        previous_status,
        ServiceStatus.cancelled,
        cancellation.reason,
        cancellation.id,
    )


@router.post(
    "/{service_id}/cancellation",
    response_model=CancellationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_cancellation(
    service_id: UUID,
    cancellation_data: CancellationCreate,
    db: Session = Depends(get_db),
) -> Cancellation:
    service = find_service_or_404(service_id, db)
    if service.status == ServiceStatus.cancelled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The service is already cancelled",
        )
    if cancellation_data.requester_customer_id != service.current_customer_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The requester must be the current service holder",
        )

    cancellation = Cancellation(
        service_id=service.id,
        folio=f"CAN-{date.today():%Y%m%d}-{uuid4().hex[:8].upper()}",
        status=CancellationStatus.scheduled,
        **cancellation_data.model_dump(),
    )
    db.add(cancellation)
    db.flush()

    if cancellation.effective_date <= date.today():
        execute_cancellation(
            service,
            cancellation,
            cancellation.registered_by,
        )

    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A cancellation already exists for this service",
        ) from error

    db.refresh(cancellation)
    return cancellation


@router.get(
    "/{service_id}/cancellation",
    response_model=CancellationRead,
)
def get_cancellation(
    service_id: UUID,
    db: Session = Depends(get_db),
) -> Cancellation:
    find_service_or_404(service_id, db)
    cancellation = db.scalar(
        select(Cancellation).where(Cancellation.service_id == service_id)
    )
    if cancellation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cancellation not found",
        )
    return cancellation


@router.post(
    "/{service_id}/cancellation/execute",
    response_model=CancellationRead,
)
def execute_scheduled_cancellation(
    service_id: UUID,
    execution: CancellationExecute,
    db: Session = Depends(get_db),
) -> Cancellation:
    service = find_service_or_404(service_id, db)
    cancellation = db.scalar(
        select(Cancellation).where(Cancellation.service_id == service_id)
    )
    if cancellation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cancellation not found",
        )
    if cancellation.status == CancellationStatus.executed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The cancellation was already executed",
        )
    if cancellation.effective_date > date.today():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The effective cancellation date has not arrived",
        )

    execute_cancellation(service, cancellation, execution.performed_by)
    db.commit()
    db.refresh(cancellation)
    return cancellation
