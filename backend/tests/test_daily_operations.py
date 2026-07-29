import unittest
from datetime import date, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.services import (
    create_service,
    transition_service_status,
)
from app.db.base import Base
from app.models.charge import Charge, ChargeType
from app.models.customer import Customer
from app.models.daily_operation import DailyOperationRun
from app.models.extension import Extension, ExtensionStatus
from app.models.service import ServiceStatus
from app.schemas.service import ServiceCreate, ServiceTransitionCreate
from app.services.daily_operations import execute_daily_operations


def previous_month(value: date) -> date:
    if value.month == 1:
        return date(value.year - 1, 12, 1)
    return date(value.year, value.month - 1, 1)


class DailyOperationsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        customer = Customer(
            full_name="Cliente de proceso diario",
            phones=["8997771122"],
        )
        self.db.add(customer)
        self.db.commit()
        service = create_service(
            ServiceCreate(
                customer_id=customer.id,
                amr_code="AMR925",
                address="Domicilio para proceso diario",
                plan_name="Hogar 30 Mbps",
                monthly_price=Decimal("600.00"),
                payment_day=min(date.today().day, 28),
            ),
            self.db,
        )
        self.service = transition_service_status(
            service.id,
            ServiceTransitionCreate(
                target_status=ServiceStatus.active,
                reason="Servicio listo para automatizacion",
            ),
            self.db,
        )
        activation = previous_month(date.today()).replace(day=1)
        self.service.activation_date = activation
        self.service.holders[0].start_date = activation
        self.extension = Extension(
            customer_id=customer.id,
            service_id=self.service.id,
            original_due_date=date.today() - timedelta(days=10),
            promised_date=date.today() - timedelta(days=1),
            reason="Prorroga vencida para prueba",
            authorized_by="Administracion",
            evidence_reference="private/evidence/test",
            status=ExtensionStatus.active,
        )
        self.db.add(self.extension)
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_dry_run_changes_nothing(self) -> None:
        result = execute_daily_operations(
            date.today(),
            True,
            "Administrador",
            self.db,
        )
        self.assertTrue(result.dry_run)
        self.assertEqual(result.monthly_charges_created, 1)
        self.assertEqual(result.extensions_expired, 1)
        self.assertEqual(
            self.db.scalar(select(func.count()).select_from(Charge)),
            0,
        )
        self.assertIsNone(self.db.scalar(select(DailyOperationRun)))
        self.db.refresh(self.extension)
        self.assertEqual(self.extension.status, ExtensionStatus.active)

    def test_live_run_is_atomic_and_idempotent(self) -> None:
        first = execute_daily_operations(
            date.today(),
            False,
            "Administrador",
            self.db,
        )
        second = execute_daily_operations(
            date.today(),
            False,
            "Administrador",
            self.db,
        )
        self.assertFalse(first.dry_run)
        self.assertEqual(second.id, first.id)
        self.assertEqual(first.monthly_charges_created, 1)
        charges = list(
            self.db.scalars(
                select(Charge).where(
                    Charge.charge_type == ChargeType.monthly
                )
            )
        )
        self.assertEqual(len(charges), 1)
        self.assertEqual(charges[0].amount, Decimal("600.00"))
        self.db.refresh(self.extension)
        self.assertEqual(self.extension.status, ExtensionStatus.expired)

    def test_future_execution_is_rejected(self) -> None:
        with self.assertRaises(HTTPException) as rejected:
            execute_daily_operations(
                date.today() + timedelta(days=1),
                False,
                "Administrador",
                self.db,
            )
        self.assertEqual(rejected.exception.status_code, 409)
