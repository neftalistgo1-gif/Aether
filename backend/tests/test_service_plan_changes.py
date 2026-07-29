import unittest
from datetime import date, timedelta
from decimal import Decimal

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.charges import (
    create_monthly_charge,
    month_start,
    next_month,
)
from app.api.v1.endpoints.plans import create_plan, deactivate_plan
from app.api.v1.endpoints.service_plan_changes import (
    change_service_plan,
    list_service_plan_changes,
)
from app.api.v1.endpoints.services import create_service
from app.db.base import Base
from app.models.audit import AuditEvent
from app.models.customer import Customer
from app.models.holder_transfer import HolderTransfer
from app.models.mikrotik import MikrotikRouter, NetworkControlCommand
from app.models.network_assignment import NetworkAssignment
from app.models.payment import Payment, PaymentStatusEvent
from app.models.payment_allocation import CreditMovement, PaymentAllocation
from app.models.service import ServiceStatus
from app.models.service_plan_change import ServicePlanChange
from app.schemas.charge import MonthlyChargeCreate
from app.schemas.plan import PlanCreate, PlanDeactivate
from app.schemas.service import ServiceCreate
from app.schemas.service_plan_change import ServicePlanChangeCreate
from app.services.pricing import agreed_price_for_period


def previous_month(value: date) -> date:
    if value.month == 1:
        return date(value.year - 1, 12, 1)
    return date(value.year, value.month - 1, 1)


class ServicePlanChangeTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        customer = Customer(
            full_name="Cliente cambio de plan",
            phones=["8997330001"],
        )
        self.db.add(customer)
        self.db.commit()
        valid_from = date.today() - timedelta(days=30)
        self.original_plan = create_plan(
            PlanCreate(
                name="Hogar 20 Mbps",
                speed="20 Mbps",
                monthly_price=Decimal("500.00"),
                valid_from=valid_from,
                created_by="Administracion",
            ),
            self.db,
        )
        self.target_plan = create_plan(
            PlanCreate(
                name="Hogar 30 Mbps",
                speed="30 Mbps",
                monthly_price=Decimal("600.00"),
                valid_from=valid_from,
                created_by="Administracion",
            ),
            self.db,
        )
        self.service = create_service(
            ServiceCreate(
                customer_id=customer.id,
                amr_code="AMR821",
                address="Calle Plan 21, Reynosa",
                plan_name=self.original_plan.name,
                monthly_price=Decimal("500.00"),
                payment_day=10,
            ),
            self.db,
        )
        self.service.plan_id = self.original_plan.id
        self.service.status = ServiceStatus.active
        current_period = month_start(date.today())
        self.service.activation_date = previous_month(current_period)
        self.service.holders[0].start_date = self.service.activation_date
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def change_data(
        self,
        price: Decimal | None = None,
        custom_reason: str | None = None,
        requested_on: date | None = None,
    ) -> ServicePlanChangeCreate:
        return ServicePlanChangeCreate(
            plan_id=self.target_plan.id,
            agreed_monthly_price=price,
            requested_on=requested_on or date.today(),
            requested_by="Cliente titular",
            applied_by="Soporte tecnico",
            reason="El cliente solicita mayor velocidad",
            custom_price_reason=custom_reason,
        )

    def test_speed_changes_now_but_price_starts_next_billing_period(self) -> None:
        current_period = month_start(date.today())
        next_period = next_month(current_period)

        change = change_service_plan(
            self.service.id,
            self.change_data(),
            self.db,
        )

        self.db.refresh(self.service)
        self.assertEqual(self.service.plan_id, self.target_plan.id)
        self.assertEqual(self.service.plan_name, self.target_plan.name)
        self.assertEqual(self.service.monthly_price, Decimal("600.00"))
        self.assertEqual(change.billing_effective_period, next_period)
        self.assertEqual(
            agreed_price_for_period(
                self.service.id,
                current_period,
                self.service.monthly_price,
                self.db,
            ),
            Decimal("500.00"),
        )
        self.assertEqual(
            agreed_price_for_period(
                self.service.id,
                next_period,
                self.service.monthly_price,
                self.db,
            ),
            Decimal("600.00"),
        )
        delayed_charge = create_monthly_charge(
            self.service.id,
            MonthlyChargeCreate(
                billing_period=current_period,
                generated_by="Proceso mensual",
            ),
            self.db,
        )
        self.assertEqual(delayed_charge.amount, Decimal("500.00"))
        self.assertEqual(
            list_service_plan_changes(self.service.id, self.db),
            [change],
        )
        audit = self.db.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "service.plan_changed"
            )
        )
        self.assertIsNotNone(audit)

    def test_next_unbilled_due_date_can_use_new_price(self) -> None:
        self.service.payment_day = date.today().day
        self.db.commit()
        change = change_service_plan(
            self.service.id,
            self.change_data(),
            self.db,
        )
        current_period = month_start(date.today())
        self.assertEqual(change.billing_effective_period, current_period)
        charge = create_monthly_charge(
            self.service.id,
            MonthlyChargeCreate(
                billing_period=current_period,
                generated_by="Proceso mensual",
            ),
            self.db,
        )
        self.assertEqual(charge.amount, Decimal("600.00"))

    def test_existing_monthly_charge_is_never_repriced(self) -> None:
        self.service.payment_day = date.today().day
        self.db.commit()
        current_period = month_start(date.today())
        original_charge = create_monthly_charge(
            self.service.id,
            MonthlyChargeCreate(
                billing_period=current_period,
                generated_by="Proceso mensual",
            ),
            self.db,
        )
        change = change_service_plan(
            self.service.id,
            self.change_data(),
            self.db,
        )
        self.db.refresh(original_charge)
        self.assertEqual(original_charge.amount, Decimal("500.00"))
        self.assertEqual(
            change.billing_effective_period,
            next_month(current_period),
        )

    def test_custom_agreed_price_requires_and_preserves_reason(self) -> None:
        with self.assertRaises(ValidationError):
            self.change_data(price=Decimal("550.00"))

        change = change_service_plan(
            self.service.id,
            self.change_data(
                price=Decimal("550.00"),
                custom_reason="Promocion por antiguedad",
            ),
            self.db,
        )
        self.assertEqual(change.new_monthly_price, Decimal("550.00"))
        self.assertEqual(
            change.custom_price_reason,
            "Promocion por antiguedad",
        )

    def test_inactive_plan_and_invalid_service_state_are_rejected(self) -> None:
        deactivate_plan(
            self.target_plan.id,
            PlanDeactivate(
                deactivated_by="Administracion",
                reason="Oferta retirada",
            ),
            self.db,
        )
        with self.assertRaises(HTTPException) as inactive:
            change_service_plan(
                self.service.id,
                self.change_data(),
                self.db,
            )
        self.assertEqual(inactive.exception.status_code, 409)

        self.service.status = ServiceStatus.pending
        self.db.commit()
        with self.assertRaises(HTTPException) as pending:
            change_service_plan(
                self.service.id,
                self.change_data(),
                self.db,
            )
        self.assertEqual(pending.exception.status_code, 409)

    def test_change_cannot_be_backdated_or_future_dated(self) -> None:
        for invalid_date in (
            date.today() - timedelta(days=1),
            date.today() + timedelta(days=1),
        ):
            with self.subTest(invalid_date=invalid_date):
                with self.assertRaises(HTTPException) as invalid:
                    change_service_plan(
                        self.service.id,
                        self.change_data(requested_on=invalid_date),
                        self.db,
                    )
                self.assertEqual(invalid.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
