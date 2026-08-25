import unittest
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.customers import (
    create_customer,
    delete_customer,
    get_customer,
    list_customers,
    update_customer,
)
from app.db.base import Base
from app.models.audit import AuditEvent
from app.models.customer import Customer
from app.schemas.customer import CustomerCreate, CustomerUpdate


class CustomerEndpointsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_create_and_list_customer(self) -> None:
        payload = CustomerCreate(
            full_name="María García",
            phones=["8991234567"],
            email="maria@example.com",
        )

        created = create_customer(payload, self.db)

        self.assertEqual(created.full_name, payload.full_name)
        self.assertEqual(list_customers(db=self.db), [created])
        self.assertEqual(self.db.query(Customer).count(), 1)
        audit = self.db.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "customer.created"
            )
        )
        self.assertEqual(audit.after_data["full_name"], payload.full_name)

        customer_id = created.id
        self.db.close()
        self.db = Session(self.engine)

        persisted = get_customer(customer_id, self.db)
        self.assertEqual(persisted.full_name, payload.full_name)
        self.assertEqual(persisted.phones, payload.phones)

    def test_get_unknown_customer_returns_404(self) -> None:
        with self.assertRaises(HTTPException) as context:
            get_customer(uuid4(), self.db)

        self.assertEqual(context.exception.status_code, 404)

    def test_update_customer_persists_partial_changes(self) -> None:
        created = create_customer(
            CustomerCreate(
                full_name="María García",
                phones=["8991234567"],
                email="maria@example.com",
            ),
            self.db,
        )

        updated = update_customer(
            created.id,
            CustomerUpdate(
                notes="Cliente actualizado",
                email=None,
                reason="Cliente solicita actualizar sus datos",
            ),
            self.db,
        )

        self.assertEqual(updated.full_name, "María García")
        self.assertIsNone(updated.email)
        self.assertEqual(updated.notes, "Cliente actualizado")
        audit = self.db.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "customer.updated"
            )
        )
        self.assertEqual(
            audit.reason,
            "Cliente solicita actualizar sus datos",
        )
        self.assertEqual(audit.before_data["email"], "maria@example.com")
        self.assertIsNone(audit.after_data["email"])

        customer_id = updated.id
        self.db.close()
        self.db = Session(self.engine)

        persisted = get_customer(customer_id, self.db)
        self.assertIsNone(persisted.email)
        self.assertEqual(persisted.notes, "Cliente actualizado")

    def test_search_customers_by_name_or_phone(self) -> None:
        maria = create_customer(
            CustomerCreate(
                full_name="María García",
                phones=["8991234567"],
            ),
            self.db,
        )
        juan = create_customer(
            CustomerCreate(
                full_name="Juan Pérez",
                phones=["8687654321"],
            ),
            self.db,
        )

        self.assertEqual(list_customers(db=self.db, q="garcía"), [maria])
        self.assertEqual(list_customers(db=self.db, q="868765"), [juan])
        self.assertEqual(list_customers(db=self.db, q="sin coincidencia"), [])

    def test_update_requires_at_least_one_field(self) -> None:
        with self.assertRaises(ValidationError):
            CustomerUpdate(reason="Sin cambios")

    def test_update_rejects_null_required_fields(self) -> None:
        with self.assertRaises(ValidationError):
            CustomerUpdate(
                full_name=None,
                reason="Prueba de campo obligatorio",
            )

    def test_update_rejects_unchanged_data(self) -> None:
        created = create_customer(
            CustomerCreate(
                full_name="Cliente sin cambios",
                phones=["8999001122"],
            ),
            self.db,
        )
        with self.assertRaises(HTTPException) as rejected:
            update_customer(
                created.id,
                CustomerUpdate(
                    full_name=created.full_name,
                    reason="Intento sin cambios reales",
                ),
                self.db,
            )
        self.assertEqual(rejected.exception.status_code, 409)

    def test_delete_customer_without_history(self) -> None:
        created = create_customer(
            CustomerCreate(
                full_name="Cliente temporal",
                phones=["Pendiente"],
                email="Pendiente",
            ),
            self.db,
        )

        self.assertIsNone(delete_customer(created.id, self.db))
        self.assertEqual(self.db.query(Customer).count(), 0)
        audit = self.db.scalar(
            select(AuditEvent).where(AuditEvent.action == "customer.deleted")
        )
        self.assertEqual(audit.before_data["full_name"], "Cliente temporal")


if __name__ == "__main__":
    unittest.main()
