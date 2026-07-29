from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.endpoints.services import find_service_or_404
from app.api.v1.endpoints.network_assignments import (
    close_current_network_assignment,
    find_current_network_assignment,
)
from app.api.v1.endpoints.extensions import find_active_extension
from app.api.v1.endpoints.mikrotik import control_service_network
from app.db.session import get_db
from app.models.mikrotik import (
    NetworkCommandStatus,
    NetworkControlAction,
    NetworkControlCommand,
)
from app.models.notification import (
    CustomerNotification,
    NotificationPurpose,
    NotificationStatus,
)
from app.models.service import (
    Service,
    ServiceEvent,
    ServiceEventType,
    ServiceStatus,
)
from app.models.charge import Charge, ChargeStatus, ChargeType
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
    CoordinatedReactivationCreate,
    CoordinatedReactivationRead,
    CoordinatedSuspensionCreate,
    CoordinatedSuspensionRead,
    ReactivationCreate,
    ReactivationRead,
    SuspensionCreate,
    SuspensionRead,
)
from app.schemas.mikrotik import NetworkControlRequest
from app.services.audit import record_audit_event

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


def prepare_suspension(
    service_id: UUID,
    suspension_data: SuspensionCreate,
    db: Session,
) -> tuple[Service, list[Charge], CustomerNotification]:
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
    active_extension = find_active_extension(
        service_id,
        db,
        suspension_data.scheduled_for,
    )
    if active_extension is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "An active payment extension prevents suspension",
                "extension_id": str(active_extension.id),
                "promised_date": active_extension.promised_date.isoformat(),
            },
        )
    if suspension_data.has_active_extension:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A service with an active extension cannot be suspended",
        )
    notification = db.get(
        CustomerNotification,
        suspension_data.notification_id,
    )
    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Suspension notification was not found",
        )
    if (
        notification.service_id != service.id
        or notification.customer_id != service.current_customer_id
        or notification.purpose != NotificationPurpose.suspension_warning
        or notification.status != NotificationStatus.delivered
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A delivered suspension warning for the current holder "
                "and service is required"
            ),
        )
    notification_time = notification.occurred_at
    if notification_time.tzinfo is None:
        notification_time = notification_time.replace(tzinfo=UTC)
    if notification_time > datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Suspension notification cannot be in the future",
        )
    used_notification = db.scalar(
        select(Suspension).where(
            Suspension.notification_id == notification.id,
            Suspension.mikrotik_result.in_(SUCCESSFUL_NETWORK_RESULTS),
        )
    )
    if used_notification is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Suspension notification was already used",
        )

    open_charges = list(
        db.scalars(
            select(Charge)
            .where(
                Charge.service_id == service_id,
                Charge.status.in_(
                    {ChargeStatus.pending, ChargeStatus.partial}
                ),
                Charge.outstanding_balance > 0,
            )
            .order_by(Charge.due_date, Charge.id)
        )
    )
    actual_debt = sum(
        (charge.outstanding_balance for charge in open_charges),
        Decimal("0.00"),
    )
    if actual_debt != suspension_data.debt_amount:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Reported debt does not match Aether balance",
                "reported_debt": str(suspension_data.debt_amount),
                "actual_debt": str(actual_debt),
            },
        )
    overdue_monthly = [
        charge
        for charge in open_charges
        if charge.charge_type == ChargeType.monthly
        and suspension_data.scheduled_for
        >= charge.due_date + timedelta(days=service.grace_days)
    ]
    if not overdue_monthly:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No monthly charge has completed its grace period",
        )
    return service, open_charges, notification


def record_suspension(
    service_id: UUID,
    suspension_data: SuspensionCreate,
    db: Session,
    network_command_id: UUID | None = None,
) -> Suspension:
    service, open_charges, notification = prepare_suspension(
        service_id,
        suspension_data,
        db,
    )
    notification_time = notification.occurred_at
    if notification_time.tzinfo is None:
        notification_time = notification_time.replace(tzinfo=UTC)
    suspension = Suspension(
        service_id=service.id,
        network_command_id=network_command_id,
        notification_id=suspension_data.notification_id,
        notification_sent=True,
        notification_sent_at=notification_time,
        debt_snapshot=[
            {
                "charge_id": str(charge.id),
                "type": charge.charge_type.value,
                "due_date": charge.due_date.isoformat(),
                "outstanding_balance": str(charge.outstanding_balance),
            }
            for charge in open_charges
        ],
        **suspension_data.model_dump(exclude={"notification_id"}),
    )
    db.add(suspension)
    db.flush()

    previous_status = service.status
    if suspension.mikrotik_result in SUCCESSFUL_NETWORK_RESULTS:
        service.status = ServiceStatus.suspended
        add_status_event(
            service,
            previous_status,
            ServiceStatus.suspended,
            suspension.reason,
            suspension.id,
        )
    record_audit_event(
        db,
        actor=suspension.performed_by,
        action="service.suspension",
        entity_type="Suspension",
        entity_id=suspension.id,
        reason=suspension.reason,
        before_data={
            "service_status": previous_status,
            "debt_amount": suspension.debt_amount,
        },
        after_data={
            "service_status": service.status,
            "network_result": suspension.mikrotik_result,
            "network_command_id": network_command_id,
        },
    )

    db.commit()
    db.refresh(suspension)
    return suspension


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
    if suspension_data.mikrotik_result == NetworkOperationResult.success:
        raise HTTPException(
            status_code=409,
            detail=(
                "Automatic success requires a verified MikroTik command; "
                "use the coordinated suspension endpoint"
            ),
        )
    return record_suspension(service_id, suspension_data, db)


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


