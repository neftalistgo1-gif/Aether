from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.endpoints.network_assignments import (
    find_current_network_assignment,
)
from app.api.v1.endpoints.services import find_service_or_404
from app.db.session import get_db
from app.integrations.mikrotik import RouterOSRestClient
from app.models.mikrotik import (
    MikrotikRouter,
    NetworkCommandStatus,
    NetworkControlAction,
    NetworkControlCommand,
    NetworkInspectionStatus,
    NetworkStateInspection,
)
from app.models.access_point import NetworkAccessPoint
from app.schemas.access_point import AccessPointHealthRead
from app.models.service import ServiceStatus
from app.schemas.mikrotik import (
    MikrotikRouterCreate,
    MikrotikRouterRead,
    MikrotikRouterUpdate,
    NetworkControlCommandRead,
    NetworkControlRequest,
    NetworkControlRetry,
    NetworkInspectionRequest,
    NetworkStateInspectionRead,
    credentials_configured,
)
from app.services.audit import record_audit_event

router = APIRouter(prefix="/api/v1", tags=["mikrotik"])

PREFLIGHT_MAX_AGE = timedelta(minutes=15)
INSPECTION_MAX_AGE = timedelta(minutes=5)


def normalized_mac(value: str | None) -> str:
    return (value or "").replace("-", ":").upper()


@router.get(
    "/mikrotik/access-points/health",
    response_model=list[AccessPointHealthRead],
)
def list_access_point_health(
    db: Session = Depends(get_db),
) -> list[AccessPointHealthRead]:
    access_points = list(
        db.scalars(
            select(NetworkAccessPoint).order_by(
                NetworkAccessPoint.name,
                NetworkAccessPoint.ip_address,
            )
        )
    )
    routers = {
        item.id: item
        for item in db.scalars(select(MikrotikRouter)).all()
    }
    neighbors_by_router: dict[UUID, dict[str, dict]] = {}
    unavailable_routers: set[UUID] = set()
    for router_id in {item.router_id for item in access_points}:
        router_config = routers.get(router_id)
        if router_config is None:
            unavailable_routers.add(router_id)
            continue
        try:
            neighbors = RouterOSRestClient(router_config).list_neighbors()
            neighbors_by_router[router_id] = {
                str(item.get("address4") or item.get("address")): item
                for item in neighbors
                if item.get("address4") or item.get("address")
            }
        except RuntimeError:
            unavailable_routers.add(router_id)

    checked_at = datetime.now(UTC)
    result: list[AccessPointHealthRead] = []
    for access_point in access_points:
        neighbor = neighbors_by_router.get(access_point.router_id, {}).get(
            access_point.ip_address
        )
        if access_point.router_id in unavailable_routers:
            health_status = "unknown"
        elif neighbor is None:
            health_status = "offline"
        elif (
            access_point.mac_address
            and normalized_mac(neighbor.get("mac-address"))
            != normalized_mac(access_point.mac_address)
        ):
            health_status = "attention"
        else:
            health_status = "online"
        result.append(
            AccessPointHealthRead(
                id=access_point.id,
                router_id=access_point.router_id,
                name=access_point.name,
                ip_address=access_point.ip_address,
                mac_address=access_point.mac_address,
                interface_name=access_point.interface_name,
                platform=access_point.platform,
                source_note=access_point.source_note,
                status=health_status,
                observed_identity=neighbor.get("identity") if neighbor else None,
                observed_age=neighbor.get("age") if neighbor else None,
                checked_at=checked_at,
            )
        )
    return result


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def audit_network_command(
    command: NetworkControlCommand,
    db: Session,
) -> None:
    record_audit_event(
        db,
        actor=command.requested_by,
        action=f"network.command.{command.status.value}",
        entity_type="NetworkControlCommand",
        entity_id=command.id,
        reason=command.error_message or command.action.value,
        after_data={
            "service_id": command.service_id,
            "preflight_command_id": command.preflight_command_id,
            "network_inspection_id": command.network_inspection_id,
            "router_id": command.router_id,
            "target_ip": command.target_ip,
            "desired_blocked": command.desired_blocked,
            "dry_run": command.dry_run,
            "status": command.status,
            "attempt": command.attempts,
            "verified_at": command.verified_at,
        },
    )


