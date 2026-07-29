from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.endpoints.services import find_service_or_404
from app.db.session import get_db
from app.models.incident import (
    Incident,
    IncidentServiceImpact,
    IncidentStatus,
    as_utc,
)
from app.models.payment_allocation import CreditMovement, CreditMovementType
from app.schemas.incident import (
    IncidentCompensationCreate,
    IncidentCompensationRead,
    IncidentCreate,
    IncidentImpactAdd,
    IncidentImpactRestore,
    IncidentRead,
    IncidentResolve,
    IncidentServiceImpactRead,
)

router = APIRouter(prefix="/api/v1/incidents", tags=["incidents"])


def find_incident_or_404(incident_id: UUID, db: Session) -> Incident:
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


def build_impact(
    incident: Incident,
    service_id: UUID,
    affected_from: datetime,
    notes: str | None,
    db: Session,
) -> IncidentServiceImpact:
    service = find_service_or_404(service_id, db)
    if service.current_customer_id is None:
        raise HTTPException(
            status_code=409,
            detail="Affected service has no current holder",
        )
    if as_utc(affected_from) < as_utc(incident.started_at):
        raise HTTPException(
            status_code=409,
            detail="Service impact cannot start before the incident",
        )
    if as_utc(affected_from) > datetime.now(UTC):
        raise HTTPException(
            status_code=409,
            detail="Service impact cannot start in the future",
        )
    return IncidentServiceImpact(
        service_id=service.id,
        customer_id=service.current_customer_id,
        affected_from=affected_from,
        notes=notes,
    )


@router.post("", response_model=IncidentRead, status_code=201)
def create_incident(
    incident_data: IncidentCreate,
    db: Session = Depends(get_db),
) -> Incident:
    if as_utc(incident_data.started_at) > datetime.now(UTC):
        raise HTTPException(
            status_code=409,
            detail="Incident cannot start in the future",
        )
    incident = Incident(
        title=incident_data.title,
        tower_name=incident_data.tower_name,
        access_point_name=incident_data.access_point_name,
        started_at=incident_data.started_at,
        status=IncidentStatus.open,
        reported_by=incident_data.reported_by,
        notes=incident_data.notes,
    )
    db.add(incident)
    for service_id in incident_data.service_ids:
        incident.impacts.append(
            build_impact(
                incident,
                service_id,
                incident_data.started_at,
                None,
                db,
            )
        )
    db.commit()
    db.refresh(incident)
    return incident


@router.get("", response_model=list[IncidentRead])
def list_incidents(
    incident_status: IncidentStatus | None = None,
    service_id: UUID | None = None,
    tower_name: str | None = Query(default=None, min_length=2),
    db: Session = Depends(get_db),
) -> list[Incident]:
    statement = select(Incident)
    if incident_status is not None:
        statement = statement.where(Incident.status == incident_status)
    if tower_name is not None:
        statement = statement.where(Incident.tower_name == tower_name.strip())
    if service_id is not None:
        statement = statement.join(IncidentServiceImpact).where(
            IncidentServiceImpact.service_id == service_id
        )
    return list(
        db.scalars(
            statement.distinct().order_by(
                Incident.started_at.desc(),
                Incident.id,
            )
        )
    )


@router.get("/{incident_id}", response_model=IncidentRead)
def get_incident(
    incident_id: UUID,
    db: Session = Depends(get_db),
) -> Incident:
    return find_incident_or_404(incident_id, db)


@router.post(
    "/{incident_id}/impacts",
    response_model=IncidentServiceImpactRead,
    status_code=201,
)
def add_incident_impact(
    incident_id: UUID,
    impact_data: IncidentImpactAdd,
    db: Session = Depends(get_db),
) -> IncidentServiceImpact:
    incident = find_incident_or_404(incident_id, db)
    if incident.status != IncidentStatus.open:
        raise HTTPException(
            status_code=409,
            detail="A resolved incident cannot receive affected services",
        )
    impact = build_impact(
        incident,
        impact_data.service_id,
        impact_data.affected_from,
        impact_data.notes,
        db,
    )
    incident.impacts.append(impact)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Service is already affected by this incident",
        ) from exc
    db.refresh(impact)
    return impact


