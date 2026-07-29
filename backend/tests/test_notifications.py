import unittest
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.notifications import (
    create_notification,
    get_notification,
    list_notifications,
)
from app.api.v1.endpoints.services import create_service
from app.db.base import Base
from app.models.audit import AuditEvent
from app.models.customer import Customer
from app.models.notification import (
    NotificationChannel,
    NotificationPurpose,
    NotificationStatus,
)
from app.schemas.notification import NotificationCreate, NotificationRead
from app.schemas.service import ServiceCreate


class NotificationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.customer = Customer(
            full_name="Cliente notificado",
            phones=["8995556677"],
        )
        self.other_customer = Customer(
            full_name="Cliente diferente",
            phones=["8991112233"],
        )
        self.db.add_all([self.customer, self.other_customer])
        self.db.commit()
        self.service = create_service(
            ServiceCreate(
                customer_id=self.customer.id,
                amr_code="AMR926",
                address="Domicilio de notificaciones",
                plan_name="Hogar 25 Mbps",
                monthly_price=Decimal("550.00"),
                payment_day=5,
            ),
            self.db,
        )

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def notification_data(self) -> NotificationCreate:
        return NotificationCreate(
            customer_id=self.customer.id,
            service_id=self.service.id,
            channel=NotificationChannel.whatsapp,
            purpose=NotificationPurpose.suspension_warning,
            status=NotificationStatus.delivered,
            recipient=self.customer.phones[0],
            message_summary="Aviso previo de suspensión por adeudo",
            evidence_reference="private/notifications/amr926-warning",
            occurred_at=datetime.now(UTC),
            recorded_by="Atención a clientes",
        )

    def test_record_is_filterable_audited_and_hides_evidence_path(self) -> None:
        notification = create_notification(
            self.notification_data(),
            self.db,
        )
        found = list_notifications(
            self.db,
            self.customer.id,
            self.service.id,
            NotificationPurpose.suspension_warning,
            NotificationStatus.delivered,
        )
        self.assertEqual(found[0].id, notification.id)
        self.assertEqual(
            get_notification(notification.id, self.db).id,
            notification.id,
        )
        public = NotificationRead.model_validate(notification).model_dump()
        self.assertTrue(public["has_evidence"])
        self.assertNotIn("evidence_reference", public)
        event = self.db.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "notification.recorded"
            )
        )
        self.assertIsNotNone(event)

    def test_digital_delivery_requires_external_evidence(self) -> None:
        values = self.notification_data().model_dump()
        values["evidence_reference"] = None
        with self.assertRaises(ValidationError):
            NotificationCreate(**values)

    def test_service_must_belong_to_customer_history(self) -> None:
        values = self.notification_data().model_dump()
        values["customer_id"] = self.other_customer.id
        with self.assertRaises(HTTPException) as rejected:
            create_notification(NotificationCreate(**values), self.db)
        self.assertEqual(rejected.exception.status_code, 409)

    def test_failed_attempt_requires_reason(self) -> None:
        values = self.notification_data().model_dump()
        values["status"] = NotificationStatus.failed
        values["evidence_reference"] = None
        with self.assertRaises(ValidationError):
            NotificationCreate(**values)


if __name__ == "__main__":
    unittest.main()