def audit_network_inspection(
    inspection: NetworkStateInspection,
    db: Session,
) -> None:
    record_audit_event(
        db,
        actor=inspection.requested_by,
        action=f"network.inspection.{inspection.status.value}",
        entity_type="NetworkStateInspection",
        entity_id=inspection.id,
        reason=inspection.error_message or "Read-only network state inspection",
        after_data={
            "service_id": inspection.service_id,
            "network_assignment_id": inspection.network_assignment_id,
            "router_id": inspection.router_id,
            "target_ip": inspection.target_ip,
            "expected_blocked": inspection.expected_blocked,
            "observed_blocked": inspection.observed_blocked,
            "matches_expected": inspection.matches_expected,
            "entry_count": inspection.entry_count,
            "status": inspection.status,
            "completed_at": inspection.completed_at,
        },
    )


def validate_live_preflight(
    control: NetworkControlRequest,
    service_id: UUID,
    action: NetworkControlAction,
    assignment,
    router_config: MikrotikRouter,
    desired_blocked: bool,
    db: Session,
) -> NetworkControlCommand | None:
    if control.dry_run:
        return None
    preflight = db.get(
        NetworkControlCommand,
        control.preflight_command_id,
    )
    now = datetime.now(UTC)
    if (
        preflight is None
        or not preflight.dry_run
        or preflight.status != NetworkCommandStatus.simulated
        or preflight.preflight_command_id is not None
        or preflight.service_id != service_id
        or preflight.action != action
        or preflight.network_assignment_id != assignment.id
        or preflight.router_id != router_config.id
        or preflight.target_ip != assignment.ip_address
        or preflight.desired_blocked != desired_blocked
        or preflight.network_inspection_id
        != control.network_inspection_id
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "Live command requires a matching simulated preflight "
                "for the current network assignment"
            ),
        )
    requested_at = as_utc(preflight.requested_at)
    if requested_at > now or now - requested_at > PREFLIGHT_MAX_AGE:
        raise HTTPException(
            status_code=409,
            detail="Network preflight expired; run a new simulation",
        )
    used = db.scalar(
        select(NetworkControlCommand).where(
            NetworkControlCommand.preflight_command_id == preflight.id
        )
    )
    if used is not None:
        raise HTTPException(
            status_code=409,
            detail="Network preflight was already used",
        )
    return preflight


def validate_reconciliation_inspection(
    control: NetworkControlRequest,
    service_id: UUID,
    action: NetworkControlAction,
    assignment,
    router_config: MikrotikRouter,
    desired_blocked: bool,
    db: Session,
) -> NetworkStateInspection | None:
    if action != NetworkControlAction.reconcile:
        if control.network_inspection_id is not None:
            raise HTTPException(
                status_code=409,
                detail="Network inspection is only valid for reconciliation",
            )
        return None
    if control.network_inspection_id is None:
        raise HTTPException(
            status_code=409,
            detail="Reconciliation requires a recent mismatching inspection",
        )
    inspection = db.get(
        NetworkStateInspection,
        control.network_inspection_id,
    )
    now = datetime.now(UTC)
    if (
        inspection is None
        or inspection.status != NetworkInspectionStatus.succeeded
        or inspection.matches_expected is not False
        or inspection.completed_at is None
        or inspection.service_id != service_id
        or inspection.network_assignment_id != assignment.id
        or inspection.router_id != router_config.id
        or inspection.target_ip != assignment.ip_address
        or inspection.expected_blocked != desired_blocked
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "Reconciliation requires a matching inspection that "
                "confirmed network drift"
            ),
        )
    completed_at = as_utc(inspection.completed_at)
    if completed_at > now or now - completed_at > INSPECTION_MAX_AGE:
        raise HTTPException(
            status_code=409,
            detail="Network inspection expired; inspect the service again",
        )
    if control.dry_run:
        used = db.scalar(
            select(NetworkControlCommand).where(
                NetworkControlCommand.network_inspection_id == inspection.id,
                NetworkControlCommand.dry_run.is_(True),
            )
        )
        if used is not None:
            raise HTTPException(
                status_code=409,
                detail="Network inspection already has a reconciliation preflight",
            )
    return inspection


def router_read(item: MikrotikRouter) -> MikrotikRouterRead:
    return MikrotikRouterRead(
        **{
            column.name: getattr(item, column.name)
            for column in item.__table__.columns
        },
        credentials_configured=credentials_configured(item.credential_key),
    )


@router.post(
    "/mikrotik/routers",
    response_model=MikrotikRouterRead,
    status_code=status.HTTP_201_CREATED,
)
def create_router(
    router_data: MikrotikRouterCreate,
    db: Session = Depends(get_db),
) -> MikrotikRouterRead:
    if router_data.enabled and not credentials_configured(
        router_data.credential_key
    ):
        raise HTTPException(
            status_code=409,
            detail="Router credentials must be configured before enabling",
        )
    item = MikrotikRouter(**router_data.model_dump())
    db.add(item)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Router name already exists") from exc
    db.refresh(item)
    return router_read(item)