def find_command_by_idempotency_key(
    idempotency_key: str,
    service_id: UUID,
    action: NetworkControlAction,
    db: Session,
) -> NetworkControlCommand | None:
    command = db.scalar(
        select(NetworkControlCommand).where(
            NetworkControlCommand.idempotency_key == idempotency_key
        )
    )
    if command is not None and (
        command.service_id != service_id or command.action != action
    ):
        raise HTTPException(
            status_code=409,
            detail="Idempotency key belongs to another command",
        )
    return command


def validate_command_assignment(
    command: NetworkControlCommand,
    db: Session,
) -> None:
    assignment = find_current_network_assignment(command.service_id, db)
    if (
        assignment is None
        or assignment.id != command.network_assignment_id
        or assignment.ip_address != command.target_ip
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "Network assignment changed after router execution; "
                "reconciliation is required"
            ),
        )


@router.post(
    "/{service_id}/suspensions/coordinated",
    response_model=CoordinatedSuspensionRead,
)
def coordinate_suspension(
    service_id: UUID,
    suspension_data: CoordinatedSuspensionCreate,
    db: Session = Depends(get_db),
) -> CoordinatedSuspensionRead:
    operation_data = SuspensionCreate(
        scheduled_for=suspension_data.scheduled_for,
        reason=suspension_data.reason,
        debt_amount=suspension_data.debt_amount,
        grace_period_elapsed=suspension_data.grace_period_elapsed,
        extension_checked=suspension_data.extension_checked,
        has_active_extension=suspension_data.has_active_extension,
        notification_id=suspension_data.notification_id,
        performed_by=suspension_data.performed_by,
        mikrotik_result=NetworkOperationResult.success,
        mikrotik_details=None,
    )
    command = find_command_by_idempotency_key(
        suspension_data.idempotency_key,
        service_id,
        NetworkControlAction.suspend,
        db,
    )
    if command is None:
        prepare_suspension(service_id, operation_data, db)
        command = control_service_network(
            service_id,
            NetworkControlAction.suspend,
            NetworkControlRequest(
                requested_by=suspension_data.performed_by,
                idempotency_key=suspension_data.idempotency_key,
                dry_run=suspension_data.dry_run,
            ),
            db,
        )

    suspension = db.scalar(
        select(Suspension).where(
            Suspension.network_command_id == command.id
        )
    )
    if (
        suspension is None
        and command.status == NetworkCommandStatus.succeeded
    ):
        validate_command_assignment(command, db)
        operation_data.mikrotik_details = (
            f"Verified MikroTik command {command.id}"
        )
        try:
            suspension = record_suspension(
                service_id,
                operation_data,
                db,
                network_command_id=command.id,
            )
        except IntegrityError:
            db.rollback()
            suspension = db.scalar(
                select(Suspension).where(
                    Suspension.network_command_id == command.id
                )
            )
            if suspension is None:
                raise
    return CoordinatedSuspensionRead(
        command=command,
        suspension=suspension,
    )


def prepare_reactivation(
    service_id: UUID,
    reactivation_data: ReactivationCreate,
    db: Session,
) -> tuple[Service, Suspension]:
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
    actual_debt = db.scalar(
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
    actual_debt = Decimal(actual_debt or 0)
    if actual_debt != reactivation_data.debt_amount:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Reported debt does not match Aether balance",
                "reported_debt": str(reactivation_data.debt_amount),
                "actual_debt": str(actual_debt),
            },
        )
    return service, effective_suspension


