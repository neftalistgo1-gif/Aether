import os
import unittest
from datetime import UTC, date, datetime, timedelta
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
    inspect_service_network,
    list_network_inspections,
    retry_network_command,
    update_router,
)
from app.api.v1.endpoints.service_operations import (
    coordinate_cancellation,
    coordinate_network_release,
    coordinate_reactivation,
    coordinate_suspension,
    create_cancellation,
)
from app.api.v1.endpoints.equipment_recovery import (
    complete_equipment_recovery,
    create_equipment_recovery,
)
from app.api.v1.endpoints.payment_agreements import (
    create_payment_agreement,
)
from app.api.v1.endpoints.network_assignments import (
    create_network_assignment,
    get_current_network_assignment,
)
from app.api.v1.endpoints.services import create_service
from app.db.base import Base
from app.integrations.mikrotik import RouterExecutionResult
from app.models.customer import Customer
from app.models.charge import Charge, ChargeStatus, ChargeType
from app.models.mikrotik import (
    MikrotikRouter,
    NetworkCommandStatus,
    NetworkControlAction,
    NetworkInspectionStatus,
)
from app.models.network_assignment import NetworkAssignment
from app.models.notification import (
    CustomerNotification,
    NotificationChannel,
    NotificationPurpose,
    NotificationStatus,
)
from app.models.service import ServiceStatus
from app.models.service_operations import CancellationStatus
from app.schemas.mikrotik import (
    MikrotikRouterCreate,
    MikrotikRouterUpdate,
    NetworkControlRequest,
    NetworkControlRetry,
    NetworkInspectionRequest,
)
from app.schemas.service_operations import (
    CancellationCreate,
    CoordinatedCancellationCreate,
    CoordinatedNetworkReleaseCreate,
    CoordinatedReactivationCreate,
    CoordinatedSuspensionCreate,
)
from app.schemas.equipment_recovery import (
    EquipmentRecoveryComplete,
    EquipmentRecoveryCreate,
)
from app.schemas.payment_agreement import PaymentAgreementCreate
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
        self.db.add(
            Charge(
                customer_id=customer.id,
                service_id=self.service.id,
                charge_type=ChargeType.monthly,
                description="Mensualidad vencida",
                amount=Decimal("600.00"),
                outstanding_balance=Decimal("600.00"),
                due_date=date.today() - timedelta(days=10),
                billing_period=date.today().replace(day=1),
                status=ChargeStatus.pending,
                generated_by="Proceso mensual",
            )
        )
        self.notification = CustomerNotification(
            customer_id=customer.id,
            service_id=self.service.id,
            channel=NotificationChannel.whatsapp,
            purpose=NotificationPurpose.suspension_warning,
            status=NotificationStatus.delivered,
            recipient=customer.phones[0],
            message_summary="Aviso previo de suspensión por adeudo",
            provider_reference="wa-message-amr901",
            occurred_at=datetime.now(UTC),
            recorded_by="Atención a clientes",
        )
        self.db.add(self.notification)
        self.db.commit()
        self.payment_agreement = create_payment_agreement(
            self.service.id,
            PaymentAgreementCreate(
                terms="Convenio autorizado para reactivación",
                authorized_by="Atencion a clientes",
                evidence_reference="private/agreements/amr901",
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
        preflight_command_id=None,
        network_inspection_id=None,
    ) -> NetworkControlRequest:
        return NetworkControlRequest(
            requested_by="Operador de red",
            idempotency_key=key,
            dry_run=dry_run,
            preflight_command_id=preflight_command_id,
            network_inspection_id=network_inspection_id,
        )

    def live_request(
        self,
        action: NetworkControlAction,
        key: str,
        network_inspection_id=None,
    ) -> NetworkControlRequest:
        preflight = control_service_network(
            self.service.id,
            action,
            self.request(
                f"{key}-preflight",
                network_inspection_id=network_inspection_id,
            ),
            self.db,
        )
        return self.request(
            key,
            dry_run=False,
            preflight_command_id=preflight.id,
            network_inspection_id=network_inspection_id,
        )

    def inspect_network(
        self,
        key: str,
        *,
        observed_blocked: bool,
        entry_count: int | None = None,
    ):
        stored_router = self.db.get(MikrotikRouter, self.router.id)
        stored_router.enabled = True
        self.db.commit()
        with patch(
            "app.api.v1.endpoints.mikrotik.RouterOSRestClient.inspect_blocked",
            return_value=RouterExecutionResult(
                blocked=observed_blocked,
                changed=False,
                entry_count=(
                    entry_count
                    if entry_count is not None
                    else int(observed_blocked)
                ),
            ),
        ):
            with patch.dict(
                os.environ,
                {
                    "MIKROTIK_PRINCIPAL_USERNAME": "aether",
                    "MIKROTIK_PRINCIPAL_PASSWORD": "secret",
                },
                clear=False,
            ):
                return inspect_service_network(
                    self.service.id,
                    NetworkInspectionRequest(
                        requested_by="Supervisor de red",
                        idempotency_key=key,
                    ),
                    self.db,
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

    def test_live_request_requires_a_preflight(self) -> None:
        with self.assertRaises(ValidationError):
            self.request(
                "mikrotik-live-without-preflight",
                dry_run=False,
            )

    def test_live_request_rejects_an_expired_preflight(self) -> None:
        preflight = control_service_network(
            self.service.id,
            NetworkControlAction.suspend,
            self.request("mikrotik-expired-preflight"),
            self.db,
        )
        preflight.requested_at = datetime.now(UTC) - timedelta(minutes=16)
        self.db.commit()

        with self.assertRaises(HTTPException) as context:
            control_service_network(
                self.service.id,
                NetworkControlAction.suspend,
                self.request(
                    "mikrotik-expired-live",
                    dry_run=False,
                    preflight_command_id=preflight.id,
                ),
                self.db,
            )
        self.assertEqual(context.exception.status_code, 409)

    def test_preflight_can_authorize_only_one_live_command(self) -> None:
        preflight = control_service_network(
            self.service.id,
            NetworkControlAction.suspend,
            self.request("mikrotik-single-use-preflight"),
            self.db,
        )
        first = control_service_network(
            self.service.id,
            NetworkControlAction.suspend,
            self.request(
                "mikrotik-single-use-live-1",
                dry_run=False,
                preflight_command_id=preflight.id,
            ),
            self.db,
        )
        self.assertEqual(first.preflight_command_id, preflight.id)

        with self.assertRaises(HTTPException) as context:
            control_service_network(
                self.service.id,
                NetworkControlAction.suspend,
                self.request(
                    "mikrotik-single-use-live-2",
                    dry_run=False,
                    preflight_command_id=preflight.id,
                ),
                self.db,
            )
        self.assertEqual(context.exception.status_code, 409)

    def test_preflight_must_match_the_requested_action(self) -> None:
        inspection = self.inspect_network(
            "mikrotik-action-inspection",
            observed_blocked=True,
        )
        preflight = control_service_network(
            self.service.id,
            NetworkControlAction.suspend,
            self.request("mikrotik-action-preflight"),
            self.db,
        )
        with self.assertRaises(HTTPException) as context:
            control_service_network(
                self.service.id,
                NetworkControlAction.reconcile,
                self.request(
                    "mikrotik-action-live",
                    dry_run=False,
                    preflight_command_id=preflight.id,
                    network_inspection_id=inspection.id,
                ),
                self.db,
            )
        self.assertEqual(context.exception.status_code, 409)

    def test_simulated_command_cannot_be_promoted_by_retry(self) -> None:
        command = control_service_network(
            self.service.id,
            NetworkControlAction.suspend,
            self.request("mikrotik-promote-preflight"),
            self.db,
        )
        with self.assertRaises(HTTPException) as context:
            retry_network_command(
                command.id,
                NetworkControlRetry(
                    requested_by="Supervisor de red",
                    dry_run=False,
                ),
                self.db,
            )
        self.assertEqual(context.exception.status_code, 409)

    def test_live_request_fails_closed_when_router_is_disabled(self) -> None:
        command = control_service_network(
            self.service.id,
            NetworkControlAction.suspend,
            self.live_request(
                NetworkControlAction.suspend,
                "mikrotik-live-001",
            ),
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
                    self.live_request(
                        NetworkControlAction.suspend,
                        "mikrotik-live-002",
                    ),
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
            self.live_request(
                NetworkControlAction.suspend,
                "mikrotik-retry-001",
            ),
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
        inspection = self.inspect_network(
            "mikrotik-reconcile-state-inspection",
            observed_blocked=False,
        )
        command = control_service_network(
            self.service.id,
            NetworkControlAction.reconcile,
            self.request(
                "mikrotik-reconcile-001",
                network_inspection_id=inspection.id,
            ),
            self.db,
        )
        self.assertTrue(command.desired_blocked)
        self.assertEqual(command.network_inspection_id, inspection.id)

    def test_read_only_inspection_reports_matching_network_state(
        self,
    ) -> None:
        inspection = self.inspect_network(
            "mikrotik-inspection-matching",
            observed_blocked=False,
        )
        repeated = inspect_service_network(
            self.service.id,
            NetworkInspectionRequest(
                requested_by="Otro operador",
                idempotency_key="mikrotik-inspection-matching",
            ),
            self.db,
        )
        history = list_network_inspections(self.service.id, self.db)

        self.assertEqual(
            inspection.status,
            NetworkInspectionStatus.succeeded,
        )
        self.assertFalse(inspection.expected_blocked)
        self.assertFalse(inspection.observed_blocked)
        self.assertTrue(inspection.matches_expected)
        self.assertEqual(inspection.entry_count, 0)
        self.assertEqual(repeated.id, inspection.id)
        self.assertEqual([item.id for item in history], [inspection.id])

    def test_failed_inspection_is_preserved_without_observed_state(
        self,
    ) -> None:
        inspection = inspect_service_network(
            self.service.id,
            NetworkInspectionRequest(
                requested_by="Supervisor de red",
                idempotency_key="mikrotik-inspection-disabled",
            ),
            self.db,
        )

        self.assertEqual(
            inspection.status,
            NetworkInspectionStatus.failed,
        )
        self.assertIsNone(inspection.observed_blocked)
        self.assertIsNone(inspection.matches_expected)
        self.assertEqual(
            inspection.error_message,
            "Router integration is disabled",
        )

    def test_matching_inspection_cannot_authorize_reconciliation(
        self,
    ) -> None:
        inspection = self.inspect_network(
            "mikrotik-inspection-no-drift",
            observed_blocked=False,
        )

        with self.assertRaises(HTTPException) as context:
            control_service_network(
                self.service.id,
                NetworkControlAction.reconcile,
                self.request(
                    "mikrotik-reconcile-unnecessary",
                    network_inspection_id=inspection.id,
                ),
                self.db,
            )

        self.assertEqual(context.exception.status_code, 409)

    def test_expired_inspection_cannot_authorize_reconciliation(
        self,
    ) -> None:
        inspection = self.inspect_network(
            "mikrotik-inspection-expired",
            observed_blocked=True,
        )
        inspection.completed_at = datetime.now(UTC) - timedelta(minutes=6)
        self.db.commit()

        with self.assertRaises(HTTPException) as context:
            control_service_network(
                self.service.id,
                NetworkControlAction.reconcile,
                self.request(
                    "mikrotik-reconcile-expired-inspection",
                    network_inspection_id=inspection.id,
                ),
                self.db,
            )

        self.assertEqual(context.exception.status_code, 409)

    def test_inspection_authorizes_only_one_reconciliation_preflight(
        self,
    ) -> None:
        inspection = self.inspect_network(
            "mikrotik-inspection-single-preflight",
            observed_blocked=True,
        )
        control_service_network(
            self.service.id,
            NetworkControlAction.reconcile,
            self.request(
                "mikrotik-reconcile-first-preflight",
                network_inspection_id=inspection.id,
            ),
            self.db,
        )

        with self.assertRaises(HTTPException) as context:
            control_service_network(
                self.service.id,
                NetworkControlAction.reconcile,
                self.request(
                    "mikrotik-reconcile-second-preflight",
                    network_inspection_id=inspection.id,
                ),
                self.db,
            )

        self.assertEqual(context.exception.status_code, 409)

    def test_reconciliation_rechecks_commercial_state_after_preflight(
        self,
    ) -> None:
        inspection = self.inspect_network(
            "mikrotik-inspection-state-change",
            observed_blocked=True,
        )
        preflight = control_service_network(
            self.service.id,
            NetworkControlAction.reconcile,
            self.request(
                "mikrotik-reconcile-state-change-preflight",
                network_inspection_id=inspection.id,
            ),
            self.db,
        )
        self.service.status = ServiceStatus.suspended
        self.db.commit()

        with self.assertRaises(HTTPException) as context:
            control_service_network(
                self.service.id,
                NetworkControlAction.reconcile,
                self.request(
                    "mikrotik-reconcile-state-change-live",
                    dry_run=False,
                    preflight_command_id=preflight.id,
                    network_inspection_id=inspection.id,
                ),
                self.db,
            )

        self.assertEqual(context.exception.status_code, 409)

    def test_reconcile_rejects_pending_and_cancelled_services(self) -> None:
        for service_status in (
            ServiceStatus.pending,
            ServiceStatus.cancelled,
        ):
            with self.subTest(service_status=service_status):
                self.service.status = service_status
                self.db.commit()
                with self.assertRaises(HTTPException) as context:
                    control_service_network(
                        self.service.id,
                        NetworkControlAction.reconcile,
                        self.request(
                            f"mikrotik-reconcile-{service_status.value}"
                        ),
                        self.db,
                    )
                self.assertEqual(context.exception.status_code, 409)

    def test_live_reconcile_verifies_router_without_commercial_change(
        self,
    ) -> None:
        inspection = self.inspect_network(
            "mikrotik-reconcile-live-inspection",
            observed_blocked=True,
        )
        live_request = self.live_request(
            NetworkControlAction.reconcile,
            "mikrotik-reconcile-live",
            network_inspection_id=inspection.id,
        )
        stored_router = self.db.get(MikrotikRouter, self.router.id)
        stored_router.enabled = True
        self.db.commit()

        with patch(
            "app.api.v1.endpoints.mikrotik.RouterOSRestClient.set_blocked",
            return_value=RouterExecutionResult(
                blocked=False,
                changed=True,
                entry_count=0,
            ),
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
                    NetworkControlAction.reconcile,
                    live_request,
                    self.db,
                )

        self.assertEqual(command.status, NetworkCommandStatus.succeeded)
        self.assertFalse(command.desired_blocked)
        self.assertTrue(command.changed_router)
        self.assertIsNotNone(command.verified_at)
        self.db.refresh(self.service)
        self.assertEqual(self.service.status, ServiceStatus.active)

    def test_retry_rejects_an_obsolete_network_assignment(self) -> None:
        command = control_service_network(
            self.service.id,
            NetworkControlAction.suspend,
            self.live_request(
                NetworkControlAction.suspend,
                "mikrotik-stale-001",
            ),
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
                    dry_run=False,
                ),
                self.db,
            )
        self.assertEqual(context.exception.status_code, 409)

    def coordinated_suspension(
        self,
        key: str,
        dry_run: bool,
        preflight_command_id=None,
    ) -> CoordinatedSuspensionCreate:
        return CoordinatedSuspensionCreate(
            scheduled_for=date.today(),
            reason="Mensualidad vencida",
            debt_amount=Decimal("600.00"),
            grace_period_elapsed=True,
            extension_checked=True,
            has_active_extension=False,
            notification_id=self.notification.id,
            performed_by="Tecnico de red",
            idempotency_key=key,
            dry_run=dry_run,
            preflight_command_id=preflight_command_id,
        )

    def coordinated_live_suspension(
        self,
        key: str,
    ) -> CoordinatedSuspensionCreate:
        preflight = coordinate_suspension(
            self.service.id,
            self.coordinated_suspension(
                f"{key}-preflight",
                dry_run=True,
            ),
            self.db,
        )
        return self.coordinated_suspension(
            key,
            dry_run=False,
            preflight_command_id=preflight.command.id,
        )

    def test_coordinated_dry_run_does_not_suspend_service(self) -> None:
        result = coordinate_suspension(
            self.service.id,
            self.coordinated_suspension(
                "coordinated-dry-run-001",
                dry_run=True,
            ),
            self.db,
        )
        self.assertEqual(
            result.command.status,
            NetworkCommandStatus.simulated,
        )
        self.assertIsNone(result.suspension)
        self.db.refresh(self.service)
        self.assertEqual(self.service.status, ServiceStatus.active)

    def test_coordinated_idempotency_key_cannot_change_execution_mode(
        self,
    ) -> None:
        coordinate_suspension(
            self.service.id,
            self.coordinated_suspension(
                "coordinated-fixed-mode",
                dry_run=True,
            ),
            self.db,
        )
        second_preflight = coordinate_suspension(
            self.service.id,
            self.coordinated_suspension(
                "coordinated-second-preflight",
                dry_run=True,
            ),
            self.db,
        )
        with self.assertRaises(HTTPException) as context:
            coordinate_suspension(
                self.service.id,
                self.coordinated_suspension(
                    "coordinated-fixed-mode",
                    dry_run=False,
                    preflight_command_id=second_preflight.command.id,
                ),
                self.db,
            )
        self.assertEqual(context.exception.status_code, 409)

    def test_verified_command_and_commercial_suspension_are_linked(self) -> None:
        stored_router = self.db.get(MikrotikRouter, self.router.id)
        stored_router.enabled = True
        self.db.commit()
        with patch(
            "app.api.v1.endpoints.mikrotik.RouterOSRestClient.set_blocked",
            return_value=RouterExecutionResult(
                blocked=True,
                changed=True,
                entry_count=1,
            ),
        ):
            with patch.dict(
                os.environ,
                {
                    "MIKROTIK_PRINCIPAL_USERNAME": "aether",
                    "MIKROTIK_PRINCIPAL_PASSWORD": "secret",
                },
                clear=False,
            ):
                result = coordinate_suspension(
                    self.service.id,
                    self.coordinated_live_suspension(
                        "coordinated-live-001",
                    ),
                    self.db,
                )

        self.assertEqual(
            result.command.status,
            NetworkCommandStatus.succeeded,
        )
        self.assertIsNotNone(result.suspension)
        self.assertEqual(
            result.suspension.network_command_id,
            result.command.id,
        )
        self.db.refresh(self.service)
        self.assertEqual(self.service.status, ServiceStatus.suspended)

    def test_coordinator_rejects_success_for_an_obsolete_ip(self) -> None:
        stored_router = self.db.get(MikrotikRouter, self.router.id)
        stored_router.enabled = True
        self.db.commit()
        key = "coordinated-obsolete-001"
        with patch(
            "app.api.v1.endpoints.mikrotik.RouterOSRestClient.set_blocked",
            return_value=RouterExecutionResult(
                blocked=True,
                changed=True,
                entry_count=1,
            ),
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
                    self.live_request(
                        NetworkControlAction.suspend,
                        key,
                    ),
                    self.db,
                )
        assignment = self.db.get(
            NetworkAssignment,
            command.network_assignment_id,
        )
        assignment.ended_at = datetime.now(UTC)
        self.db.commit()

        with self.assertRaises(HTTPException) as context:
            coordinate_suspension(
                self.service.id,
                self.coordinated_suspension(
                    key,
                    dry_run=False,
                    preflight_command_id=command.preflight_command_id,
                ),
                self.db,
            )
        self.assertEqual(context.exception.status_code, 409)
        self.db.refresh(self.service)
        self.assertEqual(self.service.status, ServiceStatus.active)

    def test_failed_command_can_finish_same_coordinated_operation(self) -> None:
        payload = self.coordinated_live_suspension(
            "coordinated-retry-001",
        )
        failed = coordinate_suspension(
            self.service.id,
            payload,
            self.db,
        )
        self.assertEqual(
            failed.command.status,
            NetworkCommandStatus.failed,
        )
        self.assertIsNone(failed.suspension)

        stored_router = self.db.get(MikrotikRouter, self.router.id)
        stored_router.enabled = True
        self.db.commit()
        with patch(
            "app.api.v1.endpoints.mikrotik.RouterOSRestClient.set_blocked",
            return_value=RouterExecutionResult(
                blocked=True,
                changed=False,
                entry_count=1,
            ),
        ):
            with patch.dict(
                os.environ,
                {
                    "MIKROTIK_PRINCIPAL_USERNAME": "aether",
                    "MIKROTIK_PRINCIPAL_PASSWORD": "secret",
                },
                clear=False,
            ):
                retry_network_command(
                    failed.command.id,
                    NetworkControlRetry(
                        requested_by="Supervisor de red",
                        dry_run=False,
                    ),
                    self.db,
                )

        finished = coordinate_suspension(
            self.service.id,
            payload,
            self.db,
        )
        repeated = coordinate_suspension(
            self.service.id,
            payload,
            self.db,
        )
        self.assertIsNotNone(finished.suspension)
        self.assertEqual(finished.suspension.id, repeated.suspension.id)
        self.assertEqual(
            finished.suspension.network_command_id,
            failed.command.id,
        )

    def test_coordinated_reactivation_removes_block_before_activation(
        self,
    ) -> None:
        stored_router = self.db.get(MikrotikRouter, self.router.id)
        stored_router.enabled = True
        self.db.commit()
        credentials = {
            "MIKROTIK_PRINCIPAL_USERNAME": "aether",
            "MIKROTIK_PRINCIPAL_PASSWORD": "secret",
        }
        with patch.dict(os.environ, credentials, clear=False):
            with patch(
                "app.api.v1.endpoints.mikrotik.RouterOSRestClient.set_blocked",
                return_value=RouterExecutionResult(
                    blocked=True,
                    changed=True,
                    entry_count=1,
                ),
            ):
                coordinate_suspension(
                    self.service.id,
                    self.coordinated_live_suspension(
                        "coordinated-cycle-suspend",
                    ),
                    self.db,
                )
            with patch(
                "app.api.v1.endpoints.mikrotik.RouterOSRestClient.set_blocked",
                return_value=RouterExecutionResult(
                    blocked=False,
                    changed=True,
                    entry_count=0,
                ),
            ):
                preflight = coordinate_reactivation(
                    self.service.id,
                    CoordinatedReactivationCreate(
                        reason="Pago verificado",
                        authorized_by="Atencion a clientes",
                        performed_by="Tecnico de red",
                        debt_amount=Decimal("600.00"),
                        payment_agreement_id=self.payment_agreement.id,
                        idempotency_key=(
                            "coordinated-cycle-reactivate-preflight"
                        ),
                        dry_run=True,
                    ),
                    self.db,
                )
                result = coordinate_reactivation(
                    self.service.id,
                    CoordinatedReactivationCreate(
                        reason="Pago verificado",
                        authorized_by="Atencion a clientes",
                        performed_by="Tecnico de red",
                        debt_amount=Decimal("600.00"),
                        payment_agreement_id=self.payment_agreement.id,
                        idempotency_key="coordinated-cycle-reactivate",
                        dry_run=False,
                        preflight_command_id=preflight.command.id,
                    ),
                    self.db,
                )

        self.assertEqual(
            result.command.status,
            NetworkCommandStatus.succeeded,
        )
        self.assertIsNotNone(result.reactivation)
        self.assertEqual(
            result.reactivation.network_command_id,
            result.command.id,
        )
        self.db.refresh(self.service)
        self.assertEqual(self.service.status, ServiceStatus.active)

    def cancellation_request(self):
        return create_cancellation(
            self.service.id,
            CancellationCreate(
                requester_customer_id=self.service.current_customer_id,
                effective_date=date.today(),
                reason="Baja definitiva solicitada por el titular",
                registered_by="Atencion a clientes",
                equipment_pending_notes="Recuperar equipo instalado",
            ),
            self.db,
        )

    def test_coordinated_cancellation_requires_verified_shutdown(
        self,
    ) -> None:
        cancellation = self.cancellation_request()
        preflight = coordinate_cancellation(
            self.service.id,
            CoordinatedCancellationCreate(
                performed_by="Tecnico de red",
                idempotency_key="cancel-network-preflight",
                dry_run=True,
            ),
            self.db,
        )
        self.assertEqual(
            preflight.command.status,
            NetworkCommandStatus.simulated,
        )
        self.assertEqual(
            cancellation.status,
            CancellationStatus.scheduled,
        )
        self.db.refresh(self.service)
        self.assertEqual(self.service.status, ServiceStatus.active)

        stored_router = self.db.get(MikrotikRouter, self.router.id)
        stored_router.enabled = True
        self.db.commit()
        with patch(
            "app.api.v1.endpoints.mikrotik.RouterOSRestClient.set_blocked",
            return_value=RouterExecutionResult(
                blocked=True,
                changed=True,
                entry_count=1,
            ),
        ):
            with patch.dict(
                os.environ,
                {
                    "MIKROTIK_PRINCIPAL_USERNAME": "aether",
                    "MIKROTIK_PRINCIPAL_PASSWORD": "secret",
                },
                clear=False,
            ):
                live_execution = CoordinatedCancellationCreate(
                    performed_by="Tecnico de red",
                    idempotency_key="cancel-network-live",
                    dry_run=False,
                    preflight_command_id=preflight.command.id,
                )
                result = coordinate_cancellation(
                    self.service.id,
                    live_execution,
                    self.db,
                )
                repeated = coordinate_cancellation(
                    self.service.id,
                    live_execution,
                    self.db,
                )

        self.assertEqual(
            result.command.status,
            NetworkCommandStatus.succeeded,
        )
        self.assertEqual(
            result.cancellation.status,
            CancellationStatus.executed,
        )
        self.assertEqual(
            result.cancellation.network_command_id,
            result.command.id,
        )
        self.assertEqual(repeated.command.id, result.command.id)
        self.assertEqual(
            repeated.cancellation.id,
            result.cancellation.id,
        )
        assignment = self.db.get(
            NetworkAssignment,
            result.command.network_assignment_id,
        )
        self.assertIsNone(assignment.ended_at)
        self.db.refresh(self.service)
        self.assertEqual(self.service.status, ServiceStatus.cancelled)

    def test_failed_network_shutdown_does_not_execute_cancellation(
        self,
    ) -> None:
        cancellation = self.cancellation_request()
        preflight = coordinate_cancellation(
            self.service.id,
            CoordinatedCancellationCreate(
                performed_by="Tecnico de red",
                idempotency_key="cancel-failed-preflight",
                dry_run=True,
            ),
            self.db,
        )
        result = coordinate_cancellation(
            self.service.id,
            CoordinatedCancellationCreate(
                performed_by="Tecnico de red",
                idempotency_key="cancel-failed-live",
                dry_run=False,
                preflight_command_id=preflight.command.id,
            ),
            self.db,
        )

        self.assertEqual(
            result.command.status,
            NetworkCommandStatus.failed,
        )
        self.assertEqual(
            cancellation.status,
            CancellationStatus.scheduled,
        )
        self.db.refresh(self.service)
        self.assertEqual(self.service.status, ServiceStatus.active)

    def execute_verified_cancellation(self, key: str):
        self.cancellation_request()
        preflight = coordinate_cancellation(
            self.service.id,
            CoordinatedCancellationCreate(
                performed_by="Tecnico de red",
                idempotency_key=f"{key}-shutdown-preflight",
                dry_run=True,
            ),
            self.db,
        )
        stored_router = self.db.get(MikrotikRouter, self.router.id)
        stored_router.enabled = True
        self.db.commit()
        with patch(
            "app.api.v1.endpoints.mikrotik.RouterOSRestClient.set_blocked",
            return_value=RouterExecutionResult(
                blocked=True,
                changed=True,
                entry_count=1,
            ),
        ):
            with patch.dict(
                os.environ,
                {
                    "MIKROTIK_PRINCIPAL_USERNAME": "aether",
                    "MIKROTIK_PRINCIPAL_PASSWORD": "secret",
                },
                clear=False,
            ):
                return coordinate_cancellation(
                    self.service.id,
                    CoordinatedCancellationCreate(
                        performed_by="Tecnico de red",
                        idempotency_key=f"{key}-shutdown-live",
                        dry_run=False,
                        preflight_command_id=preflight.command.id,
                    ),
                    self.db,
                )

    def complete_cancellation_recovery(self) -> None:
        create_equipment_recovery(
            self.service.id,
            EquipmentRecoveryCreate(
                scheduled_for=date.today(),
                assigned_technician="Tecnico instalador",
                expected_equipment=["Antena", "Modem"],
            ),
            self.db,
        )
        complete_equipment_recovery(
            self.service.id,
            EquipmentRecoveryComplete(
                performed_by="Tecnico instalador",
                recovered_equipment=["Antena", "Modem"],
                missing_equipment=[],
                condition_notes="Instalacion retirada y energia desconectada",
                evidence_references=[
                    "private/recovery/disconnected-installation.jpg"
                ],
                receipt_reference="REC-CANCEL-001",
            ),
            self.db,
        )

    def network_release_payload(
        self,
        key: str,
        *,
        dry_run: bool,
        preflight_command_id=None,
    ) -> CoordinatedNetworkReleaseCreate:
        return CoordinatedNetworkReleaseCreate(
            performed_by="Tecnico de red",
            physical_disconnect_confirmed=True,
            disconnect_evidence_reference=(
                "private/network/disconnected-installation.jpg"
            ),
            idempotency_key=key,
            dry_run=dry_run,
            preflight_command_id=preflight_command_id,
        )

    def test_network_release_requires_disconnect_confirmation(self) -> None:
        with self.assertRaises(ValidationError):
            CoordinatedNetworkReleaseCreate(
                performed_by="Tecnico de red",
                physical_disconnect_confirmed=False,
                disconnect_evidence_reference=(
                    "private/network/disconnected-installation.jpg"
                ),
                idempotency_key="release-unconfirmed",
                dry_run=True,
            )

    def test_network_release_requires_final_equipment_recovery(self) -> None:
        self.execute_verified_cancellation("release-early")

        with self.assertRaises(HTTPException) as context:
            coordinate_network_release(
                self.service.id,
                self.network_release_payload(
                    "release-early-preflight",
                    dry_run=True,
                ),
                self.db,
            )

        self.assertEqual(context.exception.status_code, 409)
        self.assertIsNotNone(
            get_current_network_assignment(self.service.id, self.db)
        )

    def test_verified_network_release_closes_reserved_assignment(
        self,
    ) -> None:
        shutdown = self.execute_verified_cancellation("release-success")
        self.complete_cancellation_recovery()
        preflight = coordinate_network_release(
            self.service.id,
            self.network_release_payload(
                "release-success-preflight",
                dry_run=True,
            ),
            self.db,
        )
        self.assertEqual(
            preflight.command.status,
            NetworkCommandStatus.simulated,
        )
        assignment = self.db.get(
            NetworkAssignment,
            shutdown.command.network_assignment_id,
        )
        self.assertIsNone(assignment.ended_at)

        with patch(
            "app.api.v1.endpoints.mikrotik.RouterOSRestClient.set_blocked",
            return_value=RouterExecutionResult(
                blocked=False,
                changed=True,
                entry_count=0,
            ),
        ):
            with patch.dict(
                os.environ,
                {
                    "MIKROTIK_PRINCIPAL_USERNAME": "aether",
                    "MIKROTIK_PRINCIPAL_PASSWORD": "secret",
                },
                clear=False,
            ):
                live_release = self.network_release_payload(
                    "release-success-live",
                    dry_run=False,
                    preflight_command_id=preflight.command.id,
                )
                result = coordinate_network_release(
                    self.service.id,
                    live_release,
                    self.db,
                )
                repeated = coordinate_network_release(
                    self.service.id,
                    live_release,
                    self.db,
                )

        self.assertEqual(
            result.command.status,
            NetworkCommandStatus.succeeded,
        )
        self.assertEqual(
            result.cancellation.network_release_command_id,
            result.command.id,
        )
        self.assertTrue(
            result.cancellation.has_network_release_evidence
        )
        self.assertNotIn(
            "network_release_evidence_reference",
            result.cancellation.model_dump(),
        )
        self.assertIsNotNone(result.cancellation.network_released_at)
        self.assertEqual(repeated.command.id, result.command.id)
        self.db.refresh(assignment)
        self.assertIsNotNone(assignment.ended_at)
        with self.assertRaises(HTTPException) as current:
            get_current_network_assignment(self.service.id, self.db)
        self.assertEqual(current.exception.status_code, 404)

    def test_failed_network_release_keeps_assignment_reserved(
        self,
    ) -> None:
        shutdown = self.execute_verified_cancellation("release-failed")
        self.complete_cancellation_recovery()
        preflight = coordinate_network_release(
            self.service.id,
            self.network_release_payload(
                "release-failed-preflight",
                dry_run=True,
            ),
            self.db,
        )
        stored_router = self.db.get(MikrotikRouter, self.router.id)
        stored_router.enabled = False
        self.db.commit()
        result = coordinate_network_release(
            self.service.id,
            self.network_release_payload(
                "release-failed-live",
                dry_run=False,
                preflight_command_id=preflight.command.id,
            ),
            self.db,
        )

        assignment = self.db.get(
            NetworkAssignment,
            shutdown.command.network_assignment_id,
        )
        self.assertEqual(
            result.command.status,
            NetworkCommandStatus.failed,
        )
        self.assertIsNone(
            result.cancellation.network_release_command_id
        )
        self.assertIsNone(assignment.ended_at)


if __name__ == "__main__":
    unittest.main()