@router.get("/mikrotik/routers", response_model=list[MikrotikRouterRead])
def list_routers(db: Session = Depends(get_db)) -> list[MikrotikRouterRead]:
    return [
        router_read(item)
        for item in db.scalars(select(MikrotikRouter).order_by(MikrotikRouter.name))
    ]


@router.patch(
    "/mikrotik/routers/{router_id}",
    response_model=MikrotikRouterRead,
)
def update_router(
    router_id: UUID,
    router_data: MikrotikRouterUpdate,
    db: Session = Depends(get_db),
) -> MikrotikRouterRead:
    item = db.get(MikrotikRouter, router_id)
    if item is None:
        raise HTTPException(status_code=404, detail="MikroTik router not found")
    updates = router_data.model_dump(exclude_unset=True)
    credential_key = updates.get("credential_key", item.credential_key)
    enabled = updates.get("enabled", item.enabled)
    if enabled and not credentials_configured(credential_key):
        raise HTTPException(
            status_code=409,
            detail="Router credentials must be configured before enabling",
        )
    for field, value in updates.items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return router_read(item)


def execute_command(
    command: NetworkControlCommand,
    router_config: MikrotikRouter,
    db: Session,
) -> NetworkControlCommand:
    command.attempts += 1
    command.executed_at = datetime.now(UTC)
    if command.dry_run:
        command.status = NetworkCommandStatus.simulated
        command.changed_router = False
        command.verified_at = None
        command.error_message = None
        command.result_details = {"verified": False, "mode": "dry_run"}
        audit_network_command(command, db)
        db.commit()
        db.refresh(command)
        return command
    if not router_config.enabled:
        command.status = NetworkCommandStatus.failed
        command.changed_router = False
        command.verified_at = None
        command.result_details = {"verified": False}
        command.error_message = "Router integration is disabled"
        audit_network_command(command, db)
        db.commit()
        db.refresh(command)
        return command
    try:
        result = RouterOSRestClient(router_config).set_blocked(
            command.target_ip,
            command.desired_blocked,
            f"Aether service {command.service_id}",
        )
        command.status = NetworkCommandStatus.succeeded
        command.changed_router = result.changed
        command.verified_at = datetime.now(UTC)
        command.result_details = {
            "blocked": result.blocked,
            "entry_count": result.entry_count,
            "verified": True,
        }
        command.error_message = None
    except RuntimeError as exc:
        command.status = NetworkCommandStatus.failed
        command.changed_router = False
        command.verified_at = None
        command.result_details = {"verified": False}
        command.error_message = str(exc)
    audit_network_command(command, db)
    db.commit()
    db.refresh(command)
    return command


def execute_network_inspection(
    inspection: NetworkStateInspection,
    router_config: MikrotikRouter,
    db: Session,
) -> NetworkStateInspection:
    inspection.completed_at = datetime.now(UTC)
    if not router_config.enabled:
        inspection.status = NetworkInspectionStatus.failed
        inspection.error_message = "Router integration is disabled"
    else:
        try:
            result = RouterOSRestClient(router_config).inspect_blocked(
                inspection.target_ip
            )
            inspection.status = NetworkInspectionStatus.succeeded
            inspection.observed_blocked = result.blocked
            inspection.matches_expected = (
                result.blocked == inspection.expected_blocked
            )
            inspection.entry_count = result.entry_count
            inspection.error_message = None
        except RuntimeError as exc:
            inspection.status = NetworkInspectionStatus.failed
            inspection.error_message = str(exc)
    audit_network_inspection(inspection, db)
    db.commit()
    db.refresh(inspection)
    return inspection


