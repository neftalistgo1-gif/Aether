import unittest
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.charges import (
    create_charge,
    create_monthly_charge,
)
from app.api.v1.endpoints.payment_allocations import (
    apply_payment,
    get_credit_balance,
    list_credit_movements,
    list_payment_allocations,
    refund_credit,
)
from app.api.v1.endpoints.payments import create_payment, verify_payment
from app.api.v1.endpoints.services import (
    create_service,
    transition_service_status,
)
from app.db.base import Base
from app.models.charge import ChargeStatus, ChargeType
from app.models.customer import Customer
from app.models.payment import PaymentMethod
from app.models.payment_allocation import CreditMovementType
from app.models.service import ServiceStatus
from app.schemas.charge import ChargeCreate, MonthlyChargeCreate
from app.schemas.payment import PaymentCreate, PaymentVerify
from app.schemas.payment_allocation import (
    CreditRefundCreate,
    PaymentApply,
)
from app.schemas.service import ServiceCreate, ServiceTransitionCreate


def previous_month(value: date) -> date:
    if value.month == 1:
        return date(value.year - 1, 12, 1)
    return date(value.year, value.month - 1, 1)


class PaymentAllocationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.customer = Customer(
            full_name="Cliente de aplicaciones",
            phones=["8995556677"],
        )
        self.db.add(self.customer)
        self.db.commit()
        service = create_service(
            ServiceCreate(
                customer_id=self.customer.id,
                amr_code="AMR901",
                address="Domicilio de aplicaciones, Reynosa",
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

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def create_general_charge(
        self,
        amount: Decimal,
        due_date: date,
        charge_type: ChargeType,
    ):
        return create_charge(
            self.service.id,
            ChargeCreate(
                charge_type=charge_type,
                description=f"Cargo {charge_type.value}",
                amount=amount,
                due_date=due_date,
                generated_by="Atencion a clientes",
            ),
            self.db,
        )

    def create_verified_payment(self, amount: Decimal):
        payment = create_payment(
            PaymentCreate(
                customer_id=self.customer.id,
                service_id=self.service.id,
                declared_amount=amount,
                declared_at=datetime.now(UTC),
                method=PaymentMethod.bank_transfer,
                reference=f"PAGO-{amount}",
                received_by="Atencion a clientes",
            ),
            self.db,
        )
        return verify_payment(
            payment.id,
            PaymentVerify(
                confirmed_amount=amount,
                verified_by="Administrador",
            ),
            self.db,
        )

    def test_payment_applies_to_oldest_charges_first(self) -> None:
        oldest = self.create_general_charge(
            Decimal("300.00"),
            date.today(),
            ChargeType.installation,
        )
        newest = self.create_general_charge(
            Decimal("400.00"),
            date.today() + timedelta(days=1),
            ChargeType.additional_service,
        )
        payment = self.create_verified_payment(Decimal("500.00"))

        result = apply_payment(
            payment.id,
            PaymentApply(applied_by="Administrador"),
            self.db,
        )

        self.assertEqual(result.allocated_amount, Decimal("500.00"))
        self.assertEqual(result.credit_generated, Decimal("0.00"))
        self.assertEqual(oldest.status, ChargeStatus.paid)
        self.assertEqual(newest.status, ChargeStatus.partial)
        self.assertEqual(newest.outstanding_balance, Decimal("200.00"))
        self.assertEqual(len(result.allocations), 2)

    def test_payment_excess_creates_credit(self) -> None:
        charge = self.create_general_charge(
            Decimal("300.00"),
            date.today(),
            ChargeType.installation,
        )
        payment = self.create_verified_payment(Decimal("500.00"))

        result = apply_payment(
            payment.id,
            PaymentApply(applied_by="Administrador"),
            self.db,
        )

        self.assertEqual(charge.status, ChargeStatus.paid)
        self.assertEqual(result.credit_generated, Decimal("200.00"))
        self.assertEqual(
            get_credit_balance(self.customer.id, self.db).balance,
            Decimal("200.00"),
        )

    def test_unverified_or_already_applied_payment_is_rejected(self) -> None:
        pending = create_payment(
            PaymentCreate(
                customer_id=self.customer.id,
                service_id=self.service.id,
                declared_amount=Decimal("500.00"),
                method=PaymentMethod.cash,
                received_by="Atencion a clientes",
            ),
            self.db,
        )
        with self.assertRaises(HTTPException) as unverified:
            apply_payment(
                pending.id,
                PaymentApply(applied_by="Administrador"),
                self.db,
            )
        self.assertEqual(unverified.exception.status_code, 409)

        verified = self.create_verified_payment(Decimal("500.00"))
        apply_payment(
            verified.id,
            PaymentApply(applied_by="Administrador"),
            self.db,
        )
        with self.assertRaises(HTTPException) as repeated:
            apply_payment(
                verified.id,
                PaymentApply(applied_by="Administrador"),
                self.db,
            )
        self.assertEqual(repeated.exception.status_code, 409)

    def test_directed_application_requires_reason_and_respects_order(self) -> None:
        first = self.create_general_charge(
            Decimal("300.00"),
            date.today(),
            ChargeType.installation,
        )
        selected = self.create_general_charge(
            Decimal("400.00"),
            date.today() + timedelta(days=1),
            ChargeType.additional_service,
        )
        payment = self.create_verified_payment(Decimal("250.00"))

        with self.assertRaises(ValueError):
            PaymentApply(
                applied_by="Administrador",
                charge_ids=[selected.id],
            )

        apply_payment(
            payment.id,
            PaymentApply(
                applied_by="Administrador",
                charge_ids=[selected.id],
                reason="Cliente solicita cubrir servicio adicional",
            ),
            self.db,
        )
        self.assertEqual(first.outstanding_balance, Decimal("300.00"))
        self.assertEqual(selected.outstanding_balance, Decimal("150.00"))

    def test_credit_is_automatically_applied_to_new_monthly_charge(self) -> None:
        payment = self.create_verified_payment(Decimal("1000.00"))
        apply_payment(
            payment.id,
            PaymentApply(applied_by="Administrador"),
            self.db,
        )
        period = date.today().replace(day=1)
        activation = previous_month(period).replace(day=5)
        self.service.activation_date = activation
        self.service.holders[0].start_date = activation
        self.db.commit()

        monthly = create_monthly_charge(
            self.service.id,
            MonthlyChargeCreate(
                billing_period=period,
                generated_by="Proceso mensual",
            ),
            self.db,
        )

        self.assertEqual(monthly.status, ChargeStatus.paid)
        self.assertEqual(monthly.outstanding_balance, Decimal("0.00"))
        self.assertEqual(
            get_credit_balance(self.customer.id, self.db).balance,
            Decimal("500.00"),
        )
        movements = list_credit_movements(self.customer.id, self.db)
        self.assertEqual(
            movements[-1].movement_type,
            CreditMovementType.charge_application,
        )

    def test_credit_refund_cannot_exceed_balance(self) -> None:
        payment = self.create_verified_payment(Decimal("500.00"))
        apply_payment(
            payment.id,
            PaymentApply(applied_by="Administrador"),
            self.db,
        )
        refund_credit(
            self.customer.id,
            CreditRefundCreate(
                amount=Decimal("200.00"),
                service_id=self.service.id,
                performed_by="Administrador",
                reason="Devolucion solicitada por el cliente",
            ),
            self.db,
        )
        self.assertEqual(
            get_credit_balance(self.customer.id, self.db).balance,
            Decimal("300.00"),
        )

        with self.assertRaises(HTTPException) as excessive:
            refund_credit(
                self.customer.id,
                CreditRefundCreate(
                    amount=Decimal("400.00"),
                    performed_by="Administrador",
                    reason="Intento superior al saldo",
                ),
                self.db,
            )
        self.assertEqual(excessive.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
