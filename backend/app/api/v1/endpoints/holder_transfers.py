from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.endpoints.services import find_service_or_404
from app.db.session import get_db
from app.models.customer import Customer
from app.models.holder_transfer import HolderTransfer
from app.models.service_operations import Cancellation, CancellationStatus
from app.models.service import (
    Service,
    ServiceEvent,
    ServiceEventType,
    ServiceHolder,
    ServiceStatus,
)
from app.schemas.holder_transfer import (
    HolderTransferCreate,
    HolderTransferRead,
    ServiceHolderAssignCreate,
    ServiceHolderRead,
)
from app.services.audit import record_audit_event
from app.services.contracts import active_contract_for_service

router = APIRouter(prefix="/api/v1/services", tags=["holder transfers"])


def find_service_for_update(service_id: UUID, db: Session) -> Service:
    service = db.scalar(
        select(Service)
        .where(Service.id == service_id)
        .with_for_update()
    )
    if service is None:
        raise HTTPException(status_code=404, detail="Service not found")
    return service


def find_current_holder_for_update(
    service_id: UUID,
    db: Session,
) -> ServiceHolder:
    holder = db.scalar(
        select(ServiceHolder)
        .where(
            ServiceHolder.service_id == service_id,
            ServiceHolder.end_date.is_(None),
        )
        .with_for_update()
    )
    if holder is None:
        raise HTTPException(
            status_code=409,
            detail="Service has no current holder",
        )
    return holder


def ensure_service_can_change_holder(service: Service, db: Session) -> None:
    if service.status == ServiceStatus.cancelled:
        raise HTTPException(
            status_code=409,
            detail="A cancelled service cannot change holder",
        )
    scheduled_cancellation = db.scalar(
        select(Cancellation).where(
            Cancellation.service_id == service.id,
            Cancellation.status == CancellationStatus.scheduled,
        )
    )
    if scheduled_cancellation is not None:
        raise HTTPException(
            status_code=409,
            detail="Resolve the scheduled cancellation before changing holder",
        )


@router.post(
    "/{service_id}/holder-transfers",
    response_model=HolderTransferRead,
    status_code=status.HTTP_201_CREATED,
)
def transfer_service_holder(
    service_id: UUID,
    data: HolderTransferCreate,
    db: Session = Depends(get_db),
) -> HolderTransfer:
    service = find_service_for_update(service_id, db)
    ensure_service_can_change_holder(service, db)
    if data.effective_date != date.today():
        raise HTTPException(
            status_code=409,
            detail="Holder transfers must take effect today",
        )
    if active_contract_for_service(service.id, db, for_update=True) is not None:
        raise HTTPException(
            status_code=409,
            detail="Terminate the active contract before changing holder",
        )
    new_customer = db.get(Customer, data.new_customer_id)
    if new_customer is None:
        raise HTTPException(status_code=404, detail="New customer not found")

    previous_holder = find_current_holder_for_update(service.id, db)
    if previous_holder.customer_id == new_customer.id:
        raise HTTPException(
            status_code=409,
            detail="The customer is already the current holder",
        )
    if data.effective_date < previous_holder.start_date:
        raise HTTPException(
            status_code=409,
            detail="Transfer cannot precede the current holder period",
        )

    previous_holder.end_date = data.effective_date
    previous_holder.change_reason = data.reason
    new_holder = ServiceHolder(
        service_id=service.id,
        customer_id=new_customer.id,
        start_date=data.effective_date,
        change_reason=data.reason,
    )
    db.add(new_holder)

    try:
        db.flush()
        transfer = HolderTransfer(
            service_id=service.id,
            previous_holder_id=previous_holder.id,
            new_holder_id=new_holder.id,
            previous_customer_id=previous_holder.customer_id,
            new_customer_id=new_customer.id,
            effective_date=data.effective_date,
            transferred_by=data.transferred_by,
            reason=data.reason,
            contract_reference=data.contract_reference,
        )
        db.add(transfer)
        db.flush()
        service.events.append(
            ServiceEvent(
                event_type=ServiceEventType.details_updated,
                changes={
                    "current_customer_id": {
                        "before": str(previous_holder.customer_id),
                        "after": str(new_customer.id),
                    },
                    "holder_transfer_id": str(transfer.id),
                },
                reason=data.reason,
            )
        )
        record_audit_event(
            db,
            actor=data.transferred_by,
            action="service.holder_transferred",
            entity_type="Service",
            entity_id=service.id,
            reason=data.reason,
            before_data={
                "current_customer_id": previous_holder.customer_id,
            },
            after_data={
                "current_customer_id": new_customer.id,
                "holder_transfer_id": transfer.id,
                "effective_date": data.effective_date,
                "contract_reference": data.contract_reference,
            },
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="The holder changed concurrently; reload and try again",
        ) from exc

    return db.get(HolderTransfer, transfer.id)


@router.post(
    "/{service_id}/holders",
    response_model=ServiceHolderRead,
    status_code=status.HTTP_201_CREATED,
)
def assign_service_holder(
    service_id: UUID,
    data: ServiceHolderAssignCreate,
    db: Session = Depends(get_db),
) -> ServiceHolder:
    """Assign a holder only when a service was registered without one."""
    service = find_service_for_update(service_id, db)
    ensure_service_can_change_holder(service, db)
    if db.get(Customer, data.customer_id) is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    current_holder = db.scalar(
        select(ServiceHolder)
        .where(
            ServiceHolder.service_id == service.id,
            ServiceHolder.end_date.is_(None),
        )
        .with_for_update()
    )
    if current_holder is not None:
        raise HTTPException(
            status_code=409,
            detail="Service already has a holder; use a holder transfer",
        )

    holder = ServiceHolder(
        service_id=service.id,
        customer_id=data.customer_id,
        start_date=date.today(),
        change_reason=data.reason,
    )
    db.add(holder)
    try:
        db.flush()
        service.events.append(
            ServiceEvent(
                event_type=ServiceEventType.details_updated,
                changes={"current_customer_id": {"before": None, "after": str(data.customer_id)}},
                reason=data.reason,
            )
        )
        record_audit_event(
            db,
            actor=data.assigned_by,
            action="service.holder_assigned",
            entity_type="Service",
            entity_id=service.id,
            reason=data.reason,
            after_data={"current_customer_id": data.customer_id},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="The holder changed concurrently; reload and try again",
        ) from exc
    return db.get(ServiceHolder, holder.id)


@router.get(
    "/{service_id}/holders",
    response_model=list[ServiceHolderRead],
)
def list_service_holders(
    service_id: UUID,
    db: Session = Depends(get_db),
) -> list[ServiceHolder]:
    find_service_or_404(service_id, db)
    return list(
        db.scalars(
            select(ServiceHolder)
            .where(ServiceHolder.service_id == service_id)
            .order_by(ServiceHolder.start_date, ServiceHolder.id)
        )
    )


@router.get(
    "/{service_id}/holder-transfers",
    response_model=list[HolderTransferRead],
)
def list_holder_transfers(
    service_id: UUID,
    db: Session = Depends(get_db),
) -> list[HolderTransfer]:
    find_service_or_404(service_id, db)
    return list(
        db.scalars(
            select(HolderTransfer)
            .where(HolderTransfer.service_id == service_id)
            .order_by(
                HolderTransfer.effective_date,
                HolderTransfer.transferred_at,
                HolderTransfer.id,
            )
        )
    )
