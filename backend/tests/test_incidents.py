import unittest
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.incidents import (
    add_incident_impact,
    compensate_incident_impact,
    create_incident,
    list_incidents,
    resolve_incident,
    restore_incident_impact,
)
from app.api.v1.endpoints.payment_allocations import customer_credit_balance
from app.api.v1.endpoints.services import create_service
from app.db.base import Base
from app.models.customer import Customer
from app.models.extension import Extension
from app.models.incident import IncidentStatus
from app.models.mikrotik import MikrotikRouter, NetworkControlCommand
from app.models.network_assignment import NetworkAssignment
from app.models.payment_agreement import PaymentAgreement
from app.models.service import ServiceStatus
from app.schemas.incident import (
    IncidentCompensationCreate,
    IncidentCreate,
    IncidentImpactAdd,
    IncidentImpactRestore,
    IncidentResolve,
)
from app.schemas.service import ServiceCreate


class IncidentTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.customer = Customer(
            full_name="Cliente con incidencia",
            phones=["8995556677"],
        )
        self.db.add(self.customer)
        self.db.commit()
        self.service = create_service(
            ServiceCreate(
                customer_id=self.customer.id,
                amr_code="AMR951",
                address="Calle Incidencia 10, Reynosa",
                plan_name="Hogar 20 Mbps",
                monthly_price=Decimal("500.00"),
                payment_day=12,
            ),
            self.db,
        )
        self.service.status = ServiceStatus.active
        self.db.commit()
        self.started_at = datetime.now(UTC) - timedelta(hours=2)

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def incident_data(self) -> IncidentCreate:
        return IncidentCreate(
            title="Falla eléctrica en torre",
            tower_name="Torre Norte",
            access_point_name="AP-Norte-01",
            started_at=self.started_at,
            reported_by="Atencion a clientes",
            service_ids=[self.service.id],
            notes="Sin energía comercial",
        )

    def test_incident_requires_a_defined_scope(self) -> None:
        with self.assertRaises(ValidationError):
            IncidentCreate(
                title="Falla sin alcance",
                started_at=self.started_at,
                reported_by="Operador",
            )

    def test_create_incident_preserves_commercial_service_status(self) -> None:
        incident = create_incident(self.incident_data(), self.db)

        self.assertEqual(incident.status, IncidentStatus.open)
        self.assertEqual(len(incident.impacts), 1)
        self.assertEqual(
            incident.impacts[0].customer_id,
            self.customer.id,
        )
        self.db.refresh(self.service)
        self.assertEqual(self.service.status, ServiceStatus.active)

    def test_resolve_records_exact_period_for_all_open_impacts(self) -> None:
        incident = create_incident(self.incident_data(), self.db)
        resolved_at = self.started_at + timedelta(minutes=95)
        resolved = resolve_incident(
            incident.id,
            IncidentResolve(
                resolved_at=resolved_at,
                cause="Falla de suministro eléctrico",
                responsible="Tecnico de red",
            ),
            self.db,
        )

        self.assertEqual(resolved.status, IncidentStatus.resolved)
        self.assertEqual(resolved.duration_minutes, 95)
        self.assertEqual(resolved.impacts[0].duration_minutes, 95)

    def test_resolution_cannot_precede_a_later_service_impact(self) -> None:
        incident = create_incident(self.incident_data(), self.db)
        second_customer = Customer(
            full_name="Segundo cliente afectado",
            phones=["8995557788"],
        )
        self.db.add(second_customer)
        self.db.commit()
        second_service = create_service(
            ServiceCreate(
                customer_id=second_customer.id,
                amr_code="AMR952",
                address="Calle Incidencia 12, Reynosa",
                plan_name="Hogar 20 Mbps",
                monthly_price=Decimal("500.00"),
                payment_day=12,
            ),
            self.db,
        )
        add_incident_impact(
            incident.id,
            IncidentImpactAdd(
                service_id=second_service.id,
                affected_from=self.started_at + timedelta(minutes=90),
            ),
            self.db,
        )

        with self.assertRaises(HTTPException) as context:
            resolve_incident(
                incident.id,
                IncidentResolve(
                    resolved_at=self.started_at + timedelta(minutes=60),
                    cause="Restablecimiento parcial",
                    responsible="Tecnico de red",
                ),
                self.db,
            )

        self.assertEqual(context.exception.status_code, 409)
        self.db.refresh(incident)
        self.assertEqual(incident.status, IncidentStatus.open)

    def test_resolution_cannot_precede_recorded_restoration(self) -> None:
        incident = create_incident(self.incident_data(), self.db)
        restore_incident_impact(
            incident.id,
            incident.impacts[0].id,
            IncidentImpactRestore(
                restored_at=self.started_at + timedelta(minutes=90)
            ),
            self.db,
        )

        with self.assertRaises(HTTPException) as context:
            resolve_incident(
                incident.id,
                IncidentResolve(
                    resolved_at=self.started_at + timedelta(minutes=60),
                    cause="Hora de cierre inconsistente",
                    responsible="Tecnico de red",
                ),
                self.db,
            )

        self.assertEqual(context.exception.status_code, 409)
        self.db.refresh(incident)
        self.assertEqual(incident.status, IncidentStatus.open)

    def test_duplicate_affected_service_is_rejected(self) -> None:
        incident = create_incident(self.incident_data(), self.db)
        with self.assertRaises(HTTPException) as context:
            add_incident_impact(
                incident.id,
                IncidentImpactAdd(
                    service_id=self.service.id,
                    affected_from=self.started_at,
                ),
                self.db,
            )
        self.assertEqual(context.exception.status_code, 409)

    def test_service_can_be_restored_before_incident_resolution(self) -> None:
        incident = create_incident(self.incident_data(), self.db)
        impact = incident.impacts[0]
        restored_at = self.started_at + timedelta(minutes=30)
        restored = restore_incident_impact(
            incident.id,
            impact.id,
            IncidentImpactRestore(restored_at=restored_at),
            self.db,
        )
        self.assertEqual(restored.duration_minutes, 30)

        resolved = resolve_incident(
            incident.id,
            IncidentResolve(
                resolved_at=self.started_at + timedelta(minutes=90),
                cause="Falla eléctrica general",
                responsible="Tecnico de red",
            ),
            self.db,
        )
        self.assertEqual(resolved.duration_minutes, 90)
        self.assertEqual(resolved.impacts[0].duration_minutes, 30)

    def test_compensation_requires_resolution_and_is_not_duplicated(self) -> None:
        incident = create_incident(self.incident_data(), self.db)
        impact = incident.impacts[0]
        compensation = IncidentCompensationCreate(
            amount=Decimal("75.00"),
            authorized_by="Gerencia",
            reason="Interrupcion prolongada",
        )
        with self.assertRaises(HTTPException) as open_incident:
            compensate_incident_impact(
                incident.id,
                impact.id,
                compensation,
                self.db,
            )
        self.assertEqual(open_incident.exception.status_code, 409)

        resolve_incident(
            incident.id,
            IncidentResolve(
                resolved_at=self.started_at + timedelta(hours=1),
                cause="Falla eléctrica",
                responsible="Tecnico de red",
            ),
            self.db,
        )
        result = compensate_incident_impact(
            incident.id,
            impact.id,
            compensation,
            self.db,
        )
        self.assertEqual(result.impact.compensation_amount, Decimal("75.00"))
        self.assertEqual(
            customer_credit_balance(self.customer.id, self.db),
            Decimal("75.00"),
        )
        with self.assertRaises(HTTPException) as duplicate:
            compensate_incident_impact(
                incident.id,
                impact.id,
                compensation,
                self.db,
            )
        self.assertEqual(duplicate.exception.status_code, 409)

    def test_list_filters_by_status_service_and_tower(self) -> None:
        incident = create_incident(self.incident_data(), self.db)
        self.assertEqual(
            [item.id for item in list_incidents(
                IncidentStatus.open,
                self.service.id,
                "Torre Norte",
                self.db,
            )],
            [incident.id],
        )
        self.assertEqual(
            list_incidents(
                IncidentStatus.resolved,
                self.service.id,
                "Torre Norte",
                self.db,
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
