from datetime import UTC, datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.notification import (
    NotificationChannel,
    NotificationPurpose,
    NotificationStatus,
)


class NotificationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: UUID
    service_id: UUID | None = None
    channel: NotificationChannel
    purpose: NotificationPurpose
    status: NotificationStatus
    recipient: str = Field(min_length=3, max_length=254)
    message_summary: str = Field(min_length=3, max_length=500)
    provider_reference: str | None = Field(default=None, max_length=250)
    evidence_reference: str | None = Field(default=None, max_length=500)
    failure_reason: str | None = Field(
        default=None,
        min_length=3,
        max_length=1000,
    )
    occurred_at: datetime
    recorded_by: str = Field(min_length=2, max_length=150)

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if (
            self.purpose == NotificationPurpose.suspension_warning
            and self.service_id is None
        ):
            raise ValueError(
                "A suspension warning must be linked to a service"
            )
        occurred_at = self.occurred_at
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=UTC)
        if occurred_at > datetime.now(UTC):
            raise ValueError("occurred_at cannot be in the future")
        if self.status == NotificationStatus.delivered:
            if self.failure_reason is not None:
                raise ValueError(
                    "A delivered notification cannot have failure_reason"
                )
            if (
                self.channel
                in {
                    NotificationChannel.whatsapp,
                    NotificationChannel.sms,
                    NotificationChannel.email,
                }
                and self.provider_reference is None
                and self.evidence_reference is None
            ):
                raise ValueError(
                    "Digital delivery requires provider or evidence reference"
                )
        elif self.failure_reason is None:
            raise ValueError(
                "failure_reason is required for a failed notification"
            )
        return self


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    service_id: UUID | None
    channel: NotificationChannel
    purpose: NotificationPurpose
    status: NotificationStatus
    recipient: str
    message_summary: str
    provider_reference: str | None
    has_evidence: bool
    failure_reason: str | None
    occurred_at: datetime
    recorded_by: str
    recorded_at: datetime
