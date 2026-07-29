import unittest
from datetime import date, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.charges import (
    cancel_charge,
    create_charge,
    create_monthly_charge,
    get_customer_balance,
    get_service_balance,
    list_customer_charges,
    list_service_charges,
)
from app.api.v1.endpoints.services import (
    create_service,
    transition_service_status,
)
from app.db.base import Base
from app.models.charge import ChargeStatus, ChargeType
from app.models.customer import Customer
from app.models.service import ServiceStatus
from app.schemas.charge import (
    ChargeCancel,
    ChargeCreate,
    MonthlyChargeCreate,
)
from app.schemas.service import ServiceCreate, ServiceTransitionCreate


def current_month() -> date:
    return date.today().replace(day=1)


def previous_month(value: date) -> date:
    if value.month == 1:
        return date(value.year - 1, 12, 1)
    return date(value.year, value.month - 1, 1)


class ChargeTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.customer = Customer(
            full_name="Cliente de cargos",
            phones=["8993334455"],
        )
        self.db.add(self.customer)
        self.db.commit()
        service = create_service(
            ServiceCreate(
                customer_id=self.customer.id,
                amr_code="AMR701",
                address="Domicilio de cargos, Reynosa",
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

    def general_charge(
        self,
        amount: Decimal = Decimal("750.00"),
        due_date: date = date.today(),
    ) -> ChargeCreate:
        return ChargeCreate(
            charge_type=ChargeType.installation,
            description="Cargo de instalacion",
            amount=amount,
            due_date=due_date,
            generated_by="Atencion a clientes",
        )

    def prepare_monthly_billing(self) -> date:
        period = current_month()
        activation = previous_month(period).replace(day=5)
        self.service.activation_date = activation
        self.service.holders[0].start_date = activation
        self.db.commit()
        return period

    def test_create_charge_preserves_responsible_customer(self) -> None:
        charge = create_charge(
            self.service.id,
            self.general_charge(),
            self.db,
        )

        self.assertEqual(charge.customer_id, self.customer.id)
        self.assertEqual(charge.status, ChargeStatus.pending)
        self.assertEqual(charge.outstanding_balance, Decimal("750.00"))
        self.assertEqual(
            list_service_charges(self.service.id, self.db)[0].id,
            charge.id,
        )
        self.assertEqual(
            list_customer_charges(self.customer.id, self.db)[0].id,
            charge.id,
        )

    def test_monthly_charge_uses_agreed_price_and_payment_day(self) -> None:
        period = self.prepare_monthly_billing()

        charge = create_monthly_charge(
            self.service.id,
            MonthlyChargeCreate(
                billing_period=period,
                generated_by="Proceso mensual",
            ),
            self.db,
        )

        self.assertEqual(charge.amount, self.service.monthly_price)
        self.assertEqual(charge.due_date, period.replace(day=5))
        self.assertEqual(charge.billing_period, period)

        with self.assertRaises(HTTPException) as duplicate:
            create_monthly_charge(
                self.service.id,
                MonthlyChargeCreate(
                    billing_period=period,
                    generated_by="Proceso mensual",
                ),
                self.db,
            )
        self.assertEqual(duplicate.exception.status_code, 409)

    def test_monthly_charge_rejects_invalid_periods(self) -> None:
        period = self.prepare_monthly_billing()

        with self.assertRaises(HTTPException) as before_activation:
            create_monthly_charge(
                self.service.id,
                MonthlyChargeCreate(
                    billing_period=previous_month(period),
                    generated_by="Proceso mensual",
                ),
                self.db,
            )
        self.assertEqual(before_activation.exception.status_code, 409)

        future = (
            date(period.year + 1, 1, 1)
            if period.month == 12
            else date(period.year, period.month + 1, 1)
        )
        with self.assertRaises(HTTPException) as future_charge:
            create_monthly_charge(
                self.service.id,
                MonthlyChargeCreate(
                    billing_period=future,
                    generated_by="Proceso mensual",
                ),
                self.db,
            )
        self.assertEqual(future_charge.exception.status_code, 409)

    def test_cancel_charge_updates_balance_without_deleting_history(self) -> None:
        charge = create_charge(
            self.service.id,
            self.general_charge(),
            self.db,
        )
        before = get_service_balance(self.service.id, self.db)
        cancelled = cancel_charge(
            charge.id,
            ChargeCancel(
                cancelled_by="Administrador",
                reason="Cargo registrado por error",
            ),
            self.db,
        )
        after = get_service_balance(self.service.id, self.db)

        self.assertEqual(before.outstanding_balance, Decimal("750.00"))
        self.assertEqual(after.outstanding_balance, Decimal("0.00"))
        self.assertEqual(cancelled.status, ChargeStatus.cancelled)
        self.assertIsNotNone(cancelled.cancelled_at)
        self.assertEqual(
            len(list_service_charges(self.service.id, self.db)),
            1,
        )

    def test_balance_separates_overdue_and_current_charges(self) -> None:
        create_charge(
            self.service.id,
            self.general_charge(
                amount=Decimal("300.00"),
                due_date=date.today(),
            ),
            self.db,
        )
        create_charge(
            self.service.id,
            ChargeCreate(
                charge_type=ChargeType.additional_service,
                description="Servicio adicional",
                amount=Decimal("200.00"),
                due_date=date.today() + timedelta(days=1),
                generated_by="Atencion a clientes",
            ),
            self.db,
        )

        balance = get_service_balance(
            self.service.id,
            self.db,
            as_of=date.today() + timedelta(days=1),
        )

        self.assertEqual(balance.outstanding_balance, Decimal("500.00"))
        self.assertEqual(balance.overdue_balance, Decimal("300.00"))
        self.assertEqual(balance.open_charges, 2)

        customer_balance = get_customer_balance(
            self.customer.id,
            self.db,
            as_of=date.today() + timedelta(days=1),
        )
        self.assertEqual(
            customer_balance.outstanding_balance,
            Decimal("500.00"),
        )
        self.assertEqual(
            customer_balance.overdue_balance,
            Decimal("300.00"),
        )
        self.assertEqual(customer_balance.open_charges, 2)
        self.assertEqual(customer_balance.credit_balance, Decimal("0.00"))

    def test_monthly_type_must_use_specialized_endpoint(self) -> None:
        with self.assertRaises(HTTPException) as context:
            create_charge(
                self.service.id,
                ChargeCreate(
                    charge_type=ChargeType.monthly,
                    description="Mensualidad manual",
                    amount=Decimal("500.00"),
                    due_date=date.today(),
                    generated_by="Operador",
                ),
                self.db,
            )

        self.assertEqual(context.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
