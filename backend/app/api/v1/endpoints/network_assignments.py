from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.endpoints.services import find_service_or_404
from app.db.session import get_db
from app.models.network_assignment import NetworkAssignment
from app.models.service import ServiceStatus
from app.models.service_operations import Cancellation, CancellationStatus
from app.schemas.network_assignment import (
    NetworkAssignmentCreate,
    NetworkAssignmentRead,
)

router = APIRouter(prefix="/api/v1/services", tags=["network assignments"])

NETWORK_CONFIGURATION_FIELDS = (
    "router_name",
    "ip_address",
    "tower_name",
    "access_point_name",
    "antenna_name",
    "frequency_mhz",
    "signal_dbm",
)


def find_current_network_assignment(
    service_id: UUID,
    db: Session,
) -> NetworkAssignment | None:
    return db.scalar(
        select(NetworkAssignment).where(
            NetworkAssignment.service_id == service_id,
            NetworkAssignment.ended_at.is_(None),
        )
    )


def close_current_network_assignment(
    service_id: UUID,
    db: Session,
) -> NetworkAssignment | None:
    assignment = find_current_network_assignment(service_id, db)
    if assignment is not None:
        assignment.ended_at = datetime.now(UTC)
    return assignment


@router.post(
    "/{service_id}/network-assignments",
    response_model=NetworkAssignmentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_network_assignment(
    service_id: UUID,
    assignment_data: NetworkAssignmentCreate,
    db: Session = Depends(get_db),
) -> NetworkAssignment:
    service = find_service_or_404(service_id, db)
    if service.status == ServiceStatus.cancelled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A cancelled service cannot receive network configuration",
        )
    if service.status == ServiceStatus.suspended:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Network configuration cannot change while the service is "
                "suspended"
            ),
        )
    current = find_current_network_assignment(service_id, db)
    if current is not None:
        scheduled_cancellation = db.scalar(
            select(Cancellation).where(
                Cancellation.service_id == service.id,
                Cancellation.status == CancellationStatus.scheduled,
            )
        )
        if scheduled_cancellation is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Network configuration cannot change while "
                    "cancellation is scheduled"
                ),
            )
    if current is not None and all(
        getattr(current, field_name) == getattr(assignment_data, field_name)
        for field_name in NETWORK_CONFIGURATION_FIELDS
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The network configuration has not changed",
        )

    conflicting_assignment = db.scalar(
        select(NetworkAssignment).where(
            NetworkAssignment.router_name == assignment_data.router_name,
            NetworkAssignment.ip_address == assignment_data.ip_address,
            NetworkAssignment.ended_at.is_(None),
            NetworkAssignment.service_id != service_id,
        )
    )
    if conflicting_assignment is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This router and IP are assigned to another service",
        )

    if current is not None:
        current.ended_at = datetime.now(UTC)

    assignment = NetworkAssignment(
        service_id=service.id,
        **assignment_data.model_dump(),
    )
    db.add(assignment)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A current network assignment already uses these values",
        ) from error
    db.refresh(assignment)
    return assignment


@router.get(
    "/{service_id}/network-assignment",
    response_model=NetworkAssignmentRead,
)
def get_current_network_assignment(
    service_id: UUID,
    db: Session = Depends(get_db),
) -> NetworkAssignment:
    find_service_or_404(service_id, db)
    assignment = find_current_network_assignment(service_id, db)
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Current network assignment not found",
        )
    return assignment


@router.get(
    "/{service_id}/network-assignments",
    response_model=list[NetworkAssignmentRead],
)
def list_network_assignments(
    service_id: UUID,
    db: Session = Depends(get_db),
) -> list[NetworkAssignment]:
    find_service_or_404(service_id, db)
    statement = (
        select(NetworkAssignment)
        .where(NetworkAssignment.service_id == service_id)
        .order_by(
            NetworkAssignment.started_at,
            NetworkAssignment.id,
        )
    )
    return list(db.scalars(statement))