@router.post(
    "/services/{service_id}/network-control/inspect",
    response_model=NetworkStateInspectionRead,
)
def inspect_service_network(
    service_id: UUID,
    request: NetworkInspectionRequest,
    db: Session = Depends(get_db),
) -> NetworkStateInspection:
    existing = db.scalar(
        select(NetworkStateInspection).where(
            NetworkStateInspection.idempotency_key
            == request.idempotency_key
        )
    )
    if existing is not None:
        if existing.service_id != service_id:
            raise HTTPException(
                status_code=409,
                detail="Idempotency key belongs to another inspection",
            )
        if (
            existing.status == NetworkInspectionStatus.pending
            and existing.completed_at is None
        ):
            router_config = db.get(MikrotikRouter, existing.router_id)
            if router_config is None:
                existing.status = NetworkInspectionStatus.failed
                existing.completed_at = datetime.now(UTC)
                existing.error_message = "MikroTik router not found"
                audit_network_inspection(existing, db)
                db.commit()
                db.refresh(existing)
                return existing
            return execute_network_inspection(
                existing,
                router_config,
                db,
            )
        return existing
    service = find_service_or_404(service_id, db)
    if service.status not in {
        ServiceStatus.active,
        ServiceStatus.suspended,
    }:
        raise HTTPException(
            status_code=409,
            detail=(
                "Only an active or suspended service can inspect "
                "network access"
            ),
        )
    assignment = find_current_network_assignment(service_id, db)
    if assignment is None:
        raise HTTPException(
            status_code=409,
            detail="Service has no current network assignment",
        )
    router_config = db.scalar(
        select(MikrotikRouter).where(
            MikrotikRouter.name == assignment.router_name
        )
    )
    if router_config is None:
        raise HTTPException(
            status_code=409,
            detail="Network router is not registered for MikroTik control",
        )
    inspection = NetworkStateInspection(
        idempotency_key=request.idempotency_key,
        service_id=service.id,
        network_assignment_id=assignment.id,
        router_id=router_config.id,
        target_ip=assignment.ip_address,
        expected_blocked=service.status == ServiceStatus.suspended,
        status=NetworkInspectionStatus.pending,
        requested_by=request.requested_by,
    )
    db.add(inspection)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        existing = db.scalar(
            select(NetworkStateInspection).where(
                NetworkStateInspection.idempotency_key
                == request.idempotency_key
            )
        )
        if existing is not None and existing.service_id == service_id:
            return existing
        raise HTTPException(
            status_code=409,
            detail="Idempotency key belongs to another inspection",
        ) from exc
    db.refresh(inspection)
    return execute_network_inspection(inspection, router_config, db)


@router.get(
    "/services/{service_id}/network-control/inspections",
    response_model=list[NetworkStateInspectionRead],
)
def list_network_inspections(
    service_id: UUID,
    db: Session = Depends(get_db),
) -> list[NetworkStateInspection]:
    find_service_or_404(service_id, db)
    return list(
        db.scalars(
            select(NetworkStateInspection)
            .where(NetworkStateInspection.service_id == service_id)
            .order_by(
                NetworkStateInspection.requested_at,
                NetworkStateInspection.id,
            )
        )
    )


@router.post(
    "/services/{service_id}/network-control/{action}",
    response_model=NetworkControlCommandRead,
)
def control_service_network(
    service_id: UUID,
    action: NetworkControlAction,
    control: NetworkControlRequest,
    db: Session = Depends(get_db),
) -> NetworkControlCommand:
    existing = db.scalar(
        select(NetworkControlCommand).where(
            NetworkControlCommand.idempotency_key == control.idempotency_key
        )
    )
    if existing is not None:
        if existing.service_id != service_id or existing.action != action:
            raise HTTPException(status_code=409, detail="Idempotency key belongs to another command")
        if (
            existing.dry_run != control.dry_run
            or existing.preflight_command_id
            != control.preflight_command_id
            or existing.network_inspection_id
            != control.network_inspection_id
        ):
            raise HTTPException(
                status_code=409,
                detail="Idempotency key payload does not match",
            )
        return existing

    service = find_service_or_404(service_id, db)
    assignment = find_current_network_assignment(service_id, db)
    if assignment is None:
        raise HTTPException(status_code=409, detail="Service has no current network assignment")
    router_config = db.scalar(
        select(MikrotikRouter).where(MikrotikRouter.name == assignment.router_name)
    )
    if router_config is None:
        raise HTTPException(status_code=409, detail="Network router is not registered for MikroTik control")
    if action == NetworkControlAction.suspend:
        if service.status != ServiceStatus.active:
            raise HTTPException(status_code=409, detail="Only an active service can be suspended")
        desired_blocked = True
    elif action == NetworkControlAction.reactivate:
        if service.status != ServiceStatus.suspended:
            raise HTTPException(status_code=409, detail="Only a suspended service can be reactivated")
        desired_blocked = False
    elif action == NetworkControlAction.decommission:
        if service.status == ServiceStatus.cancelled:
            raise HTTPException(
                status_code=409,
                detail="A cancelled service cannot start network shutdown",
            )
        desired_blocked = True
    elif action == NetworkControlAction.release:
        if service.status != ServiceStatus.cancelled:
            raise HTTPException(
                status_code=409,
                detail="Only a cancelled service can release its network IP",
            )
        desired_blocked = False
    elif action == NetworkControlAction.reconcile:
        if service.status not in {
            ServiceStatus.active,
            ServiceStatus.suspended,
        }:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Only an active or suspended service can reconcile "
                    "network access"
                ),
            )
        desired_blocked = service.status == ServiceStatus.suspended
    else:
        raise HTTPException(status_code=409, detail="Unsupported network action")
    validate_reconciliation_inspection(
        control,
        service.id,
        action,
        assignment,
        router_config,
        desired_blocked,
        db,
    )
    preflight = validate_live_preflight(
        control,
        service.id,
        action,
        assignment,
        router_config,
        desired_blocked,
        db,
    )

    command = NetworkControlCommand(
        idempotency_key=control.idempotency_key,
        service_id=service.id,
        preflight_command_id=(
            preflight.id if preflight is not None else None
        ),
        network_inspection_id=control.network_inspection_id,
        network_assignment_id=assignment.id,
        router_id=router_config.id,
        action=action,
        target_ip=assignment.ip_address,
        desired_blocked=desired_blocked,
        dry_run=control.dry_run,
        status=NetworkCommandStatus.simulated,
        requested_by=control.requested_by,
    )
    db.add(command)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        existing = db.scalar(
            select(NetworkControlCommand).where(
                NetworkControlCommand.idempotency_key
                == control.idempotency_key
            )
        )
        if (
            existing is not None
            and existing.service_id == service_id
            and existing.action == action
            and existing.dry_run == control.dry_run
            and existing.preflight_command_id
            == control.preflight_command_id
            and existing.network_inspection_id
            == control.network_inspection_id
        ):
            return existing
        raise HTTPException(
            status_code=409,
            detail="Idempotency key belongs to another command",
        ) from exc
    db.refresh(command)
    return execute_command(command, router_config, db)


