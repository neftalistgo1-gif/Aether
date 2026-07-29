import unittest
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.installations import (
    cancel_installation,
    complete_installation,
    create_installation,
    reschedule_installation,
)
from app.api.v1.endpoints.services import create_service
from app.db.base import Base
from app.models.charge import Charge, ChargeStatus
from app.models.customer import Customer
from app.models.installation import (
    CoverageResult,
    InstallationStatus,
    InstallationType,
)
from app.models.mikrotik import MikrotikRouter, NetworkControlCommand
from app.models.network_assignment import NetworkAssignment
from app.models.service import ServiceStatus
from app.schemas.installation import (
    InstallationCancel,
    InstallationComplete,
    InstallationCreate,
    InstallationReschedule,
)
from app.schemas.service import ServiceCreate


class InstallationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        customer = Customer(
            full_name="Cliente de instalacion",
            phones=["8997778899"],
        )
        self.db.add(customer)
        self.db.commit()
        self.service = create_service(
            ServiceCreate(
                customer_id=customer.id,
                amr_code="AMR991",
                address="Calle Instalacion 10, Reynosa",
                plan_name="Hogar 20 Mbps",
                monthly_price=Decimal("500.00"),
                payment_day=10,
            ),
            self.db,
        )

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def installation_data(
        self,
        installation_type: InstallationType = InstallationType.installation,
        new_address: str | None = None,
    ) -> InstallationCreate:
        return InstallationCreate(
            installation_type=installation_type,
            coverage_result=CoverageResult.viable,
            coverage_checked_by="Tecnico instalador",
            coverage_checked_at=datetime.now(UTC),
            scheduled_for=date.today() + timedelta(days=1),
            cost=Decimal("1000.00"),
            new_address=new_address,
            registered_by="Atencion a clientes",
        )

    def completion_data(self) -> InstallationComplete:
        return InstallationComplete(
            completed_at=datetime.now(UTC),
            technicians=["Tecnico uno", "Tecnico dos"],
            antenna_photos=["antena-1.jpg", "antena-2.jpg"],
            modem_photos=["modem-1.jpg"],
            navigation_confirmed=True,
            navigation_confirmed_by="Cliente",
            performed_by="Tecnico uno",
        )

    def mark_charge_paid(self, charge_id) -> None:
        charge = self.db.get(Charge, charge_id)
        charge.status = ChargeStatus.paid
        charge.outstanding_balance = Decimal("0.00")
        self.db.commit()

    def test_viable_installation_creates_charge_and_requires_payment(self) -> None:
        installation = create_installation(
            self.service.id,
            self.installation_data(),
            self.db,
        )
        self.assertEqual(installation.status, InstallationStatus.scheduled)
        self.assertIsNotNone(installation.charge_id)

        with self.assertRaises(HTTPException) as unpaid:
            complete_installation(
                self.service.id,
                installation.id,
                self.completion_data(),
                self.db,
            )
        self.assertEqual(unpaid.exception.status_code, 409)

        self.mark_charge_paid(installation.charge_id)
        completed = complete_installation(
            self.service.id,
            installation.id,
            self.completion_data(),
            self.db,
        )
        self.assertEqual(completed.status, InstallationStatus.completed)
        self.db.refresh(self.service)
        self.assertEqual(self.service.status, ServiceStatus.active)
        self.assertIsNotNone(self.service.activation_date)

    def test_navigation_and_required_photos_are_enforced(self) -> None:
        with self.assertRaises(ValidationError):
            InstallationComplete(
                completed_at=datetime.now(UTC),
                technicians=["Tecnico"],
                antenna_photos=["solo-una.jpg"],
                modem_photos=["modem.jpg"],
                navigation_confirmed=True,
                navigation_confirmed_by="Cliente",
                performed_by="Tecnico",
            )

        data = self.completion_data()
        data.navigation_confirmed = False
        installation = create_installation(
            self.service.id,
            self.installation_data(),
            self.db,
        )
        self.mark_charge_paid(installation.charge_id)
        with self.assertRaises(HTTPException):
            complete_installation(
                self.service.id,
                installation.id,
                data,
                self.db,
            )

    def test_reschedule_preserves_history_and_moves_charge_due_date(self) -> None:
        installation = create_installation(
            self.service.id,
            self.installation_data(),
            self.db,
        )
        new_date = date.today() + timedelta(days=3)
        changed = reschedule_installation(
            self.service.id,
            installation.id,
            InstallationReschedule(
                new_date=new_date,
                changed_by="Atencion a clientes",
                reason="Lluvia intensa",
            ),
            self.db,
        )
        self.assertEqual(changed.scheduled_for, new_date)
        self.assertEqual(len(changed.schedule_changes), 1)
        self.assertEqual(
            self.db.get(Charge, changed.charge_id).due_date,
            new_date,
        )

    def test_out_of_coverage_is_not_scheduled_or_charged(self) -> None:
        data = InstallationCreate(
            installation_type=InstallationType.installation,
            coverage_result=CoverageResult.out_of_coverage,
            coverage_checked_by="Tecnico instalador",
            coverage_checked_at=datetime.now(UTC),
            cost=Decimal("0.00"),
            registered_by="Atencion a clientes",
        )
        installation = create_installation(
            self.service.id,
            data,
            self.db,
        )
        self.assertEqual(installation.status, InstallationStatus.cancelled)
        self.assertIsNone(installation.charge_id)
        self.db.refresh(self.service)
        self.assertEqual(self.service.status, ServiceStatus.pending)

    def test_address_change_requires_coverage_and_updates_on_completion(self) -> None:
        self.service.status = ServiceStatus.active
        self.db.commit()
        with self.assertRaises(ValidationError):
            self.installation_data(
                InstallationType.address_change,
                new_address=None,
            )
        installation = create_installation(
            self.service.id,
            self.installation_data(
                InstallationType.address_change,
                new_address="Calle Nueva 200, Reynosa",
            ),
            self.db,
        )
        self.mark_charge_paid(installation.charge_id)
        complete_installation(
            self.service.id,
            installation.id,
            self.completion_data(),
            self.db,
        )
        self.db.refresh(self.service)
        self.assertEqual(self.service.address, "Calle Nueva 200, Reynosa")

    def test_cancellation_cancels_unpaid_charge(self) -> None:
        installation = create_installation(
            self.service.id,
            self.installation_data(),
            self.db,
        )
        cancelled = cancel_installation(
            self.service.id,
            installation.id,
            InstallationCancel(
                cancelled_by="Atencion a clientes",
                reason="Cliente solicito reprogramar mas adelante",
            ),
            self.db,
        )
        self.assertEqual(cancelled.status, InstallationStatus.cancelled)
        charge = self.db.get(Charge, cancelled.charge_id)
        self.assertEqual(charge.status, ChargeStatus.cancelled)
        self.assertEqual(charge.outstanding_balance, Decimal("0.00"))


if __name__ == "__main__":
    unittest.main()
