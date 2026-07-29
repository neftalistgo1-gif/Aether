import os
import unittest
from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.mikrotik import (
    control_service_network,
    create_router,
    retry_network_command,
    update_router,
)
from app.api.v1.endpoints.network_assignments import create_network_assignment
from app.api.v1.endpoints.services import create_service
from app.db.base import Base
from app.integrations.mikrotik import RouterExecutionResult
from app.models.customer import Customer
from app.models.mikrotik import (
    MikrotikRouter,
    NetworkCommandStatus,
    NetworkControlAction,
)
from app.models.network_assignment import NetworkAssignment
from app.models.service import ServiceStatus
from app.schemas.mikrotik import (
    MikrotikRouterCreate,
    MikrotikRouterUpdate,
    NetworkControlRequest,
    NetworkControlRetry,
)
from app.schemas.network_assignment import NetworkAssignmentCreate
from app.schemas.service import ServiceCreate


class MikroTikControlTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        customer = Customer(
            full_name="Cliente MikroTik",
            phones=["8993334455"],
        )
        self.db.add(customer)
        self.db.commit()
        self.service = create_service(
            ServiceCreate(
                customer_id=customer.id,
                amr_code="AMR901",
                address="Calle Router 100, Reynosa",
                plan_name="Hogar 30 Mbps",
                monthly_price=Decimal("600.00"),
                payment_day=10,
            ),
            self.db,
        )
        self.service.status = ServiceStatus.active
        self.service.activation_date = date.today()
        self.db.commit()
        create_network_assignment(
            self.service.id,
            NetworkAssignmentCreate(
                router_name="CCR-Principal",
                ip_address="10.50.0.10",
                tower_name="Torre Centro",
                access_point_name="AP-Centro-01",
                antenna_name="AMR901 Cliente",
                technician="Tecnico de red",
                change_reason="Alta inicial",
            ),
            self.db,
        )
        self.router = create_router(
            MikrotikRouterCreate(
                name="CCR-Principal",
                endpoint_url="https://10.0.0.1",
                suspended_address_list="aether-suspendidos",
                credential_key="principal",
            ),
            self.db,
        )

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def request(
        self,
        key: str = "mikrotik-test-001",
        dry_run: bool = True,
    ) -> NetworkControlRequest:
        return NetworkControlRequest(
            requested_by="Operador de red",
            idempotency_key=key,
            dry_run=dry_run,
        )

    def test_router_requires_https(self) -> None:
        with self.assertRaises(ValidationError):
            MikrotikRouterCreate(
                name="Inseguro",
                endpoint_url="http://10.0.0.2",
                suspended_address_list="suspendidos",
                credential_key="inseguro",
            )

    def test_router_starts_disabled_and_reports_missing_credentials(self) -> None:
        self.assertFalse(self.router.enabled)
        self.assertFalse(self.router.credentials_configured)

    def test_enabling_router_requires_external_credentials(self) -> None:
        with self.assertRaises(HTTPException) as context:
            update_router(
                self.router.id,
                MikrotikRouterUpdate(enabled=True),
                self.db,
            )
        self.assertEqual(context.exception.status_code, 409)

        environment = {
            "MIKROTIK_PRINCIPAL_USERNAME": "aether",
            "MIKROTIK_PRINCIPAL_PASSWORD": "secret",
        }
        with patch.dict(os.environ, environment, clear=False):
            enabled = update_router(
                self.router.id,
                MikrotikRouterUpdate(enabled=True),
                self.db,
            )
        self.assertTrue(enabled.enabled)
        self.assertTrue(enabled.credentials_configured)

    def test_dry_run_is_safe_audited_and_idempotent(self) -> None:
        command = control_service_network(
            self.service.id,
            NetworkControlAction.suspend,
            self.request(),
            self.db,
        )
        repeated = control_service_network(
            self.service.id,
            NetworkControlAction.suspend,
            self.request(),
            self.db,
        )

        self.assertEqual(command.id, repeated.id)
        self.assertEqual(command.status, NetworkCommandStatus.simulated)
        self.assertEqual(command.attempts, 1)
        self.assertTrue(command.desired_blocked)
        self.assertFalse(command.changed_router)
        self.assertFalse(command.result_details["verified"])

    def test_idempotency_key_cannot_be_reused_for_another_action(self) -> None:
        control_service_network(
            self.service.id,
            NetworkControlAction.suspend,
            self.request(),
            self.db,
        )
        with self.assertRaises(HTTPException) as context:
            control_service_network(
                self.service.id,
                NetworkControlAction.reconcile,
                self.request(),
                self.db,
            )
        self.assertEqual(context.exception.status_code, 409)

    def test_live_request_fails_closed_when_router_is_disabled(self) -> None:
        command = control_service_network(
            self.service.id,
            NetworkControlAction.suspend,
            self.request("mikrotik-live-001", dry_run=False),
            self.db,
        )
        self.assertEqual(command.status, NetworkCommandStatus.failed)
        self.assertEqual(command.attempts, 1)
        self.assertEqual(command.error_message, "Router integration is disabled")
        self.assertFalse(command.result_details["verified"])

    def test_verified_router_result_marks_command_successful(self) -> None:
        stored_router = self.db.get(MikrotikRouter, self.router.id)
        stored_router.enabled = True
        self.db.commit()
        result = RouterExecutionResult(
            blocked=True,
            changed=True,
            entry_count=1,
        )
        with patch(
            "app.api.v1.endpoints.mikrotik.RouterOSRestClient.set_blocked",
            return_value=result,
        ):
            with patch.dict(
                os.environ,
                {
                    "MIKROTIK_PRINCIPAL_USERNAME": "aether",
                    "MIKROTIK_PRINCIPAL_PASSWORD": "secret",
                },
                clear=False,
            ):
                command = control_service_network(
                    self.service.id,
                    NetworkControlAction.suspend,
                    self.request("mikrotik-live-002", dry_run=False),
                    self.db,
                )

        self.assertEqual(command.status, NetworkCommandStatus.succeeded)
        self.assertTrue(command.changed_router)
        self.assertIsNotNone(command.verified_at)
        self.assertTrue(command.result_details["verified"])

    def test_failed_command_can_be_retried_without_losing_audit(self) -> None:
        command = control_service_network(
            self.service.id,
            NetworkControlAction.suspend,
            self.request("mikrotik-retry-001", dry_run=False),
            self.db,
        )
        self.assertEqual(command.status, NetworkCommandStatus.failed)
        result = RouterExecutionResult(
            blocked=True,
            changed=False,
            entry_count=1,
        )
        stored_router = self.db.get(MikrotikRouter, self.router.id)
        stored_router.enabled = True
        self.db.commit()
        with patch(
            "app.api.v1.endpoints.mikrotik.RouterOSRestClient.set_blocked",
            return_value=result,
        ):
            with patch.dict(
                os.environ,
                {
                    "MIKROTIK_PRINCIPAL_USERNAME": "aether",
                    "MIKROTIK_PRINCIPAL_PASSWORD": "secret",
                },
                clear=False,
            ):
                retried = retry_network_command(
                    command.id,
                    NetworkControlRetry(
                        requested_by="Supervisor de red",
                        dry_run=False,
                    ),
                    self.db,
                )

        self.assertEqual(retried.id, command.id)
        self.assertEqual(retried.status, NetworkCommandStatus.succeeded)
        self.assertEqual(retried.attempts, 2)
        self.assertEqual(retried.requested_by, "Supervisor de red")

    def test_reconcile_uses_commercial_state_as_source_of_truth(self) -> None:
        self.service.status = ServiceStatus.suspended
        self.db.commit()
        command = control_service_network(
            self.service.id,
            NetworkControlAction.reconcile,
            self.request("mikrotik-reconcile-001"),
            self.db,
        )
        self.assertTrue(command.desired_blocked)

    def test_retry_rejects_an_obsolete_network_assignment(self) -> None:
        command = control_service_network(
            self.service.id,
            NetworkControlAction.suspend,
            self.request("mikrotik-stale-001", dry_run=False),
            self.db,
        )
        command_assignment = command.network_assignment_id
        assignment = self.db.get(NetworkAssignment, command_assignment)
        assignment.ended_at = datetime.now(UTC)
        self.db.commit()

        with self.assertRaises(HTTPException) as context:
            retry_network_command(
                command.id,
                NetworkControlRetry(
                    requested_by="Supervisor de red",
                    dry_run=True,
                ),
                self.db,
            )
        self.assertEqual(context.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
