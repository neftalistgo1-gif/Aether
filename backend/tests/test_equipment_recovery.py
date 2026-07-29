import unittest
from datetime import date, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.equipment_recovery import (
    complete_equipment_recovery,
    create_equipment_recovery,
    get_equipment_recovery,
)
from app.api.v1.endpoints.service_operations import create_cancellation
from app.api.v1.endpoints.services import (
    create_service,
    transition_service_status,
)
from app.db.base import Base
from app.models.customer import Customer
from app.models.service import ServiceStatus
from app.models.service_operations import EquipmentRecoveryStatus
from app.schemas.equipment_recovery import (
    EquipmentRecoveryComplete,
    EquipmentRecoveryCreate,
)
from app.schemas.service import ServiceCreate, ServiceTransitionCreate
from app.schemas.service_operations import CancellationCreate


class EquipmentRecoveryTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.customer = Customer(
            full_name="María García",
            phones=["8991234567"],
        )
        self.db.add(self.customer)
        self.db.commit()
        self.service = create_service(
            ServiceCreate(
                customer_id=self.customer.id,
                amr_code="AMR301",
                address="Calle Principal 123, Reynosa",
                plan_name="Hogar 20 Mbps",
                monthly_price=Decimal("500.00"),
                payment_day=5,
            ),
            self.db,
        )
        self.service = transition_service_status(
            self.service.id,
            ServiceTransitionCreate(
                target_status=ServiceStatus.active,
                reason="Instalación terminada",
            ),
            self.db,
        )

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def cancel_service(self, effective_date: date) -> None:
        self.service.status = ServiceStatus.pending
        self.service.activation_date = None
        self.db.commit()
        create_cancellation(
            self.service.id,
            CancellationCreate(
                requester_customer_id=self.customer.id,
                effective_date=effective_date,
                reason="Baja solicitada por el cliente",
                registered_by="Atención a clientes",
            ),
            self.db,
        )

    def schedule_recovery(
        self,
        scheduled_for: date = date.today(),
    ):
        return create_equipment_recovery(
            self.service.id,
            EquipmentRecoveryCreate(
                scheduled_for=scheduled_for,
                assigned_technician="Técnico instalador",
                expected_equipment=["Antena", "Módem", "PoE", "Tubo"],
                notes="Priorizar la antena",
            ),
            self.db,
        )

    def completion(
        self,
        recovered: list[str],
        missing: list[str],
    ) -> EquipmentRecoveryComplete:
        return EquipmentRecoveryComplete(
            performed_by="Técnico instalador",
            recovered_equipment=recovered,
            missing_equipment=missing,
            condition_notes="Equipos recibidos para inspección",
            evidence_references=["evidencia/recovery-001.jpg"],
            receipt_reference="REC-001",
        )

    def test_schedule_recovery_updates_cancellation_status(self) -> None:
        self.cancel_service(date.today())

        recovery = self.schedule_recovery()

        self.assertEqual(
            recovery.status,
            EquipmentRecoveryStatus.scheduled,
        )
        self.assertEqual(
            get_equipment_recovery(self.service.id, self.db).id,
            recovery.id,
        )
        self.assertEqual(
            recovery.cancellation.equipment_recovery_status,
            EquipmentRecoveryStatus.scheduled,
        )

        with self.assertRaises(HTTPException) as duplicate:
            self.schedule_recovery()
        self.assertEqual(duplicate.exception.status_code, 409)

    def test_complete_full_recovery(self) -> None:
        self.cancel_service(date.today())
        self.schedule_recovery()

        recovery = complete_equipment_recovery(
            self.service.id,
            self.completion(
                ["Antena", "Módem", "PoE", "Tubo"],
                [],
            ),
            self.db,
        )

        self.assertEqual(recovery.status, EquipmentRecoveryStatus.complete)
        self.assertIsNotNone(recovery.performed_at)
        self.assertEqual(
            recovery.cancellation.equipment_recovery_status,
            EquipmentRecoveryStatus.complete,
        )

    def test_complete_partial_recovery(self) -> None:
        self.cancel_service(date.today())
        self.schedule_recovery()

        recovery = complete_equipment_recovery(
            self.service.id,
            self.completion(
                ["Antena", "PoE", "Tubo"],
                ["Módem"],
            ),
            self.db,
        )

        self.assertEqual(recovery.status, EquipmentRecoveryStatus.partial)

    def test_complete_unrecoverable_visit(self) -> None:
        self.cancel_service(date.today())
        self.schedule_recovery()

        recovery = complete_equipment_recovery(
            self.service.id,
            self.completion(
                [],
                ["Antena", "Módem", "PoE", "Tubo"],
            ),
            self.db,
        )

        self.assertEqual(
            recovery.status,
            EquipmentRecoveryStatus.unrecoverable,
        )

    def test_completion_rejects_unclassified_expected_equipment(self) -> None:
        self.cancel_service(date.today())
        self.schedule_recovery()

        with self.assertRaises(HTTPException) as context:
            complete_equipment_recovery(
                self.service.id,
                self.completion(["Antena"], ["Módem"]),
                self.db,
            )

        self.assertEqual(context.exception.status_code, 409)

    def test_recovery_cannot_precede_effective_cancellation(self) -> None:
        tomorrow = date.today() + timedelta(days=1)
        self.cancel_service(tomorrow)

        with self.assertRaises(HTTPException) as context:
            self.schedule_recovery(date.today())

        self.assertEqual(context.exception.status_code, 409)

    def test_recovery_cannot_complete_before_cancellation(self) -> None:
        tomorrow = date.today() + timedelta(days=1)
        self.cancel_service(tomorrow)
        self.schedule_recovery(tomorrow)

        with self.assertRaises(HTTPException) as context:
            complete_equipment_recovery(
                self.service.id,
                self.completion(
                    ["Antena", "Módem", "PoE", "Tubo"],
                    [],
                ),
                self.db,
            )

        self.assertEqual(context.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
