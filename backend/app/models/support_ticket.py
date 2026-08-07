from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SupportTicketCategory(str, Enum):
    service_issue = "service_issue"
    payment_issue = "payment_issue"
    billing_question = "billing_question"
    account_data = "account_data"
    installation_request = "installation_request"
    other = "other"


class SupportTicketPriority(str, Enum):
    low = "low"
    normal = "normal"
    high = "high"
    urgent = "urgent"


class SupportTicketStatus(str, Enum):
    new = "new"
    triaged = "triaged"
    assigned_to_technical = "assigned_to_technical"
    waiting_customer = "waiting_customer"
    resolved = "resolved"
    closed = "closed"


class SupportTicketAssignee(str, Enum):
    customer_service = "customer_service"
    network_technician = "network_technician"
    installer = "installer"


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    customer_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        index=True,
    )
    service_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("services.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    category: Mapped[SupportTicketCategory] = mapped_column(
        SqlEnum(
            SupportTicketCategory,
            name="support_ticket_category",
            native_enum=False,
            validate_strings=True,
        )
    )
    priority: Mapped[SupportTicketPriority] = mapped_column(
        SqlEnum(
            SupportTicketPriority,
            name="support_ticket_priority",
            native_enum=False,
            validate_strings=True,
        ),
        default=SupportTicketPriority.normal,
    )
    status: Mapped[SupportTicketStatus] = mapped_column(
        SqlEnum(
            SupportTicketStatus,
            name="support_ticket_status",
            native_enum=False,
            validate_strings=True,
        ),
        default=SupportTicketStatus.new,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    evidence_reference: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    reported_by: Mapped[str] = mapped_column(String(150))
    created_by: Mapped[str] = mapped_column(String(150))
    assigned_to: Mapped[SupportTicketAssignee | None] = mapped_column(
        SqlEnum(
            SupportTicketAssignee,
            name="support_ticket_assignee",
            native_enum=False,
            validate_strings=True,
        ),
        nullable=True,
    )
    classified_by: Mapped[str | None] = mapped_column(String(150), nullable=True)
    classification_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    customer = relationship("Customer")
    service = relationship("Service")
