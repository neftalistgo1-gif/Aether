import unittest
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.network_assignments import (
    create_network_assignment,
    get_current_network_assignment,
    list_network_assignments,
)
from app.api.v1.endpoints.service_operations import create_cancellation
from app.api.v1.endpoints.services import (
    create_service,
    transition_service_status,
)
from app.db.base import Base
from app.models.customer import Customer
from app.models.service import Service, ServiceStatus
from app.schemas.network_assignment import NetworkAssignmentCreate
from app.schemas.service import ServiceCreate, ServiceTransitionCreate
from app.schemas.service_operations import CancellationCreate


class NetworkAssignmentTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.customer = Customer(
            full_name="Cliente de red",
            phones=["8992223344"],
        )
        self.db.add(self.customer)
        self.db.commit()
        self.service = self.create_active_service("AMR601")

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

    def network_data(
        self,
        ip: str = "10.20.30.40",
        access_point: str = "AP-Norte-01",
        reason: str = "Configuracion inicial",
    ) -> NetworkAssignmentCreate:
        return NetworkAssignmentCreate(
            router_name="CCR2116-Principal",
            ip_address=ip,
            tower_name="Torre Norte",
            access_point_name=access_point,
            antenna_name=f"{self.service.amr_code} Cliente de red",
            frequency_mhz=Decimal("5805.000"),
            signal_dbm=Decimal("-58.50"),
            technician="Tecnico de red",
            change_reason=reason,
        )

    def test_create_and_get_current_network_assignment(self) -> None:
        assignment = create_network_assignment(
            self.service.id,
            self.network_data(),
            self.db,
        )

        current = get_current_network_assignment(
            self.service.id,
            self.db,
        )
        self.assertEqual(current.id, assignment.id)
        self.assertEqual(current.ip_address, "10.20.30.40")
        self.assertIsNone(current.ended_at)

    def test_change_closes_previous_assignment_and_preserves_history(self) -> None:
        previous = create_network_assignment(
            self.service.id,
            self.network_data(),
            self.db,
        )
        current = create_network_assignment(
            self.service.id,
            self.network_data(
                ip="10.20.30.41",
                access_point="AP-Norte-02",
                reason="Cambio por interferencia",
            ),
            self.db,
        )

        history = list_network_assignments(self.service.id, self.db)
        self.assertEqual(len(history), 2)
        self.assertIsNotNone(previous.ended_at)
        self.assertIsNone(current.ended_at)
        self.assertEqual(history[-1].id, current.id)

    def test_router_and_ip_cannot_be_current_on_two_services(self) -> None:
        create_network_assignment(
            self.service.id,
            self.network_data(),
            self.db,
        )
        second_service = self.create_active_service("AMR602")

        with self.assertRaises(HTTPException) as context:
            create_network_assignment(
                second_service.id,
                self.network_data(),
                self.db,
            )

        self.assertEqual(context.exception.status_code, 409)

    def test_unchanged_or_suspended_configuration_is_rejected(self) -> None:
        create_network_assignment(
            self.service.id,
            self.network_data(),
            self.db,
        )
        with self.assertRaises(HTTPException) as unchanged:
            create_network_assignment(
                self.service.id,
                self.network_data(reason="Intento duplicado"),
                self.db,
            )
        self.assertEqual(unchanged.exception.status_code, 409)

        self.service.status = ServiceStatus.suspended
        self.db.commit()
        with self.assertRaises(HTTPException) as suspended:
            create_network_assignment(
                self.service.id,
                self.network_data(ip="10.20.30.42"),
                self.db,
            )
        self.assertEqual(suspended.exception.status_code, 409)

    def test_cancellation_closes_current_network_assignment(self) -> None:
        assignment = create_network_assignment(
            self.service.id,
            self.network_data(),
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

        self.assertIsNotNone(assignment.ended_at)
        with self.assertRaises(HTTPException) as current:
            get_current_network_assignment(self.service.id, self.db)
        self.assertEqual(current.exception.status_code, 404)
        with self.assertRaises(HTTPException) as cancelled:
            create_network_assignment(
                self.service.id,
                self.network_data(ip="10.20.30.43"),
                self.db,
            )
        self.assertEqual(cancelled.exception.status_code, 409)

    def test_ip_address_must_be_valid_and_is_normalized(self) -> None:
        with self.assertRaises(ValueError):
            self.network_data(ip="999.20.30.40")

        ipv6 = self.network_data(ip="2001:0db8:0000:0000:0000:0000:0000:0001")
        self.assertEqual(ipv6.ip_address, "2001:db8::1")


if __name__ == "__main__":
    unittest.main()
