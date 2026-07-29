from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models.plan import Plan, PlanPrice, PlanStatus
from app.schemas.plan import (
    PlanCreate,
    PlanDeactivate,
    PlanPriceChange,
    PlanRead,
)
from app.services.audit import record_audit_event

router = APIRouter(prefix="/api/v1/plans", tags=["plans"])


def plan_query():
    return select(Plan).options(selectinload(Plan.prices))


def find_plan_or_404(plan_id: UUID, db: Session) -> Plan:
    plan = db.scalar(plan_query().where(Plan.id == plan_id))
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


def find_plan_for_update(plan_id: UUID, db: Session) -> Plan:
    plan = db.scalar(
        plan_query().where(Plan.id == plan_id).with_for_update()
    )
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


@router.post("", response_model=PlanRead, status_code=201)
def create_plan(
    plan_data: PlanCreate,
    db: Session = Depends(get_db),
) -> Plan:
    if plan_data.valid_from > date.today():
        raise HTTPException(
            status_code=409,
            detail="Initial plan price cannot start in the future",
        )
    plan = Plan(
        name=plan_data.name.strip(),
        speed=plan_data.speed.strip(),
        description=plan_data.description,
        status=PlanStatus.active,
    )
    plan.prices.append(
        PlanPrice(
            monthly_price=plan_data.monthly_price,
            valid_from=plan_data.valid_from,
            changed_by=plan_data.created_by,
            reason=plan_data.reason,
        )
    )
    db.add(plan)
    try:
        db.flush()
        record_audit_event(
            db,
            actor=plan_data.created_by,
            action="plan.created",
            entity_type="Plan",
            entity_id=plan.id,
            reason=plan_data.reason,
            after_data={
                "name": plan.name,
                "speed": plan.speed,
                "monthly_price": plan_data.monthly_price,
                "valid_from": plan_data.valid_from,
            },
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Plan name already exists",
        ) from exc
    return find_plan_or_404(plan.id, db)


@router.get("", response_model=list[PlanRead])
def list_plans(
    plan_status: PlanStatus | None = None,
    db: Session = Depends(get_db),
) -> list[Plan]:
    statement = plan_query()
    if plan_status is not None:
        statement = statement.where(Plan.status == plan_status)
    return list(db.scalars(statement.order_by(Plan.name)).unique())


@router.get("/{plan_id}", response_model=PlanRead)
def get_plan(
    plan_id: UUID,
    db: Session = Depends(get_db),
) -> Plan:
    return find_plan_or_404(plan_id, db)


@router.post("/{plan_id}/prices", response_model=PlanRead)
def change_plan_price(
    plan_id: UUID,
    price_data: PlanPriceChange,
    db: Session = Depends(get_db),
) -> Plan:
    plan = find_plan_for_update(plan_id, db)
    if plan.status != PlanStatus.active:
        raise HTTPException(
            status_code=409,
            detail="An inactive plan cannot receive a new price",
        )
    if price_data.effective_from > date.today():
        raise HTTPException(
            status_code=409,
            detail="Price changes cannot start in the future",
        )
    current = next(
        (price for price in reversed(plan.prices) if price.valid_until is None),
        None,
    )
    if current is None:
        raise HTTPException(status_code=409, detail="Plan has no current price")
    if price_data.effective_from <= current.valid_from:
        raise HTTPException(
            status_code=409,
            detail="New price must start after the current price",
        )
    if price_data.monthly_price == current.monthly_price:
        raise HTTPException(status_code=409, detail="Plan price has not changed")
    previous_price = current.monthly_price
    current.valid_until = price_data.effective_from - timedelta(days=1)
    plan.prices.append(
        PlanPrice(
            monthly_price=price_data.monthly_price,
            valid_from=price_data.effective_from,
            changed_by=price_data.changed_by,
            reason=price_data.reason,
        )
    )
    record_audit_event(
        db,
        actor=price_data.changed_by,
        action="plan.price_changed",
        entity_type="Plan",
        entity_id=plan.id,
        reason=price_data.reason,
        before_data={"monthly_price": previous_price},
        after_data={
            "monthly_price": price_data.monthly_price,
            "effective_from": price_data.effective_from,
        },
    )
    db.commit()
    return find_plan_or_404(plan.id, db)


@router.post("/{plan_id}/deactivate", response_model=PlanRead)
def deactivate_plan(
    plan_id: UUID,
    deactivation: PlanDeactivate,
    db: Session = Depends(get_db),
) -> Plan:
    plan = find_plan_for_update(plan_id, db)
    if plan.status == PlanStatus.inactive:
        raise HTTPException(status_code=409, detail="Plan is already inactive")
    current = next(
        (price for price in reversed(plan.prices) if price.valid_until is None),
        None,
    )
    if current is not None:
        current.valid_until = date.today()
    plan.status = PlanStatus.inactive
    plan.deactivated_at = datetime.now(UTC)
    plan.deactivated_by = deactivation.deactivated_by
    plan.deactivation_reason = deactivation.reason
    record_audit_event(
        db,
        actor=deactivation.deactivated_by,
        action="plan.deactivated",
        entity_type="Plan",
        entity_id=plan.id,
        reason=deactivation.reason,
        before_data={"status": PlanStatus.active},
        after_data={"status": plan.status},
    )
    db.commit()
    return find_plan_or_404(plan.id, db)
