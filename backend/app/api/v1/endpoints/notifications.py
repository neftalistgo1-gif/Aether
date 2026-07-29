from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.endpoints.services import find_service_or_404
from app.db.session import get_db
from app.models.customer import Customer
from app.models.notification import (
    CustomerNotification,
    NotificationPurpose,
    NotificationStatus,
)
from app.schemas.notification import NotificationCreate, NotificationRead
from app.services.audit import record_audit_event

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.post(
    "",
    response_model=NotificationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_notification(
    data: NotificationCreate,
    db: Session = Depends(get_db),
) -> CustomerNotification:
    if db.get(Customer, data.customer_id) is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    if data.service_id is not None:
        service = find_service_or_404(data.service_id, db)
        if not any(
            holder.customer_id == data.customer_id
            for holder in service.holders
        ):
            raise HTTPException(
                status_code=409,
                detail="Customer does not belong to service history",
            )
    notification = CustomerNotification(**data.model_dump())
    db.add(notification)
    db.flush()
    record_audit_event(
        db,
        actor=data.recorded_by,
        action="notification.recorded",
        entity_type="CustomerNotification",
        entity_id=notification.id,
        reason=f"{data.purpose.value} via {data.channel.value}",
        after_data={
            "customer_id": data.customer_id,
            "service_id": data.service_id,
            "purpose": data.purpose,
            "channel": data.channel,
            "status": data.status,
            "has_evidence": notification.has_evidence,
        },
    )
    db.commit()
    db.refresh(notification)
    return notification


@router.get("", response_model=list[NotificationRead])
def list_notifications(
    db: Session = Depends(get_db),
    customer_id: Annotated[UUID | None, Query()] = None,
    service_id: Annotated[UUID | None, Query()] = None,
    purpose: Annotated[NotificationPurpose | None, Query()] = None,
    notification_status: Annotated[
        NotificationStatus | None,
        Query(alias="status"),
    ] = None,
) -> list[CustomerNotification]:
    statement = select(CustomerNotification)
    if customer_id is not None:
        statement = statement.where(
            CustomerNotification.customer_id == customer_id
        )
    if service_id is not None:
        statement = statement.where(
            CustomerNotification.service_id == service_id
        )
    if purpose is not None:
        statement = statement.where(
            CustomerNotification.purpose == purpose
        )
    if notification_status is not None:
        statement = statement.where(
            CustomerNotification.status == notification_status
        )
    return list(
        db.scalars(
            statement.order_by(
                CustomerNotification.occurred_at.desc(),
                CustomerNotification.id,
            )
        )
    )


@router.get("/{notification_id}", response_model=NotificationRead)
def get_notification(
    notification_id: UUID,
    db: Session = Depends(get_db),
) -> CustomerNotification:
    notification = db.get(CustomerNotification, notification_id)
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notification
