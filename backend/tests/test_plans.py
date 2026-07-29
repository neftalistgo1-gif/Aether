import unittest
from datetime import date, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.plans import (
    change_plan_price,
    create_plan,
    deactivate_plan,
    list_plans,
)
from app.api.v1.endpoints.services import create_service
from app.db.base import Base
from app.models.audit import AuditEvent
from app.models.customer import Customer
from app.models.mikrotik import MikrotikRouter, NetworkControlCommand
from app.models.network_assignment import NetworkAssignment
from app.models.plan import PlanStatus
from app.schemas.plan import (
    PlanCreate,
    PlanDeactivate,
    PlanPriceChange,
)
from app.schemas.service import ServiceCreate


class PlanTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def plan_data(self, name: str = "Hogar 20 Mbps") -> PlanCreate:
        return PlanCreate(
            name=name,
            speed="20 Mbps",
            description="Internet residencial",
            monthly_price=Decimal("500.00"),
            valid_from=date.today() - timedelta(days=30),
            created_by="Gerencia",
            reason="Alta inicial del plan",
        )

    def test_create_plan_has_one_current_price_and_audit(self) -> None:
        plan = create_plan(self.plan_data(), self.db)

        self.assertEqual(plan.status, PlanStatus.active)
        self.assertEqual(plan.current_price, Decimal("500.00"))
        self.assertEqual(len(plan.prices), 1)
        event = self.db.scalar(
            select(AuditEvent).where(
                AuditEvent.entity_id == str(plan.id),
                AuditEvent.action == "plan.created",
            )
        )
        self.assertIsNotNone(event)

    def test_price_change_closes_previous_period(self) -> None:
        plan = create_plan(self.plan_data(), self.db)
        changed = change_plan_price(
            plan.id,
            PlanPriceChange(
                monthly_price=Decimal("550.00"),
                effective_from=date.today(),
                changed_by="Gerencia",
                reason="Actualizacion de tarifa publicada",
            ),
            self.db,
        )

        self.assertEqual(changed.current_price, Decimal("550.00"))
        self.assertEqual(len(changed.prices), 2)
        self.assertEqual(
            changed.prices[0].valid_until,
            date.today() - timedelta(days=1),
        )
        self.assertIsNone(changed.prices[1].valid_until)

    def test_plan_price_change_does_not_modify_service_agreement(self) -> None:
        plan = create_plan(self.plan_data(), self.db)
        customer = Customer(
            full_name="Cliente con precio acordado",
            phones=["8998889900"],
        )
        self.db.add(customer)
        self.db.commit()
        service = create_service(
            ServiceCreate(
                customer_id=customer.id,
                amr_code="AMR981",
                address="Calle Plan 20, Reynosa",
                plan_name=plan.name,
                monthly_price=Decimal("450.00"),
                payment_day=15,
            ),
            self.db,
        )

        change_plan_price(
            plan.id,
            PlanPriceChange(
                monthly_price=Decimal("550.00"),
                effective_from=date.today(),
                changed_by="Gerencia",
                reason="Nueva tarifa general",
            ),
            self.db,
        )
        self.db.refresh(service)
        self.assertEqual(service.plan_name, "Hogar 20 Mbps")
        self.assertEqual(service.monthly_price, Decimal("450.00"))

    def test_duplicate_name_and_invalid_price_period_are_rejected(self) -> None:
        plan = create_plan(self.plan_data(), self.db)
        with self.assertRaises(HTTPException) as duplicate:
            create_plan(self.plan_data(), self.db)
        self.assertEqual(duplicate.exception.status_code, 409)

        with self.assertRaises(HTTPException) as invalid_period:
            change_plan_price(
                plan.id,
                PlanPriceChange(
                    monthly_price=Decimal("550.00"),
                    effective_from=plan.prices[0].valid_from,
                    changed_by="Gerencia",
                    reason="Periodo invalido",
                ),
                self.db,
            )
        self.assertEqual(invalid_period.exception.status_code, 409)

    def test_deactivation_closes_offer_without_touching_history(self) -> None:
        plan = create_plan(self.plan_data(), self.db)
        inactive = deactivate_plan(
            plan.id,
            PlanDeactivate(
                deactivated_by="Gerencia",
                reason="Oferta retirada",
            ),
            self.db,
        )

        self.assertEqual(inactive.status, PlanStatus.inactive)
        self.assertIsNone(inactive.current_price)
        self.assertEqual(inactive.prices[0].valid_until, date.today())
        self.assertEqual(
            [item.id for item in list_plans(PlanStatus.inactive, self.db)],
            [plan.id],
        )
        with self.assertRaises(HTTPException):
            change_plan_price(
                plan.id,
                PlanPriceChange(
                    monthly_price=Decimal("600.00"),
                    effective_from=date.today(),
                    changed_by="Gerencia",
                    reason="Intento sobre plan inactivo",
                ),
                self.db,
            )


if __name__ == "__main__":
    unittest.main()
