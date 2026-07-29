import unittest
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.assets import (
    assign_asset,
    create_asset,
    list_asset_assignments,
    list_assets,
    return_asset,
)
from app.api.v1.endpoints.equipment_recovery import (
    complete_equipment_recovery,
    create_equipment_recovery,
)
from app.api.v1.endpoints.maintenance_inspections import (
    create_maintenance_inspection,
)
from app.api.v1.endpoints.service_operations import create_cancellation
from app.api.v1.endpoints.services import (
    create_service,
    transition_service_status,
)
from app.db.base import Base
from app.models.asset import (
    Asset,
    AssetOwner,
    AssetReturnOutcome,
    AssetStatus,
    AssetType,
)
from app.models.customer import Customer
from app.models.maintenance_inspection import InspectionResult
from app.models.service import Service, ServiceStatus
from app.schemas.asset import (
    AssetAssignmentCreate,
    AssetAssignmentReturn,
    AssetCreate,
)
from app.schemas.equipment_recovery import (
    EquipmentRecoveryComplete,
    EquipmentRecoveryCreate,
)
from app.schemas.maintenance_inspection import (
    InspectionTest,
    MaintenanceInspectionCreate,
)
from app.schemas.service import ServiceCreate, ServiceTransitionCreate
from app.schemas.service_operations import CancellationCreate


class AssetInventoryTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.customer = Customer(
            full_name="Cliente de inventario",
            phones=["8991112233"],
        )
        self.db.add(self.customer)
        self.db.commit()
        self.service = self.create_active_service("AMR501")

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def create_active_service(self, amr_code: str) -> Service:
        service = create_service(
            ServiceCreate(
                customer_id=self.customer.id,
                amr_code=amr_code,
                address=f"Domicilio {amr_code}, Reynosa",
                plan_name="Hogar 20 Mbps",
                monthly_price=Decimal("500.00"),
                payment_day=5,
            ),
            self.db,
        )
        return transition_service_status(
            service.id,
            ServiceTransitionCreate(
                target_status=ServiceStatus.active,
                reason="Instalacion terminada",
            ),
            self.db,
        )

    def asset_data(
        self,
        owner: AssetOwner = AssetOwner.amr,
        serial_number: str = "SERIAL-501",
        mac_address: str = "aa-bb-cc-dd-ee-01",
    ) -> AssetCreate:
        return AssetCreate(
            asset_type=AssetType.antenna,
            description="Antena sectorial",
            brand="Ubiquiti",
            model="LiteBeam",
            serial_number=serial_number,
            mac_address=mac_address,
            owner=owner,
            acquired_on=date.today(),
        )

    def assignment_data(self, asset_id) -> AssetAssignmentCreate:
        return AssetAssignmentCreate(
            asset_id=asset_id,
            assigned_by="Tecnico instalador",
            condition_on_delivery="Probado y funcionando",
        )

    def test_create_asset_normalizes_identity_and_lists_inventory(self) -> None:
        asset = create_asset(self.asset_data(), self.db)

        self.assertTrue(asset.internal_code.startswith("AST-"))
        self.assertEqual(asset.mac_address, "AA:BB:CC:DD:EE:01")
        self.assertEqual(asset.status, AssetStatus.available)
        self.assertEqual(
            [item.id for item in list_assets(self.db, q="SERIAL-501")],
            [asset.id],
        )

        with self.assertRaises(HTTPException) as duplicate:
            create_asset(self.asset_data(), self.db)
        self.assertEqual(duplicate.exception.status_code, 409)

    def test_customer_owned_asset_cannot_be_assigned(self) -> None:
        asset = create_asset(
            self.asset_data(owner=AssetOwner.customer),
            self.db,
        )

        self.assertEqual(asset.status, AssetStatus.sold_to_customer)
        with self.assertRaises(HTTPException) as context:
            assign_asset(
                self.service.id,
                self.assignment_data(asset.id),
                self.db,
            )
        self.assertEqual(context.exception.status_code, 409)

    def test_assignment_requires_active_service_and_available_asset(self) -> None:
        pending_service = create_service(
            ServiceCreate(
                customer_id=self.customer.id,
                amr_code="AMR502",
                address="Domicilio pendiente, Reynosa",
                plan_name="Hogar 20 Mbps",
                monthly_price=Decimal("500.00"),
                payment_day=5,
            ),
            self.db,
        )
        asset = create_asset(self.asset_data(), self.db)

        with self.assertRaises(HTTPException) as inactive:
            assign_asset(
                pending_service.id,
                self.assignment_data(asset.id),
                self.db,
            )
        self.assertEqual(inactive.exception.status_code, 409)

        assignment = assign_asset(
            self.service.id,
            self.assignment_data(asset.id),
            self.db,
        )
        self.assertEqual(asset.status, AssetStatus.assigned)

        with self.assertRaises(HTTPException) as duplicate:
            assign_asset(
                self.service.id,
                self.assignment_data(asset.id),
                self.db,
            )
        self.assertEqual(duplicate.exception.status_code, 409)
        self.assertEqual(
            list_asset_assignments(asset.id, self.db)[0].id,
            assignment.id,
        )

    def test_manual_return_moves_asset_to_quarantine(self) -> None:
        asset = create_asset(self.asset_data(), self.db)
        assignment = assign_asset(
            self.service.id,
            self.assignment_data(asset.id),
            self.db,
        )

        closed = return_asset(
            self.service.id,
            assignment.id,
            AssetAssignmentReturn(
                returned_by="Tecnico instalador",
                condition_on_return="Pendiente de revision en taller",
                outcome=AssetReturnOutcome.recovered,
            ),
            self.db,
        )

        self.assertIsNotNone(closed.returned_at)
        self.assertEqual(asset.status, AssetStatus.quarantine)

    def test_recovery_inspection_and_reassignment_reuse_same_asset(self) -> None:
        asset = create_asset(self.asset_data(), self.db)
        first_assignment = assign_asset(
            self.service.id,
            self.assignment_data(asset.id),
            self.db,
        )
        create_cancellation(
            self.service.id,
            CancellationCreate(
                requester_customer_id=self.customer.id,
                effective_date=date.today(),
                reason="Baja solicitada por el cliente",
                pending_balance=Decimal("0.00"),
                credit_balance=Decimal("0.00"),
                registered_by="Atencion a clientes",
            ),
            self.db,
        )
        create_equipment_recovery(
            self.service.id,
            EquipmentRecoveryCreate(
                scheduled_for=date.today(),
                assigned_technician="Tecnico instalador",
                expected_equipment=[asset.internal_code],
            ),
            self.db,
        )
        complete_equipment_recovery(
            self.service.id,
            EquipmentRecoveryComplete(
                performed_by="Tecnico instalador",
                recovered_equipment=[asset.internal_code],
                missing_equipment=[],
                condition_notes="Equipo recuperado para taller",
            ),
            self.db,
        )

        self.assertEqual(asset.status, AssetStatus.quarantine)
        self.assertIsNotNone(first_assignment.returned_at)
        self.assertEqual(
            self.db.scalar(select(func.count()).select_from(Asset)),
            1,
        )

        create_maintenance_inspection(
            self.service.id,
            MaintenanceInspectionCreate(
                equipment_name=asset.internal_code,
                technician="Tecnico de taller",
                serial_number=asset.serial_number,
                mac_address=asset.mac_address,
                model=asset.model,
                cleaning_performed=True,
                cleaning_notes="Limpieza completa",
                tests=[
                    InspectionTest(
                        name="Conexion",
                        passed=True,
                        notes="Conexion estable",
                    )
                ],
                result=InspectionResult.ready_for_reuse,
                decision_reason="Todas las pruebas aprobadas",
            ),
            self.db,
        )
        self.assertEqual(asset.status, AssetStatus.ready_for_reuse)

        second_service = self.create_active_service("AMR503")
        second_assignment = assign_asset(
            second_service.id,
            self.assignment_data(asset.id),
            self.db,
        )

        self.assertEqual(asset.status, AssetStatus.assigned)
        self.assertEqual(second_assignment.asset_id, asset.id)
        self.assertEqual(len(list_asset_assignments(asset.id, self.db)), 2)


if __name__ == "__main__":
    unittest.main()