@router.post(
    "/{incident_id}/impacts/{impact_id}/restore",
    response_model=IncidentServiceImpactRead,
)
def restore_incident_impact(
    incident_id: UUID,
    impact_id: UUID,
    restoration: IncidentImpactRestore,
    db: Session = Depends(get_db),
) -> IncidentServiceImpact:
    incident = find_incident_or_404(incident_id, db)
    if incident.status != IncidentStatus.open:
        raise HTTPException(
            status_code=409,
            detail="Incident is already resolved",
        )
    impact = db.scalar(
        select(IncidentServiceImpact)
        .where(
            IncidentServiceImpact.id == impact_id,
            IncidentServiceImpact.incident_id == incident.id,
        )
        .with_for_update()
    )
    if impact is None:
        raise HTTPException(status_code=404, detail="Incident impact not found")
    if impact.restored_at is not None:
        raise HTTPException(
            status_code=409,
            detail="Service impact is already restored",
        )
    restored_at = as_utc(restoration.restored_at)
    if restored_at < as_utc(impact.affected_from):
        raise HTTPException(
            status_code=409,
            detail="restored_at cannot be before affected_from",
        )
    if restored_at > datetime.now(UTC):
        raise HTTPException(
            status_code=409,
            detail="restored_at cannot be in the future",
        )
    impact.restored_at = restoration.restored_at
    db.commit()
    db.refresh(impact)
    return impact


@router.post("/{incident_id}/resolve", response_model=IncidentRead)
def resolve_incident(
    incident_id: UUID,
    resolution: IncidentResolve,
    db: Session = Depends(get_db),
) -> Incident:
    incident = find_incident_or_404(incident_id, db)
    if incident.status == IncidentStatus.resolved:
        raise HTTPException(status_code=409, detail="Incident is already resolved")
    if as_utc(resolution.resolved_at) < as_utc(incident.started_at):
        raise HTTPException(
            status_code=409,
            detail="resolved_at cannot be before started_at",
        )
    if as_utc(resolution.resolved_at) > datetime.now(UTC):
        raise HTTPException(
            status_code=409,
            detail="resolved_at cannot be in the future",
        )
    incident.status = IncidentStatus.resolved
    incident.resolved_at = resolution.resolved_at
    incident.cause = resolution.cause
    incident.responsible = resolution.responsible
    for impact in incident.impacts:
        if impact.restored_at is None:
            impact.restored_at = resolution.resolved_at
    db.commit()
    db.refresh(incident)
    return incident


@router.post(
    "/{incident_id}/impacts/{impact_id}/compensation",
    response_model=IncidentCompensationRead,
    status_code=status.HTTP_201_CREATED,
)
def compensate_incident_impact(
    incident_id: UUID,
    impact_id: UUID,
    compensation: IncidentCompensationCreate,
    db: Session = Depends(get_db),
) -> IncidentCompensationRead:
    incident = find_incident_or_404(incident_id, db)
    if incident.status != IncidentStatus.resolved:
        raise HTTPException(
            status_code=409,
            detail="Compensation requires a resolved incident",
        )
    impact = db.scalar(
        select(IncidentServiceImpact)
        .where(
            IncidentServiceImpact.id == impact_id,
            IncidentServiceImpact.incident_id == incident.id,
        )
        .with_for_update()
    )
    if impact is None:
        raise HTTPException(status_code=404, detail="Incident impact not found")
    if impact.compensation_movement_id is not None:
        raise HTTPException(
            status_code=409,
            detail="This impact already has a compensation",
        )
    movement = CreditMovement(
        customer_id=impact.customer_id,
        service_id=impact.service_id,
        movement_type=CreditMovementType.authorized_adjustment,
        amount=compensation.amount,
        occurred_at=datetime.now(UTC),
        performed_by=compensation.authorized_by,
        reason=(
            f"Incident {incident.id}: {compensation.reason}"
        ),
    )
    db.add(movement)
    db.flush()
    impact.compensation_amount = compensation.amount
    impact.compensation_movement_id = movement.id
    db.commit()
    db.refresh(impact)
    db.refresh(movement)
    return IncidentCompensationRead(
        impact=impact,
        credit_movement=movement,
    )
