import unittest
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.equipment_recovery import (
    complete_equipment_recovery,
    create_equipment_recovery,
)
from app.api.v1.endpoints.maintenance_inspections import (
    create_maintenance_inspection,
    get_equipment_inspection_status,
    list_maintenance_inspections,
)
from app.api.v1.endpoints.service_operations import create_cancellation
from app.api.v1.endpoints.services import (
    create_service,
    transition_service_status,
)
from app.db.base import Base
from app.models.customer import Customer
from app.models.maintenance_inspection import InspectionResult
from app.models.service import ServiceStatus
from app.schemas.equipment_recovery import (
    EquipmentRecoveryComplete,
    EquipmentRecoveryCreate,
)
from app.schemas.maintenance_inspection import (
    InspectionState,
    InspectionTest,
    MaintenanceInspectionCreate,
)
from app.schemas.service import ServiceCreate, ServiceTransitionCreate
from app.schemas.service_operations import CancellationCreate


class MaintenanceInspectionTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        customer = Customer(
            full_name="Cliente de mantenimiento",
            phones=["8997654321"],
        )
        self.db.add(customer)
        self.db.commit()
        self.customer = customer
        service = create_service(
            ServiceCreate(
                customer_id=customer.id,
                amr_code="AMR401",
                address="Calle Taller 401, Reynosa",
                plan_name="Hogar 20 Mbps",
                monthly_price=Decimal("500.00"),
                payment_day=5,
            ),
            self.db,
        )
        self.service = transition_service_status(
            service.id,
            ServiceTransitionCreate(
                target_status=ServiceStatus.active,
                reason="Instalacion terminada",
            ),
            self.db,
        )
        create_cancellation(
            self.service.id,
            CancellationCreate(
                requester_customer_id=customer.id,
                effective_date=date.today(),
                reason="Baja solicitada por el cliente",
                registered_by="Atencion a clientes",
            ),
            self.db,
        )
        create_equipment_recovery(
            self.service.id,
            EquipmentRecoveryCreate(
                scheduled_for=date.today(),
                assigned_technician="Tecnico instalador",
                expected_equipment=["Antena", "Modem", "PoE"],
            ),
            self.db,
        )
        complete_equipment_recovery(
            self.service.id,
            EquipmentRecoveryComplete(
                performed_by="Tecnico instalador",
                recovered_equipment=["Antena", "Modem"],
                missing_equipment=["PoE"],
                condition_notes="Equipos enviados a cuarentena",
            ),
            self.db,
        )

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def inspection_data(
        self,
        equipment_name: str = "Antena",
        result: InspectionResult = InspectionResult.ready_for_reuse,
        cleaning_performed: bool = True,
        tests_passed: bool = True,
    ) -> MaintenanceInspectionCreate:
        return MaintenanceInspectionCreate(
            equipment_name=equipment_name,
            technician="Tecnico de taller",
            serial_number="SN-401",
            mac_address="aa-bb-cc-dd-ee-ff",
            model="Equipo de prueba",
            cleaning_performed=cleaning_performed,
            cleaning_notes="Limpieza externa e interna",
            tests=[
                InspectionTest(
                    name="Conexion",
                    passed=tests_passed,
                    notes="Prueba controlada en taller",
                )
            ],
            repairs_performed=[],
            evidence_references=["evidencia/inspection-401.jpg"],
            result=result,
            decision_reason="Resultado confirmado por el tecnico",
        )

    def test_recovered_equipment_starts_in_quarantine(self) -> None:
        statuses = get_equipment_inspection_status(
            self.service.id,
            self.db,
        )

        self.assertEqual(len(statuses), 2)
        self.assertTrue(
            all(item.state == InspectionState.quarantine for item in statuses)
        )
        self.assertTrue(all(not item.reusable for item in statuses))

    def test_ready_for_reuse_requires_cleaning_and_passing_tests(self) -> None:
        with self.assertRaises(ValueError):
            self.inspection_data(cleaning_performed=False)
        with self.assertRaises(ValueError):
            self.inspection_data(tests_passed=False)

    def test_only_recovered_equipment_can_be_inspected(self) -> None:
        with self.assertRaises(HTTPException) as context:
            create_maintenance_inspection(
                self.service.id,
                self.inspection_data(equipment_name="PoE"),
                self.db,
            )

        self.assertEqual(context.exception.status_code, 409)

    def test_ready_equipment_is_reusable_and_terminal(self) -> None:
        inspection = create_maintenance_inspection(
            self.service.id,
            self.inspection_data(equipment_name="antena"),
            self.db,
        )
        statuses = get_equipment_inspection_status(
            self.service.id,
            self.db,
        )

        antenna = next(
            item for item in statuses if item.equipment_name == "Antena"
        )
        self.assertEqual(inspection.equipment_name, "Antena")
        self.assertEqual(inspection.mac_address, "AA:BB:CC:DD:EE:FF")
        self.assertEqual(antenna.state, InspectionState.ready_for_reuse)
        self.assertTrue(antenna.reusable)

        with self.assertRaises(HTTPException) as context:
            create_maintenance_inspection(
                self.service.id,
                self.inspection_data(),
                self.db,
            )
        self.assertEqual(context.exception.status_code, 409)

    def test_repair_result_allows_reinspection_and_preserves_history(self) -> None:
        create_maintenance_inspection(
            self.service.id,
            self.inspection_data(
                result=InspectionResult.needs_repair,
                tests_passed=False,
            ),
            self.db,
        )
        create_maintenance_inspection(
            self.service.id,
            self.inspection_data(),
            self.db,
        )

        history = list_maintenance_inspections(
            self.service.id,
            self.db,
        )
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].result, InspectionResult.needs_repair)
        self.assertEqual(history[1].result, InspectionResult.ready_for_reuse)

    def test_discarded_equipment_is_not_reusable_and_is_terminal(self) -> None:
        create_maintenance_inspection(
            self.service.id,
            self.inspection_data(
                result=InspectionResult.discarded,
                tests_passed=False,
            ),
            self.db,
        )
        status_item = get_equipment_inspection_status(
            self.service.id,
            self.db,
        )[0]

        self.assertEqual(status_item.state, InspectionState.discarded)
        self.assertFalse(status_item.reusable)

        with self.assertRaises(HTTPException) as context:
            create_maintenance_inspection(
                self.service.id,
                self.inspection_data(),
                self.db,
            )
        self.assertEqual(context.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
