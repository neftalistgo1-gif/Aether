import unittest
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.holder_transfers import (
    list_holder_transfers,
    list_service_holders,
    transfer_service_holder,
)
from app.api.v1.endpoints.charges import create_charge
from app.api.v1.endpoints.services import create_service
from app.db.base import Base
from app.models.asset import (
    Asset,
    AssetAssignment,
    AssetOwner,
    AssetStatus,
    AssetType,
)
from app.models.audit import AuditEvent
from app.models.charge import Charge, ChargeStatus, ChargeType
from app.models.customer import Customer
from app.models.equipment_recovery import EquipmentRecovery
from app.models.holder_transfer import HolderTransfer
from app.models.mikrotik import MikrotikRouter, NetworkControlCommand
from app.models.network_assignment import NetworkAssignment
from app.models.payment import Payment, PaymentStatusEvent
from app.models.payment_allocation import CreditMovement, PaymentAllocation
from app.models.service import ServiceHolder, ServiceStatus
from app.schemas.holder_transfer import HolderTransferCreate
from app.schemas.charge import ChargeCreate
from app.schemas.service import ServiceCreate


class HolderTransferTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.previous_customer = Customer(
            full_name="Titular anterior",
            phones=["8997000001"],
        )
        self.new_customer = Customer(
            full_name="Titular nuevo",
            phones=["8997000002"],
        )
        self.third_customer = Customer(
            full_name="Tercer titular",
            phones=["8997000003"],
        )
        self.db.add_all(
            [
                self.previous_customer,
                self.new_customer,
                self.third_customer,
            ]
        )
        self.db.commit()
        self.service = create_service(
            ServiceCreate(
                customer_id=self.previous_customer.id,
                amr_code="AMR720",
                address="Calle Titular 100, Reynosa",
                plan_name="Hogar 20 Mbps",
                monthly_price=Decimal("500.00"),
                payment_day=10,
            ),
            self.db,
        )
        self.service.status = ServiceStatus.active
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def transfer_data(
        self,
        customer_id=None,
        effective_date: date | None = None,
    ) -> HolderTransferCreate:
        return HolderTransferCreate(
            new_customer_id=customer_id or self.new_customer.id,
            effective_date=effective_date or date.today(),
            transferred_by="Atencion a clientes",
            reason="Cesion autorizada por ambos titulares",
            contract_reference="CTR-2026-0720",
        )

    def test_transfer_preserves_service_equipment_and_old_debt(self) -> None:
        charge = Charge(
            customer_id=self.previous_customer.id,
            service_id=self.service.id,
            charge_type=ChargeType.monthly,
            description="Mensualidad anterior a la transferencia",
            amount=Decimal("500.00"),
            outstanding_balance=Decimal("500.00"),
            due_date=date.today(),
            billing_period=date.today().replace(day=1),
            status=ChargeStatus.pending,
            generated_by="Sistema",
        )
        asset = Asset(
            internal_code="ANT-TRANSFER-001",
            asset_type=AssetType.antenna,
            description="Antena instalada",
            owner=AssetOwner.amr,
            status=AssetStatus.assigned,
        )
        self.db.add_all([charge, asset])
        self.db.flush()
        assignment = AssetAssignment(
            asset_id=asset.id,
            service_id=self.service.id,
            assigned_by="Tecnico",
            condition_on_delivery="Funcionando",
            ownership=AssetOwner.amr,
        )
        self.db.add(assignment)
        self.db.commit()
        unchanged_service_values = (
            self.service.amr_code,
            self.service.address,
            self.service.plan_name,
            self.service.monthly_price,
            self.service.payment_day,
            self.service.grace_days,
            self.service.status,
        )

        transfer = transfer_service_holder(
            self.service.id,
            self.transfer_data(),
            self.db,
        )

        self.assertEqual(transfer.previous_customer_id, self.previous_customer.id)
        self.assertEqual(transfer.new_customer_id, self.new_customer.id)
        self.db.refresh(self.service)
        self.assertEqual(self.service.current_customer_id, self.new_customer.id)
        self.assertEqual(
            (
                self.service.amr_code,
                self.service.address,
                self.service.plan_name,
                self.service.monthly_price,
                self.service.payment_day,
                self.service.grace_days,
                self.service.status,
            ),
            unchanged_service_values,
        )
        self.db.refresh(charge)
        self.assertEqual(charge.customer_id, self.previous_customer.id)
        new_charge = create_charge(
            self.service.id,
            ChargeCreate(
                charge_type=ChargeType.additional_service,
                description="Cargo posterior a la transferencia",
                amount=Decimal("100.00"),
                due_date=date.today(),
                generated_by="Atencion a clientes",
            ),
            self.db,
        )
        self.assertEqual(new_charge.customer_id, self.new_customer.id)
        self.assertEqual(
            self.db.scalar(select(func.count()).select_from(Charge)),
            2,
        )
        self.db.refresh(assignment)
        self.assertIsNone(assignment.returned_at)
        self.assertEqual(assignment.service_id, self.service.id)

        audit = self.db.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "service.holder_transferred"
            )
        )
        self.assertIsNotNone(audit)
        self.assertEqual(audit.actor, "Atencion a clientes")

    def test_transfer_closes_previous_period_and_keeps_history(self) -> None:
        first = transfer_service_holder(
            self.service.id,
            self.transfer_data(),
            self.db,
        )
        second = transfer_service_holder(
            self.service.id,
            self.transfer_data(
                customer_id=self.third_customer.id,
            ),
            self.db,
        )

        holders = list_service_holders(self.service.id, self.db)
        transfers = list_holder_transfers(self.service.id, self.db)
        self.assertEqual(len(holders), 3)
        self.assertEqual(len(transfers), 2)
        holders_by_customer = {
            holder.customer_id: holder
            for holder in holders
        }
        self.assertEqual(
            holders_by_customer[self.previous_customer.id].end_date,
            date.today(),
        )
        self.assertEqual(
            holders_by_customer[self.new_customer.id].end_date,
            date.today(),
        )
        self.assertIsNone(
            holders_by_customer[self.third_customer.id].end_date
        )
        self.assertEqual(transfers[0].id, first.id)
        self.assertEqual(transfers[1].id, second.id)

    def test_current_customer_cannot_be_transferred_to_itself(self) -> None:
        with self.assertRaises(HTTPException) as error:
            transfer_service_holder(
                self.service.id,
                self.transfer_data(
                    customer_id=self.previous_customer.id,
                ),
                self.db,
            )
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(
            self.db.scalar(select(func.count()).select_from(HolderTransfer)),
            0,
        )

    def test_transfer_rejects_unknown_customer_and_noncurrent_date(self) -> None:
        with self.assertRaises(HTTPException) as unknown:
            transfer_service_holder(
                self.service.id,
                self.transfer_data(customer_id=uuid4()),
                self.db,
            )
        self.assertEqual(unknown.exception.status_code, 404)

        for invalid_date in (
            date.today() - timedelta(days=1),
            date.today() + timedelta(days=1),
        ):
            with self.subTest(invalid_date=invalid_date):
                with self.assertRaises(HTTPException) as invalid:
                    transfer_service_holder(
                        self.service.id,
                        self.transfer_data(effective_date=invalid_date),
                        self.db,
                    )
                self.assertEqual(invalid.exception.status_code, 409)

    def test_cancelled_service_cannot_change_holder(self) -> None:
        self.service.status = ServiceStatus.cancelled
        self.service.cancellation_date = date.today()
        self.db.commit()
        with self.assertRaises(HTTPException) as error:
            transfer_service_holder(
                self.service.id,
                self.transfer_data(),
                self.db,
            )
        self.assertEqual(error.exception.status_code, 409)
        current_holders = self.db.scalars(
            select(ServiceHolder).where(
                ServiceHolder.service_id == self.service.id,
                ServiceHolder.end_date.is_(None),
            )
        ).all()
        self.assertEqual(len(current_holders), 1)
        self.assertEqual(
            current_holders[0].customer_id,
            self.previous_customer.id,
        )


if __name__ == "__main__":
    unittest.main()
