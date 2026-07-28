import unittest
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.services import (
    create_service,
    get_service,
    list_services,
)
from app.db.base import Base
from app.models.customer import Customer
from app.models.service import Service, ServiceHolder, ServiceStatus
from app.schemas.service import ServiceCreate


class ServiceEndpointsTestCase(unittest.TestCase):
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

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def service_payload(self, amr_code: str = "AMR301") -> ServiceCreate:
        return ServiceCreate(
            customer_id=self.customer.id,
            amr_code=amr_code,
            address="Calle Principal 123, Reynosa",
            plan_name="Hogar 20 Mbps",
            monthly_price=Decimal("500.00"),
            payment_day=5,
            status=ServiceStatus.active,
        )

    def test_create_service_with_initial_holder(self) -> None:
        created = create_service(self.service_payload(), self.db)

        self.assertEqual(created.amr_code, "AMR301")
        self.assertEqual(created.current_customer_id, self.customer.id)
        self.assertEqual(self.db.query(Service).count(), 1)
        self.assertEqual(self.db.query(ServiceHolder).count(), 1)

        service_id = created.id
        self.db.close()
        self.db = Session(self.engine)

        persisted = get_service(service_id, self.db)
        self.assertEqual(persisted.current_customer_id, self.customer.id)

    def test_create_service_rejects_unknown_customer(self) -> None:
        payload = self.service_payload()
        payload.customer_id = uuid4()

        with self.assertRaises(HTTPException) as context:
            create_service(payload, self.db)

        self.assertEqual(context.exception.status_code, 404)

    def test_current_amr_code_must_be_unique(self) -> None:
        create_service(self.service_payload(), self.db)

        with self.assertRaises(HTTPException) as context:
            create_service(self.service_payload(), self.db)

        self.assertEqual(context.exception.status_code, 409)

    def test_list_services_filters_by_query_customer_and_status(self) -> None:
        service = create_service(self.service_payload("amr450"), self.db)

        self.assertEqual(list_services(db=self.db, q="AMR450"), [service])
        self.assertEqual(list_services(db=self.db, q="Principal"), [service])
        self.assertEqual(
            list_services(db=self.db, customer_id=self.customer.id),
            [service],
        )
        self.assertEqual(
            list_services(db=self.db, service_status=ServiceStatus.active),
            [service],
        )
        self.assertEqual(
            list_services(db=self.db, service_status=ServiceStatus.cancelled),
            [],
        )


if __name__ == "__main__":
    unittest.main()
