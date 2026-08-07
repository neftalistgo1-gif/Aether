from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models.customer import Customer
from app.models.service import Service
from app.models.support_ticket import (
    SupportTicket,
    SupportTicketAssignee,
    SupportTicketStatus,
)
from app.schemas.support_ticket import (
    SupportTicketClassify,
    SupportTicketCreate,
    SupportTicketRead,
    SupportTicketResolve,
)
from app.services.audit import record_audit_event

router = APIRouter(prefix="/api/v1/support-tickets", tags=["support-tickets"])


def ticket_query():
    return select(SupportTicket)


def find_ticket_or_404(ticket_id: UUID, db: Session) -> SupportTicket:
    ticket = db.scalar(ticket_query().where(SupportTicket.id == ticket_id))
    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Support ticket not found",
        )
    return ticket


@router.post("", response_model=SupportTicketRead, status_code=201)
def create_ticket(
    ticket_data: SupportTicketCreate,
    db: Session = Depends(get_db),
) -> SupportTicket:
    if db.get(Customer, ticket_data.customer_id) is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    if ticket_data.service_id is not None and db.get(Service, ticket_data.service_id) is None:
        raise HTTPException(status_code=404, detail="Service not found")
    if ticket_data.service_id is not None:
        service = db.get(Service, ticket_data.service_id)
        if service.current_customer_id != ticket_data.customer_id:
            raise HTTPException(
                status_code=409,
                detail="Ticket service does not belong to customer",
            )
    ticket = SupportTicket(
        status=SupportTicketStatus.new,
        **ticket_data.model_dump(),
    )
    db.add(ticket)
    db.flush()
    record_audit_event(
        db,
        actor=ticket_data.created_by,
        action="support_ticket.created",
        entity_type="SupportTicket",
        entity_id=ticket.id,
        reason=ticket_data.title,
        after_data={
            "customer_id": ticket.customer_id,
            "service_id": ticket.service_id,
            "category": ticket.category,
            "priority": ticket.priority,
            "status": ticket.status,
        },
    )
    db.commit()
    db.refresh(ticket)
    return find_ticket_or_404(ticket.id, db)


@router.get("", response_model=list[SupportTicketRead])
def list_tickets(
    db: Session = Depends(get_db),
    status_filter: SupportTicketStatus | None = None,
    customer_id: UUID | None = None,
) -> list[SupportTicket]:
    statement = ticket_query()
    if status_filter is not None:
        statement = statement.where(SupportTicket.status == status_filter)
    if customer_id is not None:
        statement = statement.where(SupportTicket.customer_id == customer_id)
    statement = statement.order_by(SupportTicket.created_at.desc(), SupportTicket.id)
    return list(db.scalars(statement))


@router.get("/{ticket_id}", response_model=SupportTicketRead)
def get_ticket(ticket_id: UUID, db: Session = Depends(get_db)) -> SupportTicket:
    return find_ticket_or_404(ticket_id, db)


@router.post("/{ticket_id}/classify", response_model=SupportTicketRead)
def classify_ticket(
    ticket_id: UUID,
    classification: SupportTicketClassify,
    db: Session = Depends(get_db),
) -> SupportTicket:
    ticket = find_ticket_or_404(ticket_id, db)
    if ticket.status in {SupportTicketStatus.resolved, SupportTicketStatus.closed}:
        raise HTTPException(
            status_code=409,
            detail="Closed tickets cannot be reclassified",
        )
    ticket.assigned_to = classification.assigned_to
    ticket.classified_by = classification.classified_by
    ticket.classification_notes = classification.classification_notes
    ticket.status = (
        SupportTicketStatus.assigned_to_technical
        if classification.assigned_to
        != SupportTicketAssignee.customer_service
        else SupportTicketStatus.triaged
    )
    record_audit_event(
        db,
        actor=classification.classified_by,
        action="support_ticket.classified",
        entity_type="SupportTicket",
        entity_id=ticket.id,
        reason=classification.classification_notes or ticket.title,
        after_data={
            "assigned_to": ticket.assigned_to,
            "status": ticket.status,
        },
    )
    db.commit()
    db.refresh(ticket)
    return find_ticket_or_404(ticket.id, db)


@router.post("/{ticket_id}/resolve", response_model=SupportTicketRead)
def resolve_ticket(
    ticket_id: UUID,
    resolution: SupportTicketResolve,
    db: Session = Depends(get_db),
) -> SupportTicket:
    ticket = find_ticket_or_404(ticket_id, db)
    if ticket.status == SupportTicketStatus.closed:
        raise HTTPException(status_code=409, detail="Ticket is already closed")
    ticket.status = SupportTicketStatus.resolved
    ticket.resolved_at = datetime.now(UTC)
    ticket.resolution_notes = resolution.resolution_notes
    record_audit_event(
        db,
        actor=resolution.resolved_by,
        action="support_ticket.resolved",
        entity_type="SupportTicket",
        entity_id=ticket.id,
        reason=resolution.resolution_notes,
        after_data={"status": ticket.status},
    )
    db.commit()
    db.refresh(ticket)
    return find_ticket_or_404(ticket.id, db)
