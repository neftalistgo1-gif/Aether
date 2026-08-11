import unittest
from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.integrations.uisp import sync_devices
from app.models.asset import Asset, AssetStatus, AssetType
from app.models.plan import Plan, PlanPrice
from app.models.network_device import NetworkDevice
from app.models.service import Service, ServiceStatus


class UISPSynchronizationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        plan = Plan(name="15 Mbps", speed="15 Mbps")
        plan.prices.append(
            PlanPrice(monthly_price=Decimal("350.00"), valid_from=date(2026, 1, 1), changed_by="Sistema", reason="Catalogo")
        )
        self.db.add(plan)
        self.db.flush()
        self.service = Service(
            amr_code="AMR215", plan_id=plan.id, address="Fiesta #2712A Miravalle", plan_name="15 Mbps",
            monthly_price=Decimal("350.00"), payment_day=5, status=ServiceStatus.pending,
        )
        self.db.add(self.service)
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def devices(self) -> list[dict]:
        return [
            {
                "ipAddress": "192.168.5.22/24",
                "identification": {"id": "ap-1", "displayName": "AMRG_Miravalle_II", "role": "ap", "mac": "AA-BB-CC-DD-EE-01", "model": "Rocket Prism"},
                "overview": {"status": "active", "lastSeen": "2026-08-11T18:42:00Z"},
            },
            {
                "ipAddress": "192.168.5.235/24",
                "identification": {"id": "cpe-1", "displayName": "AMR215 Fiesta #2712A Miravalle", "role": "station", "mac": "AA-BB-CC-DD-EE-02", "model": "LiteBeam"},
                "overview": {"status": "active", "lastSeen": "2026-08-11T18:42:00Z"},
            },
        ]

    def test_sync_registers_installed_inventory_and_links_matching_service(self) -> None:
        result = sync_devices(self.db, self.devices())

        self.assertEqual(result["inventory_created"], 2)
        self.assertEqual(result["services_linked"], 1)
        assets = list(self.db.scalars(select(Asset).order_by(Asset.description)))
        self.assertEqual([asset.asset_type for asset in assets], [AssetType.cpe, AssetType.access_point])
        self.assertTrue(all(asset.status == AssetStatus.installed for asset in assets))
        device = self.db.scalar(
            select(NetworkDevice).where(NetworkDevice.uisp_device_id == "cpe-1")
        )
        self.assertEqual(device.service_id, self.service.id)
        self.assertIsNotNone(device.asset_id)

        repeated = sync_devices(self.db, self.devices())
        self.assertEqual(repeated["inventory_created"], 0)


if __name__ == "__main__":
    unittest.main()
