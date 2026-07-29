import unittest
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.service_operations import (
    create_cancellation,
    execute_scheduled_cancellation,
    list_reactivations,
    list_suspensions,
    reactivate_service,
    suspend_service,
)
from app.api.v1.endpoints.services import (
    create_service,
    get_service,
    transition_service_status,
)
from app.db.base import Base
from app.models.customer import Customer
from app.models.notification import (
    CustomerNotification,
    NotificationChannel,
    NotificationPurpose,
    NotificationStatus,
)
from app.models.charge import Charge, ChargeStatus, ChargeType
from app.models.service import ServiceStatus
from app.models.service_operations import (
    CancellationStatus,
    NetworkOperationResult,
)
from app.schemas.service import ServiceCreate, ServiceTransitionCreate
from app.schemas.service_operations import (
    CancellationCreate,
    CancellationExecute,
    ReactivationCreate,
    SuspensionCreate,
)


class ServiceOperationsTestCase(unittest.TestCase):
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
        self.db.add(
            Charge(
                customer_id=self.customer.id,
                service_id=self.service.id,
                charge_type=ChargeType.monthly,
                description="Mensualidad vencida",
                amount=Decimal("500.00"),
                outstanding_balance=Decimal("500.00"),
                due_date=date.today() - timedelta(days=5),
                billing_period=date.today().replace(day=1),
                status=ChargeStatus.pending,
                generated_by="Proceso mensual",
            )
        )
        self.notification = CustomerNotification(
            customer_id=self.customer.id,
            service_id=self.service.id,
            channel=NotificationChannel.whatsapp,
            purpose=NotificationPurpose.suspension_warning,
            status=NotificationStatus.delivered,
            recipient=self.customer.phones[0],
            message_summary="Aviso previo de suspensión por adeudo",
            evidence_reference="private/notifications/amr301-warning",
            occurred_at=datetime.now(UTC),
            recorded_by="Atención a clientes",
        )
        self.db.add(self.notification)
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def suspension_payload(
        self,
        result: NetworkOperationResult = NetworkOperationResult.manual,
    ) -> SuspensionCreate:
        return SuspensionCreate(
            scheduled_for=date.today(),
            reason="Mensualidad vencida",
            debt_amount=Decimal("500.00"),
            grace_period_elapsed=True,
            extension_checked=True,
            has_active_extension=False,
            notification_id=self.notification.id,
            performed_by="Técnico de red",
            mikrotik_result=result,
            mikrotik_details="Operación de prueba",
        )

    def reactivation_payload(
        self,
        result: NetworkOperationResult = NetworkOperationResult.manual,
    ) -> ReactivationCreate:
        return ReactivationCreate(
            reason="Pago verificado",
            authorized_by="Atención a clientes",
            performed_by="Técnico de red",
            debt_amount=Decimal("500.00"),
            mikrotik_result=result,
            mikrotik_details="Operación de prueba",
        )

    def cancellation_payload(
        self,
        effective_date: date,
    ) -> CancellationCreate:
        return CancellationCreate(
            requester_customer_id=self.customer.id,
            effective_date=effective_date,
            reason="Baja solicitada por el cliente",
            pending_balance=Decimal("0.00"),
            credit_balance=Decimal("0.00"),
            registered_by="Atención a clientes",
            equipment_pending_notes="Recuperar antena, módem y PoE",
        )

    def test_suspension_requires_all_business_checks(self) -> None:
        payload = self.suspension_payload()
        payload.grace_period_elapsed = False

        with self.assertRaises(HTTPException) as context:
            suspend_service(self.service.id, payload, self.db)

        self.assertEqual(context.exception.status_code, 409)
        self.assertEqual(
            get_service(self.service.id, self.db).status,
            ServiceStatus.active,
        )
        self.assertEqual(list_suspensions(self.service.id, self.db), [])

    def test_suspension_cannot_execute_before_scheduled_date(self) -> None:
        data = self.suspension_payload().model_dump()
        data["scheduled_for"] = date.today() + timedelta(days=1)

        with self.assertRaises(ValidationError):
            SuspensionCreate(**data)

    def test_failed_suspension_is_recorded_without_changing_status(self) -> None:
        attempt = suspend_service(
            self.service.id,
            self.suspension_payload(NetworkOperationResult.failed),
            self.db,
        )

        self.assertEqual(
            attempt.mikrotik_result,
            NetworkOperationResult.failed,
        )
        self.assertEqual(
            get_service(self.service.id, self.db).status,
            ServiceStatus.active,
        )
        self.assertEqual(len(list_suspensions(self.service.id, self.db)), 1)
        self.assertEqual(len(attempt.debt_snapshot), 1)
        self.assertEqual(
            attempt.debt_snapshot[0]["outstanding_balance"],
            "500.00",
        )

    def test_claimed_automatic_success_requires_verified_command(self) -> None:
        with self.assertRaises(HTTPException) as context:
            suspend_service(
                self.service.id,
                self.suspension_payload(NetworkOperationResult.success),
                self.db,
            )
        self.assertEqual(context.exception.status_code, 409)

    def test_suspension_debt_must_match_calculated_balance(self) -> None:
        payload = self.suspension_payload()
        payload.debt_amount = Decimal("400.00")

        with self.assertRaises(HTTPException) as context:
            suspend_service(self.service.id, payload, self.db)

        self.assertEqual(context.exception.status_code, 409)
        self.assertEqual(context.exception.detail["actual_debt"], "500.00")

    def test_suspension_requires_a_delivered_notification(self) -> None:
        self.notification.status = NotificationStatus.failed
        self.notification.failure_reason = "No se pudo entregar"
        self.db.commit()
        with self.assertRaises(HTTPException) as context:
            suspend_service(
                self.service.id,
                self.suspension_payload(),
                self.db,
            )
        self.assertEqual(context.exception.status_code, 409)

    def test_successful_notification_cannot_be_reused(self) -> None:
        suspend_service(
            self.service.id,
            self.suspension_payload(),
            self.db,
        )
        self.service.status = ServiceStatus.active
        self.db.commit()
        with self.assertRaises(HTTPException) as context:
            suspend_service(
                self.service.id,
                self.suspension_payload(),
                self.db,
            )
        self.assertEqual(context.exception.status_code, 409)

    def test_suspend_and_reactivate_with_retry(self) -> None:
        suspend_service(
            self.service.id,
            self.suspension_payload(),
            self.db,
        )
        self.assertEqual(
            get_service(self.service.id, self.db).status,
            ServiceStatus.suspended,
        )

        reactivate_service(
            self.service.id,
            self.reactivation_payload(NetworkOperationResult.failed),
            self.db,
        )
        self.assertEqual(
            get_service(self.service.id, self.db).status,
            ServiceStatus.suspended,
        )

        reactivate_service(
            self.service.id,
            self.reactivation_payload(),
            self.db,
        )
        self.assertEqual(
            get_service(self.service.id, self.db).status,
            ServiceStatus.active,
        )
        self.assertEqual(
            len(list_reactivations(self.service.id, self.db)),
            2,
        )

    def test_reactivation_requires_current_aether_balance(self) -> None:
        suspend_service(
            self.service.id,
            self.suspension_payload(),
            self.db,
        )
        payload = self.reactivation_payload()
        payload.debt_amount = Decimal("0.00")

        with self.assertRaises(HTTPException) as context:
            reactivate_service(self.service.id, payload, self.db)

        self.assertEqual(context.exception.status_code, 409)
        self.assertEqual(
            context.exception.detail["actual_debt"],
            "500.00",
        )
        self.assertEqual(
            get_service(self.service.id, self.db).status,
            ServiceStatus.suspended,
        )

    def test_immediate_cancellation_is_final(self) -> None:
        cancellation = create_cancellation(
            self.service.id,
            self.cancellation_payload(date.today()),
            self.db,
        )

        self.assertEqual(cancellation.status, CancellationStatus.executed)
        self.assertIsNotNone(cancellation.executed_at)
        self.assertTrue(cancellation.folio.startswith("CAN-"))
        self.assertEqual(
            get_service(self.service.id, self.db).status,
            ServiceStatus.cancelled,
        )

    def test_future_cancellation_waits_for_effective_date(self) -> None:
        cancellation = create_cancellation(
            self.service.id,
            self.cancellation_payload(date.today() + timedelta(days=1)),
            self.db,
        )

        self.assertEqual(cancellation.status, CancellationStatus.scheduled)
        self.assertEqual(
            get_service(self.service.id, self.db).status,
            ServiceStatus.active,
        )

        with self.assertRaises(HTTPException) as context:
            execute_scheduled_cancellation(
                self.service.id,
                CancellationExecute(performed_by="Atención a clientes"),
                self.db,
            )
        self.assertEqual(context.exception.status_code, 409)

        cancellation.effective_date = date.today()
        self.db.commit()
        executed = execute_scheduled_cancellation(
            self.service.id,
            CancellationExecute(performed_by="Atención a clientes"),
            self.db,
        )
        self.assertEqual(executed.status, CancellationStatus.executed)
        self.assertEqual(
            get_service(self.service.id, self.db).status,
            ServiceStatus.cancelled,
        )

    def test_cancellation_requester_must_be_current_holder(self) -> None:
        payload = self.cancellation_payload(date.today())
        payload.requester_customer_id = uuid4()

        with self.assertRaises(HTTPException) as context:
            create_cancellation(self.service.id, payload, self.db)

        self.assertEqual(context.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
