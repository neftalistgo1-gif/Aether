import unittest
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.contracts import (
    create_contract,
    list_contracts,
    sign_contract,
    terminate_contract,
    void_contract,
)
from app.api.v1.endpoints.holder_transfers import transfer_service_holder
from app.api.v1.endpoints.installations import (
    complete_installation,
    create_installation,
)
from app.api.v1.endpoints.plans import create_plan
from app.api.v1.endpoints.service_plan_changes import change_service_plan
from app.api.v1.endpoints.services import create_service
from app.db.base import Base
from app.models.contract import (
    ContractAmendmentType,
    ContractStatus,
    EvidenceKind,
)
from app.models.customer import Customer
from app.models.holder_transfer import HolderTransfer
from app.models.installation import (
    CoverageResult,
    InstallationType,
)
from app.models.mikrotik import MikrotikRouter, NetworkControlCommand
from app.models.network_assignment import NetworkAssignment
from app.models.payment import Payment, PaymentStatusEvent
from app.models.payment_allocation import CreditMovement, PaymentAllocation
from app.models.service import ServiceStatus
from app.schemas.contract import (
    ContractCreate,
    ContractRead,
    ContractSign,
    ContractTerminate,
    ContractVoid,
)
from app.schemas.holder_transfer import HolderTransferCreate
from app.schemas.installation import InstallationComplete, InstallationCreate
from app.schemas.plan import PlanCreate
from app.schemas.service import ServiceCreate
from app.schemas.service_plan_change import ServicePlanChangeCreate


DIGITAL_HASH = "a" * 64


class ContractTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.customer = Customer(
            full_name="Cliente con contrato",
            phones=["8997440001"],
        )
        self.other_customer = Customer(
            full_name="Nuevo titular contrato",
            phones=["8997440002"],
        )
        self.db.add_all([self.customer, self.other_customer])
        self.db.commit()
        self.service = create_service(
            ServiceCreate(
                customer_id=self.customer.id,
                amr_code="AMR922",
                address="Calle Contrato 22, Reynosa",
                plan_name="Hogar 20 Mbps",
                monthly_price=Decimal("500.00"),
                payment_day=10,
            ),
            self.db,
        )
        self.service.status = ServiceStatus.active
        self.service.activation_date = date.today()
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def create_draft(self, start_date: date | None = None):
        return create_contract(
            self.service.id,
            ContractCreate(
                customer_id=self.customer.id,
                version="2026.1",
                start_date=start_date or date.today(),
                created_by="Atencion a clientes",
            ),
            self.db,
        )

    def sign_data(
        self,
        kind: EvidenceKind = EvidenceKind.private_digital,
    ) -> ContractSign:
        return ContractSign(
            signed_on=date.today(),
            signed_by="Atencion a clientes",
            evidence_kind=kind,
            document_reference=(
                "archivo-privado:contratos/registro-seguro"
                if kind == EvidenceKind.private_digital
                else "archivo-fisico:caja-3/carpeta-22"
            ),
            document_sha256=(
                DIGITAL_HASH
                if kind == EvidenceKind.private_digital
                else None
            ),
        )

    def activate_contract(self):
        draft = self.create_draft()
        return sign_contract(
            self.service.id,
            draft.id,
            self.sign_data(),
            self.db,
        )

    def test_draft_and_signature_preserve_snapshot_and_hide_reference(self) -> None:
        draft = self.create_draft()
        self.assertTrue(draft.folio.startswith("CTR-"))
        self.assertEqual(draft.status, ContractStatus.draft)
        self.assertEqual(draft.address_snapshot, self.service.address)
        self.assertEqual(draft.plan_name_snapshot, self.service.plan_name)
        self.assertEqual(
            draft.monthly_price_snapshot,
            self.service.monthly_price,
        )

        signed = sign_contract(
            self.service.id,
            draft.id,
            self.sign_data(),
            self.db,
        )
        self.assertEqual(signed.status, ContractStatus.active)
        self.assertTrue(signed.has_document)
        public_data = ContractRead.model_validate(signed).model_dump()
        self.assertNotIn("document_reference", public_data)
        self.assertNotIn("termination_document_reference", public_data)
        self.assertEqual(public_data["document_sha256"], DIGITAL_HASH)
        self.assertEqual(list_contracts(self.service.id, None, self.db), [signed])

    def test_digital_evidence_requires_hash_and_physical_does_not(self) -> None:
        with self.assertRaises(ValidationError):
            ContractSign(
                signed_on=date.today(),
                signed_by="Atencion a clientes",
                evidence_kind=EvidenceKind.private_digital,
                document_reference="archivo-privado:sin-hash",
            )
        draft = self.create_draft()
        signed = sign_contract(
            self.service.id,
            draft.id,
            self.sign_data(EvidenceKind.physical),
            self.db,
        )
        self.assertEqual(signed.evidence_kind, EvidenceKind.physical)
        self.assertIsNone(signed.document_sha256)

    def test_only_one_active_contract_and_drafts_can_be_voided(self) -> None:
        self.activate_contract()
        second = self.create_draft()
        with self.assertRaises(HTTPException) as duplicate:
            sign_contract(
                self.service.id,
                second.id,
                self.sign_data(EvidenceKind.physical),
                self.db,
            )
        self.assertEqual(duplicate.exception.status_code, 409)
        voided = void_contract(
            self.service.id,
            second.id,
            ContractVoid(
                voided_by="Atencion a clientes",
                reason="Borrador duplicado",
            ),
            self.db,
        )
        self.assertEqual(voided.status, ContractStatus.void)

    def test_active_contract_must_end_before_holder_transfer(self) -> None:
        contract = self.activate_contract()
        transfer = HolderTransferCreate(
            new_customer_id=self.other_customer.id,
            transferred_by="Atencion a clientes",
            reason="Cesion autorizada por ambos titulares",
        )
        with self.assertRaises(HTTPException) as blocked:
            transfer_service_holder(self.service.id, transfer, self.db)
        self.assertEqual(blocked.exception.status_code, 409)

        terminated = terminate_contract(
            self.service.id,
            contract.id,
            ContractTerminate(
                terminated_by="Atencion a clientes",
                reason="Cambio de titular autorizado",
                evidence_kind=EvidenceKind.physical,
                document_reference="archivo-fisico:caja-3/terminacion-22",
            ),
            self.db,
        )
        self.assertEqual(terminated.status, ContractStatus.terminated)
        self.assertTrue(terminated.termination_folio.startswith("TER-"))
        completed_transfer = transfer_service_holder(
            self.service.id,
            transfer,
            self.db,
        )
        self.assertEqual(
            completed_transfer.new_customer_id,
            self.other_customer.id,
        )

    def test_plan_change_creates_contract_amendment(self) -> None:
        contract = self.activate_contract()
        plan = create_plan(
            PlanCreate(
                name="Hogar 30 Mbps",
                speed="30 Mbps",
                monthly_price=Decimal("600.00"),
                valid_from=date.today() - timedelta(days=1),
                created_by="Administracion",
            ),
            self.db,
        )
        change_service_plan(
            self.service.id,
            ServicePlanChangeCreate(
                plan_id=plan.id,
                requested_by="Cliente titular",
                applied_by="Soporte tecnico",
                reason="Cambio de velocidad solicitado",
            ),
            self.db,
        )
        self.db.refresh(contract)
        self.assertEqual(contract.plan_name_snapshot, plan.name)
        self.assertEqual(
            contract.monthly_price_snapshot,
            Decimal("600.00"),
        )
        self.assertEqual(len(contract.amendments), 1)
        self.assertEqual(
            contract.amendments[0].amendment_type,
            ContractAmendmentType.plan_change,
        )

    def test_address_change_creates_contract_amendment(self) -> None:
        contract = self.activate_contract()
        installation = create_installation(
            self.service.id,
            InstallationCreate(
                installation_type=InstallationType.address_change,
                coverage_result=CoverageResult.viable,
                coverage_checked_by="Tecnico instalador",
                coverage_checked_at=datetime.now(UTC),
                scheduled_for=date.today() + timedelta(days=1),
                cost=Decimal("0.00"),
                new_address="Calle Contrato Nueva 220, Reynosa",
                registered_by="Atencion a clientes",
            ),
            self.db,
        )
        complete_installation(
            self.service.id,
            installation.id,
            InstallationComplete(
                completed_at=datetime.now(UTC),
                technicians=["Tecnico uno"],
                antenna_photos=["antena-1.jpg", "antena-2.jpg"],
                modem_photos=["modem-1.jpg"],
                navigation_confirmed=True,
                navigation_confirmed_by="Cliente",
                performed_by="Tecnico uno",
            ),
            self.db,
        )
        self.db.refresh(contract)
        self.assertEqual(
            contract.address_snapshot,
            "Calle Contrato Nueva 220, Reynosa",
        )
        self.assertEqual(len(contract.amendments), 1)
        self.assertEqual(
            contract.amendments[0].amendment_type,
            ContractAmendmentType.address_change,
        )

    def test_future_contract_and_wrong_holder_are_rejected(self) -> None:
        with self.assertRaises(HTTPException) as wrong_holder:
            create_contract(
                self.service.id,
                ContractCreate(
                    customer_id=self.other_customer.id,
                    version="2026.1",
                    start_date=date.today(),
                    created_by="Atencion a clientes",
                ),
                self.db,
            )
        self.assertEqual(wrong_holder.exception.status_code, 409)

        future = self.create_draft(
            start_date=date.today() + timedelta(days=1)
        )
        with self.assertRaises(HTTPException) as too_early:
            sign_contract(
                self.service.id,
                future.id,
                self.sign_data(),
                self.db,
            )
        self.assertEqual(too_early.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
