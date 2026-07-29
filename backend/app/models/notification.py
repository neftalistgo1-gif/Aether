from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NotificationChannel(str, Enum):
    whatsapp = "whatsapp"
    sms = "sms"
    email = "email"
    phone = "phone"
    in_person = "in_person"


class NotificationPurpose(str, Enum):
    suspension_warning = "suspension_warning"
    payment_reminder = "payment_reminder"
    service_update = "service_update"
    general = "general"


class NotificationStatus(str, Enum):
    delivered = "delivered"
    failed = "failed"


class CustomerNotification(Base):
    __tablename__ = "customer_notifications"

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
    channel: Mapped[NotificationChannel] = mapped_column(
        SqlEnum(
            NotificationChannel,
            name="notification_channel",
            native_enum=False,
            validate_strings=True,
        ),
        index=True,
    )
    purpose: Mapped[NotificationPurpose] = mapped_column(
        SqlEnum(
            NotificationPurpose,
            name="notification_purpose",
            native_enum=False,
            validate_strings=True,
        ),
        index=True,
    )
    status: Mapped[NotificationStatus] = mapped_column(
        SqlEnum(
            NotificationStatus,
            name="notification_status",
            native_enum=False,
            validate_strings=True,
        ),
        index=True,
    )
    recipient: Mapped[str] = mapped_column(String(254))
    message_summary: Mapped[str] = mapped_column(String(500))
    provider_reference: Mapped[str | None] = mapped_column(
        String(250),
        nullable=True,
    )
    evidence_reference: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recorded_by: Mapped[str] = mapped_column(String(150))
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    @property
    def has_evidence(self) -> bool:
        return self.evidence_reference is not None
