from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.endpoints.charges import month_start, next_month
from app.api.v1.endpoints.plans import find_plan_or_404
from app.api.v1.endpoints.services import find_service_or_404
from app.db.session import get_db
from app.models.charge import Charge, ChargeType
from app.models.contract import ContractAmendmentType
from app.models.plan import PlanStatus
from app.models.service import (
    ServiceEvent,
    ServiceEventType,
    ServiceStatus,
)
from app.models.service_plan_change import ServicePlanChange
from app.schemas.service_plan_change import (
    ServicePlanChangeCreate,
    ServicePlanChangeRead,
)
from app.services.audit import record_audit_event
from app.services.contracts import amend_active_contract

router = APIRouter(prefix="/api/v1/services", tags=["service plan changes"])


def billing_effective_period(
    service,
    requested_on: date,
    db: Session,
) -> date:
    current_period = month_start(requested_on)
    current_due_date = current_period.replace(day=service.payment_day)
    current_charge_exists = db.scalar(
        select(Charge.id)
        .where(
            Charge.service_id == service.id,
            Charge.charge_type == ChargeType.monthly,
            Charge.billing_period == current_period,
        )
        .limit(1)
    )
    period = (
        current_period
        if requested_on <= current_due_date
        and current_charge_exists is None
        else next_month(current_period)
    )
    if service.activation_date is not None:
        first_monthly_period = next_month(
            month_start(service.activation_date)
        )
        period = max(period, first_monthly_period)
    return period


@router.post(
    "/{service_id}/plan-changes",
    response_model=ServicePlanChangeRead,
    status_code=status.HTTP_201_CREATED,
)
def change_service_plan(
    service_id: UUID,
    data: ServicePlanChangeCreate,
    db: Session = Depends(get_db),
) -> ServicePlanChange:
    service = find_service_or_404(service_id, db)
    if service.status not in {
        ServiceStatus.active,
        ServiceStatus.suspended,
    }:
        raise HTTPException(
            status_code=409,
            detail="Only active or suspended services can change plan",
        )
    if data.requested_on != date.today():
        raise HTTPException(
            status_code=409,
            detail="Plan changes must be recorded on the request date",
        )
    plan = find_plan_or_404(data.plan_id, db)
    if plan.status != PlanStatus.active:
        raise HTTPException(
            status_code=409,
            detail="The selected plan is inactive",
        )
    if plan.current_price is None:
        raise HTTPException(
            status_code=409,
            detail="The selected plan has no current price",
        )
    new_price = data.agreed_monthly_price or plan.current_price
    if (
        data.agreed_monthly_price is not None
        and data.agreed_monthly_price == plan.current_price
    ):
        raise HTTPException(
            status_code=409,
            detail="Use the published price without a custom agreement",
        )
    if service.plan_name == plan.name and service.monthly_price == new_price:
        raise HTTPException(
            status_code=409,
            detail="The service already has this plan and price",
        )

    effective_period = billing_effective_period(
        service,
        data.requested_on,
        db,
    )
    change = ServicePlanChange(
        service_id=service.id,
        previous_plan_id=service.plan_id,
        new_plan_id=plan.id,
        previous_plan_name=service.plan_name,
        new_plan_name=plan.name,
        previous_monthly_price=service.monthly_price,
        new_monthly_price=new_price,
        requested_on=data.requested_on,
        billing_effective_period=effective_period,
        requested_by=data.requested_by,
        applied_by=data.applied_by,
        reason=data.reason,
        custom_price_reason=data.custom_price_reason,
    )
    previous_plan_id = service.plan_id
    previous_plan_name = service.plan_name
    previous_price = service.monthly_price
    service.plan_id = plan.id
    service.plan_name = plan.name
    service.monthly_price = new_price
    db.add(change)

    try:
        db.flush()
        amend_active_contract(
            service=service,
            amendment_type=ContractAmendmentType.plan_change,
            before_data={
                "plan_name": previous_plan_name,
                "monthly_price": str(previous_price),
            },
            after_data={
                "plan_name": plan.name,
                "monthly_price": str(new_price),
                "billing_effective_period": effective_period.isoformat(),
            },
            evidence_reference=f"service_plan_change:{change.id}",
            amended_by=data.applied_by,
            reason=data.reason,
            effective_date=data.requested_on,
            db=db,
        )
        service.events.append(
            ServiceEvent(
                event_type=ServiceEventType.details_updated,
                changes={
                    "plan": {
                        "before": previous_plan_name,
                        "after": plan.name,
                    },
                    "monthly_price": {
                        "before": str(previous_price),
                        "after": str(new_price),
                        "billing_effective_period": (
                            effective_period.isoformat()
                        ),
                    },
                    "service_plan_change_id": str(change.id),
                },
                reason=data.reason,
            )
        )
        record_audit_event(
            db,
            actor=data.applied_by,
            action="service.plan_changed",
            entity_type="Service",
            entity_id=service.id,
            reason=data.reason,
            before_data={
                "plan_id": previous_plan_id,
                "plan_name": previous_plan_name,
                "monthly_price": previous_price,
            },
            after_data={
                "plan_id": plan.id,
                "plan_name": plan.name,
                "monthly_price": new_price,
                "billing_effective_period": effective_period,
                "requested_by": data.requested_by,
            },
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Plan change could not be recorded",
        ) from exc
    return db.get(ServicePlanChange, change.id)


@router.get(
    "/{service_id}/plan-changes",
    response_model=list[ServicePlanChangeRead],
)
def list_service_plan_changes(
    service_id: UUID,
    db: Session = Depends(get_db),
) -> list[ServicePlanChange]:
    find_service_or_404(service_id, db)
    return list(
        db.scalars(
            select(ServicePlanChange)
            .where(ServicePlanChange.service_id == service_id)
            .order_by(
                ServicePlanChange.requested_on,
                ServicePlanChange.changed_at,
                ServicePlanChange.id,
            )
        )
    )
