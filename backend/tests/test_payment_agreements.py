import unittest
from datetime import date, timedelta
from decimal import Decimal

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.charges import create_charge
from app.api.v1.endpoints.payment_agreements import (
    cancel_payment_agreement,
    create_payment_agreement,
    fulfill_payment_agreement,
    list_payment_agreements,
)
from app.api.v1.endpoints.services import (
    create_service,
    transition_service_status,
)
from app.db.base import Base
from app.models.charge import ChargeType
from app.models.customer import Customer
from app.models.payment_agreement import PaymentAgreementStatus
from app.models.service import ServiceStatus
from app.schemas.charge import ChargeCreate
from app.schemas.payment_agreement import (
    PaymentAgreementCreate,
    PaymentAgreementRead,
    PaymentAgreementResolve,
)
from app.schemas.service import ServiceCreate, ServiceTransitionCreate


class PaymentAgreementTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.customer = Customer(
            full_name="Cliente con convenio",
            phones=["8996112233"],
        )
        self.db.add(self.customer)
        self.db.commit()
        service = create_service(
            ServiceCreate(
                customer_id=self.customer.id,
                amr_code="AMR961",
                address="Domicilio con convenio, Reynosa",
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

    def add_debt(self, amount: Decimal = Decimal("500.00")) -> None:
        create_charge(
            self.service.id,
            ChargeCreate(
                charge_type=ChargeType.other,
                description="Saldo incluido en convenio",
                amount=amount,
                due_date=date.today(),
                generated_by="Atencion a clientes",
            ),
            self.db,
        )

    def agreement_data(self, **changes) -> PaymentAgreementCreate:
        values = {
            "terms": "Cliente pagara cuando reciba su siguiente ingreso",
            "authorized_by": "Atencion a clientes",
        }
        values.update(changes)
        return PaymentAgreementCreate(**values)

    def test_flexible_agreement_preserves_only_known_terms(self) -> None:
        self.add_debt()
        agreement = create_payment_agreement(
            self.service.id,
            self.agreement_data(),
            self.db,
        )

        self.assertTrue(agreement.folio.startswith("AGR-"))
        self.assertEqual(
            agreement.customer_id,
            self.service.current_customer_id,
        )
        self.assertEqual(agreement.status, PaymentAgreementStatus.active)
        self.assertIsNone(agreement.promised_amount)
        self.assertIsNone(agreement.promised_date)
        self.assertIsNone(agreement.installment_count)
        public = PaymentAgreementRead.model_validate(
            agreement
        ).model_dump()
        self.assertFalse(public["has_evidence"])
        self.assertNotIn("evidence_reference", public)

    def test_agreement_requires_debt_and_rejects_excess_amount(self) -> None:
        with self.assertRaises(HTTPException) as no_debt:
            create_payment_agreement(
                self.service.id,
                self.agreement_data(),
                self.db,
            )
        self.assertEqual(no_debt.exception.status_code, 409)

        self.add_debt()
        with self.assertRaises(HTTPException) as excess:
            create_payment_agreement(
                self.service.id,
                self.agreement_data(
                    promised_amount=Decimal("501.00")
                ),
                self.db,
            )
        self.assertEqual(excess.exception.status_code, 409)
        self.assertEqual(
            excess.exception.detail["outstanding_balance"],
            "500.00",
        )

    def test_optional_terms_are_validated_when_present(self) -> None:
        with self.assertRaises(ValidationError):
            self.agreement_data(
                promised_date=date.today() - timedelta(days=1)
            )
        with self.assertRaises(ValidationError):
            self.agreement_data(installment_count=0)
        with self.assertRaises(ValidationError):
            self.agreement_data(terms="   ")

    def test_agreement_can_be_fulfilled_once_and_filtered(self) -> None:
        self.add_debt()
        agreement = create_payment_agreement(
            self.service.id,
            self.agreement_data(
                promised_amount=Decimal("300.00"),
                promised_date=date.today() + timedelta(days=5),
                installment_count=2,
                evidence_reference="private/agreements/amr961",
            ),
            self.db,
        )
        resolution = PaymentAgreementResolve(
            performed_by="Supervisor de cobranza",
            reason="Cliente cumplio los terminos acordados",
        )
        fulfilled = fulfill_payment_agreement(
            self.service.id,
            agreement.id,
            resolution,
            self.db,
        )

        self.assertEqual(
            fulfilled.status,
            PaymentAgreementStatus.fulfilled,
        )
        self.assertIsNotNone(fulfilled.resolved_at)
        self.assertEqual(
            list_payment_agreements(
                self.service.id,
                PaymentAgreementStatus.active,
                self.db,
            ),
            [],
        )
        self.assertEqual(
            list_payment_agreements(
                self.service.id,
                PaymentAgreementStatus.fulfilled,
                self.db,
            ),
            [fulfilled],
        )
        with self.assertRaises(HTTPException) as repeated:
            cancel_payment_agreement(
                self.service.id,
                agreement.id,
                resolution,
                self.db,
            )
        self.assertEqual(repeated.exception.status_code, 409)

    def test_cancelled_service_cannot_receive_agreement(self) -> None:
        self.add_debt()
        self.service.status = ServiceStatus.cancelled
        self.db.commit()

        with self.assertRaises(HTTPException) as context:
            create_payment_agreement(
                self.service.id,
                self.agreement_data(),
                self.db,
            )
        self.assertEqual(context.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