@router.get(
    "/services/{service_id}/network-control/commands",
    response_model=list[NetworkControlCommandRead],
)
def list_network_commands(
    service_id: UUID,
    db: Session = Depends(get_db),
) -> list[NetworkControlCommand]:
    find_service_or_404(service_id, db)
    return list(
        db.scalars(
            select(NetworkControlCommand)
            .where(NetworkControlCommand.service_id == service_id)
            .order_by(NetworkControlCommand.requested_at, NetworkControlCommand.id)
        )
    )


@router.post(
    "/network-control/commands/{command_id}/retry",
    response_model=NetworkControlCommandRead,
)
def retry_network_command(
    command_id: UUID,
    retry: NetworkControlRetry,
    db: Session = Depends(get_db),
) -> NetworkControlCommand:
    command = db.get(NetworkControlCommand, command_id)
    if command is None:
        raise HTTPException(status_code=404, detail="Network command not found")
    if command.status == NetworkCommandStatus.succeeded:
        raise HTTPException(
            status_code=409,
            detail="A successful command does not need a retry",
        )
    if command.status == NetworkCommandStatus.simulated:
        raise HTTPException(
            status_code=409,
            detail=(
                "A simulated command cannot be promoted by retry; "
                "create a live command linked to it"
            ),
        )
    if retry.dry_run != command.dry_run:
        raise HTTPException(
            status_code=409,
            detail="Retry cannot change the command execution mode",
        )
    if not command.dry_run and command.preflight_command_id is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Legacy live command has no preflight; "
                "run a new simulation"
            ),
        )
    if command.action == NetworkControlAction.reconcile:
        service = find_service_or_404(command.service_id, db)
        expected_blocked = service.status == ServiceStatus.suspended
        if (
            service.status
            not in {ServiceStatus.active, ServiceStatus.suspended}
            or command.network_inspection_id is None
            or command.desired_blocked != expected_blocked
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Reconciliation retry no longer matches the current "
                    "commercial state; inspect the service again"
                ),
            )
    assignment = find_current_network_assignment(command.service_id, db)
    if (
        assignment is None
        or assignment.id != command.network_assignment_id
        or assignment.ip_address != command.target_ip
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "Network assignment changed; create a new reconciliation "
                "command"
            ),
        )
    router_config = db.get(MikrotikRouter, command.router_id)
    if router_config is None:
        raise HTTPException(status_code=409, detail="MikroTik router not found")
    if router_config.name != assignment.router_name:
        raise HTTPException(
            status_code=409,
            detail=(
                "Router assignment changed; create a new reconciliation "
                "command"
            ),
        )
    command.requested_by = retry.requested_by
    return execute_command(command, router_config, db)
