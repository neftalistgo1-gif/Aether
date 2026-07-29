from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.service_plan_change import ServicePlanChange


def agreed_price_for_period(
    service_id: UUID,
    billing_period: date,
    current_price: Decimal,
    db: Session,
) -> Decimal:
    latest_effective_change = db.scalar(
        select(ServicePlanChange)
        .where(
            ServicePlanChange.service_id == service_id,
            ServicePlanChange.billing_effective_period <= billing_period,
        )
        .order_by(
            ServicePlanChange.billing_effective_period.desc(),
            ServicePlanChange.changed_at.desc(),
            ServicePlanChange.id.desc(),
        )
        .limit(1)
    )
    if latest_effective_change is not None:
        return latest_effective_change.new_monthly_price

    earliest_change = db.scalar(
        select(ServicePlanChange)
        .where(ServicePlanChange.service_id == service_id)
        .order_by(
            ServicePlanChange.billing_effective_period,
            ServicePlanChange.changed_at,
            ServicePlanChange.id,
        )
        .limit(1)
    )
    if earliest_change is not None:
        return earliest_change.previous_monthly_price
    return current_price
