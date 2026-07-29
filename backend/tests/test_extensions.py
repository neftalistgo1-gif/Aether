import unittest
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.charges import create_charge
from app.api.v1.endpoints.extensions import (
    create_extension,
    fulfill_extension,
    list_extensions,
)
from app.api.v1.endpoints.service_operations import suspend_service
from app.api.v1.endpoints.services import create_service, transition_service_status
from app.db.base import Base
from app.models.charge import ChargeType
from app.models.customer import Customer
from app.models.extension import ExtensionStatus
from app.models.service import ServiceStatus
from app.models.service_operations import NetworkOperationResult
from app.schemas.charge import ChargeCreate
from app.schemas.extension import ExtensionCreate, ExtensionResolve
from app.schemas.service import ServiceCreate, ServiceTransitionCreate
from app.schemas.service_operations import SuspensionCreate


class ExtensionTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.customer = Customer(full_name="Cliente con prorroga", phones=["8996667788"])
        self.db.add(self.customer)
        self.db.commit()
        service = create_service(
            ServiceCreate(
                customer_id=self.customer.id,
                amr_code="AMR951",
                address="Domicilio con prorroga, Reynosa",
                plan_name="Hogar 20 Mbps",
                monthly_price=Decimal("500.00"),
                payment_day=5,
            ),
            self.db,
        )
        self.service = transition_service_status(
            service.id,
            ServiceTransitionCreate(target_status=ServiceStatus.active, reason="Instalacion terminada"),
            self.db,
        )

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def add_debt(self) -> None:
        create_charge(
            self.service.id,
            ChargeCreate(
                charge_type=ChargeType.other,
                description="Deuda pendiente",
                amount=Decimal("500.00"),
                due_date=date.today(),
                generated_by="Atencion a clientes",
            ),
            self.db,
        )

    def extension_data(self) -> ExtensionCreate:
        return ExtensionCreate(
            original_due_date=date.today(),
            promised_date=date.today() + timedelta(days=3),
            reason="Cliente solicita tiempo adicional",
            authorized_by="Atencion a clientes",
            evidence_reference="whatsapp/prorroga-951",
        )

    def test_extension_requires_debt(self) -> None:
        with self.assertRaises(HTTPException) as context:
            create_extension(self.service.id, self.extension_data(), self.db)
        self.assertEqual(context.exception.status_code, 409)

    def test_only_one_active_extension_and_resolution_is_audited(self) -> None:
        self.add_debt()
        extension = create_extension(self.service.id, self.extension_data(), self.db)
        with self.assertRaises(HTTPException):
            create_extension(self.service.id, self.extension_data(), self.db)

        fulfilled = fulfill_extension(
            self.service.id,
            extension.id,
            ExtensionResolve(performed_by="Administrador", reason="Cliente cumplio el acuerdo"),
            self.db,
        )
        self.assertEqual(fulfilled.status, ExtensionStatus.fulfilled)
        self.assertIsNotNone(fulfilled.resolved_at)

    def test_active_extension_prevents_suspension_even_if_input_says_none(self) -> None:
        self.add_debt()
        create_extension(self.service.id, self.extension_data(), self.db)
        with self.assertRaises(HTTPException) as context:
            suspend_service(
                self.service.id,
                SuspensionCreate(
                    scheduled_for=date.today(),
                    reason="Falta de pago",
                    debt_amount=Decimal("500.00"),
                    grace_period_elapsed=True,
                    extension_checked=True,
                    has_active_extension=False,
                    notification_sent=True,
                    notification_sent_at=datetime.now(UTC),
                    performed_by="Tecnico de red",
                    mikrotik_result=NetworkOperationResult.manual,
                ),
                self.db,
            )
        self.assertEqual(context.exception.status_code, 409)

    def test_elapsed_extension_is_marked_expired(self) -> None:
        self.add_debt()
        extension = create_extension(self.service.id, self.extension_data(), self.db)
        extension.promised_date = date.today() - timedelta(days=1)
        self.db.commit()

        history = list_extensions(self.service.id, self.db)
        self.assertEqual(history[0].status, ExtensionStatus.expired)


if __name__ == "__main__":
    unittest.main()
