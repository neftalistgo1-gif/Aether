from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.charge import Charge, ChargeStatus
from app.models.payment_allocation import CreditMovement, CreditMovementType


def customer_credit_balance(customer_id, db: Session) -> Decimal:
    balance = db.scalar(
        select(func.coalesce(func.sum(CreditMovement.amount), 0)).where(
            CreditMovement.customer_id == customer_id
        )
    )
    return Decimal(balance or 0)


def apply_credit_to_charge(
    charge: Charge,
    performed_by: str,
    db: Session,
) -> Decimal:
    available = customer_credit_balance(charge.customer_id, db)
    if available <= 0 or charge.outstanding_balance <= 0:
        return Decimal("0.00")
    applied = min(available, charge.outstanding_balance)
    db.add(
        CreditMovement(
            customer_id=charge.customer_id,
            service_id=charge.service_id,
            charge_id=charge.id,
            movement_type=CreditMovementType.charge_application,
            amount=-applied,
            performed_by=performed_by,
            reason="Credit automatically applied to monthly charge",
        )
    )
    charge.outstanding_balance -= applied
    charge.status = (
        ChargeStatus.paid
        if charge.outstanding_balance == 0
        else ChargeStatus.partial
    )
    return applied
