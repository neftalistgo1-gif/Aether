import unittest
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.payments import (
    cancel_payment,
    create_payment,
    list_payment_events,
    list_payments,
    reject_payment,
    verify_payment,
)
from app.api.v1.endpoints.services import create_service
from app.db.base import Base
from app.models.customer import Customer
from app.models.audit import AuditEvent
from app.models.payment import PaymentMethod, PaymentStatus
from app.schemas.payment import (
    PaymentCreate,
    PaymentDecision,
    PaymentVerify,
)
from app.schemas.service import ServiceCreate


class PaymentTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.customer = Customer(
            full_name="Cliente de pagos",
            phones=["8994445566"],
        )
        self.db.add(self.customer)
        self.db.commit()
        self.service = create_service(
            ServiceCreate(
                customer_id=self.customer.id,
                amr_code="AMR801",
                address="Domicilio de pagos, Reynosa",
                plan_name="Hogar 20 Mbps",
                monthly_price=Decimal("500.00"),
                payment_day=5,
            ),
            self.db,
        )

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def payment_data(
        self,
        customer_id=None,
        service_id=None,
        reference: str = "REF-PAGO-801",
    ) -> PaymentCreate:
        return PaymentCreate(
            customer_id=customer_id or self.customer.id,
            service_id=(
                self.service.id
                if service_id is None
                else service_id
            ),
            declared_amount=Decimal("500.00"),
            declared_at=datetime.now(UTC),
            method=PaymentMethod.bank_transfer,
            reference=reference,
            proof_reference="comprobantes/pago-801.jpg",
            origin_account_holder="Cliente de pagos",
            received_by="Atencion a clientes",
        )

    def test_received_payment_is_pending_and_audited(self) -> None:
        payment = create_payment(self.payment_data(), self.db)

        self.assertEqual(payment.status, PaymentStatus.pending)
        self.assertIsNone(payment.confirmed_amount)
        events = list_payment_events(payment.id, self.db)
        self.assertEqual(len(events), 1)
        self.assertIsNone(events[0].from_status)
        self.assertEqual(events[0].to_status, PaymentStatus.pending)
        audit = self.db.scalar(
            select(AuditEvent).where(
                AuditEvent.entity_id == str(payment.id),
                AuditEvent.action == "payment.received",
            )
        )
        self.assertIsNotNone(audit)
        self.assertEqual(audit.actor, "Atencion a clientes")

    def test_verify_payment_confirms_amount_and_records_event(self) -> None:
        payment = create_payment(self.payment_data(), self.db)
        verified = verify_payment(
            payment.id,
            PaymentVerify(
                confirmed_amount=Decimal("500.00"),
                verified_by="Administrador",
            ),
            self.db,
        )

        self.assertEqual(verified.status, PaymentStatus.verified)
        self.assertEqual(verified.confirmed_amount, Decimal("500.00"))
        self.assertIsNotNone(verified.verified_at)
        self.assertEqual(len(list_payment_events(payment.id, self.db)), 2)
        actions = set(
            self.db.scalars(
                select(AuditEvent.action).where(
                    AuditEvent.entity_id == str(payment.id)
                )
            )
        )
        self.assertEqual(
            actions,
            {"payment.received", "payment.verified"},
        )

    def test_amount_difference_requires_verification_notes(self) -> None:
        payment = create_payment(self.payment_data(), self.db)

        with self.assertRaises(HTTPException) as context:
            verify_payment(
                payment.id,
                PaymentVerify(
                    confirmed_amount=Decimal("450.00"),
                    verified_by="Administrador",
                ),
                self.db,
            )
        self.assertEqual(context.exception.status_code, 409)

        verified = verify_payment(
            payment.id,
            PaymentVerify(
                confirmed_amount=Decimal("450.00"),
                verified_by="Administrador",
                notes="El banco confirma un monto menor",
            ),
            self.db,
        )
        self.assertEqual(verified.confirmed_amount, Decimal("450.00"))

    def test_rejected_payment_is_terminal(self) -> None:
        payment = create_payment(self.payment_data(), self.db)
        rejected = reject_payment(
            payment.id,
            PaymentDecision(
                performed_by="Administrador",
                reason="Comprobante no identificado en el banco",
            ),
            self.db,
        )

        self.assertEqual(rejected.status, PaymentStatus.rejected)
        with self.assertRaises(HTTPException) as context:
            verify_payment(
                payment.id,
                PaymentVerify(
                    confirmed_amount=Decimal("500.00"),
                    verified_by="Administrador",
                ),
                self.db,
            )
        self.assertEqual(context.exception.status_code, 409)

    def test_pending_payment_can_be_cancelled(self) -> None:
        payment = create_payment(self.payment_data(), self.db)
        cancelled = cancel_payment(
            payment.id,
            PaymentDecision(
                performed_by="Atencion a clientes",
                reason="Registro duplicado",
            ),
            self.db,
        )

        self.assertEqual(cancelled.status, PaymentStatus.cancelled)

    def test_service_must_belong_to_customer_history(self) -> None:
        unrelated = Customer(
            full_name="Persona sin este servicio",
            phones=["8997778899"],
        )
        self.db.add(unrelated)
        self.db.commit()

        with self.assertRaises(HTTPException) as context:
            create_payment(
                self.payment_data(customer_id=unrelated.id),
                self.db,
            )
        self.assertEqual(context.exception.status_code, 409)

    def test_list_payments_filters_by_customer_status_and_reference(self) -> None:
        payment = create_payment(self.payment_data(), self.db)

        by_customer = list_payments(
            self.db,
            customer_id=self.customer.id,
        )
        by_status = list_payments(
            self.db,
            payment_status=PaymentStatus.pending,
        )
        by_reference = list_payments(self.db, q="PAGO-801")

        self.assertEqual([item.id for item in by_customer], [payment.id])
        self.assertEqual([item.id for item in by_status], [payment.id])
        self.assertEqual([item.id for item in by_reference], [payment.id])


if __name__ == "__main__":
    unittest.main()
