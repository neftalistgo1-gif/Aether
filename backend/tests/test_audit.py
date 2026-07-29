import unittest
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.main import app
from app.api.v1.endpoints.audit import list_audit_events
from app.db.base import Base
from app.models.audit import AuditEvent
from app.services.audit import record_audit_event


class AuditEventTestCase(unittest.TestCase):
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

    def test_event_is_filterable_and_serializes_snapshots(self) -> None:
        entity_id = uuid4()
        record_audit_event(
            self.db,
            actor="Administrador",
            action="balance.adjusted",
            entity_type="CreditMovement",
            entity_id=entity_id,
            reason="Correccion autorizada",
            before_data={"balance": Decimal("25.00")},
            after_data={
                "balance": Decimal("50.00"),
                "password": "must-not-be-stored",
            },
        )
        self.db.commit()

        events = list_audit_events(
            actor="Administrador",
            action="balance.adjusted",
            entity_type="CreditMovement",
            entity_id=str(entity_id),
            limit=100,
            db=self.db,
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].before_data["balance"], "25.00")
        self.assertEqual(events[0].after_data["password"], "[REDACTED]")

    def test_event_rolls_back_with_failed_business_transaction(self) -> None:
        record_audit_event(
            self.db,
            actor="Operador",
            action="payment.failed-example",
            entity_type="Payment",
            entity_id=uuid4(),
            reason="Operacion revertida",
        )
        self.db.rollback()
        self.assertIsNone(self.db.scalar(select(AuditEvent)))

    def test_persisted_event_cannot_be_changed_or_deleted(self) -> None:
        event = record_audit_event(
            self.db,
            actor="Administrador",
            action="payment.verified",
            entity_type="Payment",
            entity_id=uuid4(),
            reason="Verificacion original",
        )
        self.db.commit()
        event.reason = "Intento de cambio"
        with self.assertRaises(ValueError):
            self.db.commit()
        self.db.rollback()

        stored = self.db.get(AuditEvent, event.id)
        self.db.delete(stored)
        with self.assertRaises(ValueError):
            self.db.commit()
        self.db.rollback()

    def test_api_exposes_no_write_or_delete_route(self) -> None:
        audit_paths = {
            path: operations
            for path, operations in app.openapi()["paths"].items()
            if path.startswith("/api/v1/audit-events")
        }
        self.assertTrue(audit_paths)
        methods = {
            method.upper()
            for operations in audit_paths.values()
            for method in operations
        }
        self.assertEqual(methods, {"GET"})


if __name__ == "__main__":
    unittest.main()
