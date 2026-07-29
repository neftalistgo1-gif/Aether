from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.audit import AuditEvent
from app.schemas.audit import AuditEventRead

router = APIRouter(prefix="/api/v1/audit-events", tags=["audit"])


@router.get("", response_model=list[AuditEventRead])
def list_audit_events(
    actor: str | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    db: Session = Depends(get_db),
) -> list[AuditEvent]:
    statement = select(AuditEvent)
    if actor is not None:
        statement = statement.where(AuditEvent.actor == actor)
    if action is not None:
        statement = statement.where(AuditEvent.action == action)
    if entity_type is not None:
        statement = statement.where(AuditEvent.entity_type == entity_type)
    if entity_id is not None:
        statement = statement.where(AuditEvent.entity_id == entity_id)
    return list(
        db.scalars(
            statement.order_by(
                AuditEvent.occurred_at.desc(),
                AuditEvent.id.desc(),
            ).limit(limit)
        )
    )


@router.get("/{event_id}", response_model=AuditEventRead)
def get_audit_event(
    event_id: UUID,
    db: Session = Depends(get_db),
) -> AuditEvent:
    event = db.get(AuditEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Audit event not found")
    return event