def record_reactivation(
    service_id: UUID,
    reactivation_data: ReactivationCreate,
    db: Session,
    network_command_id: UUID | None = None,
) -> Reactivation:
    service, effective_suspension = prepare_reactivation(
        service_id,
        reactivation_data,
        db,
    )
    reactivation = Reactivation(
        suspension_id=effective_suspension.id,
        network_command_id=network_command_id,
        **reactivation_data.model_dump(),
    )
    db.add(reactivation)
    db.flush()

    previous_status = service.status
    if reactivation.mikrotik_result in SUCCESSFUL_NETWORK_RESULTS:
        service.status = ServiceStatus.active
        add_status_event(
            service,
            previous_status,
            ServiceStatus.active,
            reactivation.reason,
            reactivation.id,
        )
    record_audit_event(
        db,
        actor=reactivation.performed_by,
        action="service.reactivation",
        entity_type="Reactivation",
        entity_id=reactivation.id,
        reason=reactivation.reason,
        before_data={
            "service_status": previous_status,
            "debt_amount": reactivation.debt_amount,
        },
        after_data={
            "service_status": service.status,
            "network_result": reactivation.mikrotik_result,
            "network_command_id": network_command_id,
            "authorized_by": reactivation.authorized_by,
        },
    )

    db.commit()
    db.refresh(reactivation)
    return reactivation


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
    if reactivation_data.mikrotik_result == NetworkOperationResult.success:
        raise HTTPException(
            status_code=409,
            detail=(
                "Automatic success requires a verified MikroTik command; "
                "use the coordinated reactivation endpoint"
            ),
        )
    return record_reactivation(service_id, reactivation_data, db)


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


@router.post(
    "/{service_id}/reactivations/coordinated",
    response_model=CoordinatedReactivationRead,
)
def coordinate_reactivation(
    service_id: UUID,
    reactivation_data: CoordinatedReactivationCreate,
    db: Session = Depends(get_db),
) -> CoordinatedReactivationRead:
    operation_data = ReactivationCreate(
        reason=reactivation_data.reason,
        authorized_by=reactivation_data.authorized_by,
        performed_by=reactivation_data.performed_by,
        debt_amount=reactivation_data.debt_amount,
        mikrotik_result=NetworkOperationResult.success,
        mikrotik_details=None,
    )
    command = find_command_by_idempotency_key(
        reactivation_data.idempotency_key,
        service_id,
        NetworkControlAction.reactivate,
        db,
    )
    if command is None:
        prepare_reactivation(service_id, operation_data, db)
        command = control_service_network(
            service_id,
            NetworkControlAction.reactivate,
            NetworkControlRequest(
                requested_by=reactivation_data.performed_by,
                idempotency_key=reactivation_data.idempotency_key,
                dry_run=reactivation_data.dry_run,
            ),
            db,
        )

    reactivation = db.scalar(
        select(Reactivation).where(
            Reactivation.network_command_id == command.id
        )
    )
    if (
        reactivation is None
        and command.status == NetworkCommandStatus.succeeded
    ):
        validate_command_assignment(command, db)
        operation_data.mikrotik_details = (
            f"Verified MikroTik command {command.id}"
        )
        try:
            reactivation = record_reactivation(
                service_id,
                operation_data,
                db,
                network_command_id=command.id,
            )
        except IntegrityError:
            db.rollback()
            reactivation = db.scalar(
                select(Reactivation).where(
                    Reactivation.network_command_id == command.id
                )
            )
            if reactivation is None:
                raise
    return CoordinatedReactivationRead(
        command=command,
        reactivation=reactivation,
    )


def execute_cancellation(
    service: Service,
    cancellation: Cancellation,
    performed_by: str,
    db: Session,
) -> None:
    previous_status = service.status
    service.status = ServiceStatus.cancelled
    service.cancellation_date = cancellation.effective_date
    cancellation.status = CancellationStatus.executed
    cancellation.executed_by = performed_by
    cancellation.executed_at = datetime.now(UTC)
    close_current_network_assignment(service.id, db)
    add_status_event(
        service,
        previous_status,
        ServiceStatus.cancelled,
        cancellation.reason,
        cancellation.id,
    )
    record_audit_event(
        db,
        actor=performed_by,
        action="service.cancellation.executed",
        entity_type="Cancellation",
        entity_id=cancellation.id,
        reason=cancellation.reason,
        before_data={"service_status": previous_status},
        after_data={
            "service_status": service.status,
            "effective_date": cancellation.effective_date,
        },
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
    record_audit_event(
        db,
        actor=cancellation.registered_by,
        action="service.cancellation.requested",
        entity_type="Cancellation",
        entity_id=cancellation.id,
        reason=cancellation.reason,
        after_data={
            "service_id": service.id,
            "effective_date": cancellation.effective_date,
            "status": cancellation.status,
            "pending_balance": cancellation.pending_balance,
            "credit_balance": cancellation.credit_balance,
        },
    )

    if cancellation.effective_date <= date.today():
        execute_cancellation(
            service,
            cancellation,
            cancellation.registered_by,
            db,
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

    execute_cancellation(
        service,
        cancellation,
        execution.performed_by,
        db,
    )
    db.commit()
    db.refresh(cancellation)
    return cancellation
