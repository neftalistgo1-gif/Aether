from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.support_ticket import (
    SupportTicketAssignee,
    SupportTicketCategory,
    SupportTicketPriority,
    SupportTicketStatus,
)


class SupportTicketCreate(BaseModel):
    customer_id: UUID
    service_id: UUID | None = None
    category: SupportTicketCategory
    priority: SupportTicketPriority = SupportTicketPriority.normal
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=10, max_length=4000)
    evidence_reference: str | None = Field(default=None, max_length=500)
    reported_by: str = Field(min_length=2, max_length=150)
    created_by: str = Field(min_length=2, max_length=150)


class SupportTicketClassify(BaseModel):
    assigned_to: SupportTicketAssignee
    classified_by: str = Field(min_length=2, max_length=150)
    classification_notes: str | None = Field(default=None, max_length=2000)


class SupportTicketResolve(BaseModel):
    resolved_by: str = Field(min_length=2, max_length=150)
    resolution_notes: str = Field(min_length=3, max_length=4000)


class SupportTicketRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    service_id: UUID | None
    category: SupportTicketCategory
    priority: SupportTicketPriority
    status: SupportTicketStatus
    title: str
    description: str
    evidence_reference: str | None
    reported_by: str
    created_by: str
    assigned_to: SupportTicketAssignee | None
    classified_by: str | None
    classification_notes: str | None
    resolution_notes: str | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
