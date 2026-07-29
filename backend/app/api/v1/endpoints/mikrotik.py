from datetime import UTC, datetime
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
)
from app.models.service import ServiceStatus
from app.schemas.mikrotik import (
    MikrotikRouterCreate,
    MikrotikRouterRead,
    MikrotikRouterUpdate,
    NetworkControlCommandRead,
    NetworkControlRequest,
    NetworkControlRetry,
    credentials_configured,
)

router = APIRouter(prefix="/api/v1", tags=["mikrotik"])


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
        db.commit()
        db.refresh(command)
        return command
    if not router_config.enabled:
        command.status = NetworkCommandStatus.failed
        command.changed_router = False
        command.verified_at = None
        command.result_details = {"verified": False}
        command.error_message = "Router integration is disabled"
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
    db.commit()
    db.refresh(command)
    return command


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
    else:
        desired_blocked = service.status == ServiceStatus.suspended

    command = NetworkControlCommand(
        idempotency_key=control.idempotency_key,
        service_id=service.id,
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
    command.dry_run = retry.dry_run
    return execute_command(command, router_config, db)
