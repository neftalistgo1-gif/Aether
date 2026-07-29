import unittest
from datetime import UTC, date, datetime, timedelta
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from app.api.dependencies.auth import (
    capability_for_operation,
    require_administrator,
    require_authenticated_user,
    require_authorized_user,
)
from app.api.v1.endpoints.auth import (
    bootstrap_administrator,
    create_operator_user,
    deactivate_operator_user,
    login,
    logout,
    replace_operator_permissions,
)
from app.api.v1.endpoints.plans import create_plan
from app.core.security import hash_password, verify_password
from app.db.base import Base
from app.main import app
from app.models.audit import AuditEvent
from app.models.auth import AuthSession, Capability, OperatorUser, UserRole
from app.schemas.auth import (
    BootstrapAdminCreate,
    LoginRequest,
    UserCreate,
    UserDeactivate,
    UserPermissionReplace,
)
from app.schemas.plan import PlanCreate


def build_request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"user-agent", b"aether-test-client")],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
            "scheme": "http",
        }
    )


def build_operation_request(method: str, route_path: str) -> Request:
    class Route:
        path = route_path

    request = build_request()
    request.scope["method"] = method
    request.scope["route"] = Route()
    return request


class AuthenticationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.secret_patch = patch(
            "app.api.v1.endpoints.auth.AETHER_BOOTSTRAP_SECRET",
            "bootstrap-secret-for-tests",
        )
        self.secret_patch.start()

    def tearDown(self) -> None:
        self.secret_patch.stop()
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def bootstrap(self):
        return bootstrap_administrator(
            BootstrapAdminCreate(
                username="admin",
                display_name="Administrador real",
                password="Clave-Segura-Para-Pruebas-123",
            ),
            build_request(),
            "bootstrap-secret-for-tests",
            self.db,
        )

    def authenticate(self, token: str):
        request = build_request()
        dependency = require_authenticated_user(
            request,
            HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials=token,
            ),
            self.db,
        )
        user = next(dependency)
        return dependency, request, user

    def test_password_hash_is_salted_and_verifiable(self) -> None:
        first = hash_password("Una-Clave-Muy-Segura-123")
        second = hash_password("Una-Clave-Muy-Segura-123")
        self.assertNotEqual(first, second)
        self.assertNotIn("Una-Clave-Muy-Segura-123", first)
        self.assertTrue(
            verify_password("Una-Clave-Muy-Segura-123", first)
        )
        self.assertFalse(verify_password("clave-incorrecta", first))

    def test_bootstrap_is_single_use_and_credentials_are_not_stored(self) -> None:
        credentials = self.bootstrap()
        user = self.db.scalar(select(OperatorUser))
        session = self.db.scalar(select(AuthSession))
        self.assertNotEqual(user.password_hash, "Clave-Segura-Para-Pruebas-123")
        self.assertNotEqual(session.token_hash, credentials.access_token)

        with self.assertRaises(HTTPException) as repeated:
            self.bootstrap()
        self.assertEqual(repeated.exception.status_code, 409)
        with self.assertRaises(HTTPException) as missing:
            dependency = require_authenticated_user(
                build_request(),
                None,
                self.db,
            )
            next(dependency)
        self.assertEqual(missing.exception.status_code, 401)

    def test_authenticated_identity_overrides_claimed_audit_actor(self) -> None:
        token = self.bootstrap().access_token
        dependency, _request, user = self.authenticate(token)
        try:
            create_plan(
                PlanCreate(
                    name="Plan autenticado",
                    speed="20 Mbps",
                    monthly_price="500.00",
                    valid_from=date.today(),
                    created_by="Nombre suplantado",
                    reason="Alta inicial autenticada",
                ),
                self.db,
            )
        finally:
            dependency.close()
        event = self.db.scalar(
            select(AuditEvent).where(AuditEvent.action == "plan.created")
        )
        self.assertEqual(event.actor, "Administrador real")
        self.assertEqual(event.actor_user_id, user.id)
        self.assertEqual(event.source_ip, "127.0.0.1")
        self.assertEqual(event.device, "aether-test-client")

    def test_login_logout_and_expiration_invalidate_sessions(self) -> None:
        first_token = self.bootstrap().access_token
        dependency, request, user = self.authenticate(first_token)
        try:
            logout(request, user, self.db)
        finally:
            dependency.close()
        with self.assertRaises(HTTPException) as revoked:
            revoked_dependency = require_authenticated_user(
                build_request(),
                HTTPAuthorizationCredentials(
                    scheme="Bearer",
                    credentials=first_token,
                ),
                self.db,
            )
            next(revoked_dependency)
        self.assertEqual(revoked.exception.status_code, 401)

        with self.assertRaises(HTTPException) as bad_login:
            login(
                LoginRequest(
                    username="admin",
                    password="incorrecta",
                ),
                build_request(),
                self.db,
            )
        self.assertEqual(bad_login.exception.status_code, 401)
        credentials = login(
            LoginRequest(
                username="ADMIN",
                password="Clave-Segura-Para-Pruebas-123",
            ),
            build_request(),
            self.db,
        )
        session = self.db.scalar(
            select(AuthSession)
            .where(AuthSession.revoked_at.is_(None))
            .order_by(AuthSession.created_at.desc())
        )
        session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        self.db.commit()
        with self.assertRaises(HTTPException) as expired:
            expired_dependency = require_authenticated_user(
                build_request(),
                HTTPAuthorizationCredentials(
                    scheme="Bearer",
                    credentials=credentials.access_token,
                ),
                self.db,
            )
            next(expired_dependency)
        self.assertEqual(expired.exception.status_code, 401)

    def test_only_administrator_manages_users_and_deactivation_revokes(self) -> None:
        admin_credentials = self.bootstrap()
        dependency, _request, administrator = self.authenticate(
            admin_credentials.access_token
        )
        try:
            user = create_operator_user(
                UserCreate(
                    username="soporte",
                    display_name="Atencion a clientes",
                    password="Clave-Segura-Soporte-456",
                    role="customer_service",
                ),
                administrator,
                self.db,
            )
        finally:
            dependency.close()
        user_credentials = login(
            LoginRequest(
                username="soporte",
                password="Clave-Segura-Soporte-456",
            ),
            build_request(),
            self.db,
        )
        user_dependency, _request, authenticated_user = self.authenticate(
            user_credentials.access_token
        )
        try:
            with self.assertRaises(HTTPException) as forbidden:
                require_administrator(authenticated_user)
        finally:
            user_dependency.close()
        self.assertEqual(forbidden.exception.status_code, 403)

        admin_dependency, _request, administrator = self.authenticate(
            admin_credentials.access_token
        )
        try:
            deactivated = deactivate_operator_user(
                user.id,
                UserDeactivate(reason="Cuenta de prueba finalizada"),
                administrator,
                self.db,
            )
        finally:
            admin_dependency.close()
        self.assertFalse(deactivated.is_active)
        with self.assertRaises(HTTPException) as rejected:
            rejected_dependency = require_authenticated_user(
                build_request(),
                HTTPAuthorizationCredentials(
                    scheme="Bearer",
                    credentials=user_credentials.access_token,
                ),
                self.db,
            )
            next(rejected_dependency)
        self.assertEqual(rejected.exception.status_code, 401)

    def test_openapi_marks_all_business_operations_as_protected(self) -> None:
        schema = app.openapi()
        for path, operations in schema["paths"].items():
            if not path.startswith("/api/v1/"):
                continue
            if path in {
                "/api/v1/health",
                "/api/v1/auth/bootstrap",
                "/api/v1/auth/login",
            }:
                continue
            for method, operation in operations.items():
                with self.subTest(path=path, method=method):
                    self.assertTrue(operation.get("security"))

    def test_permissions_are_explicit_and_fail_closed(self) -> None:
        admin_credentials = self.bootstrap()
        dependency, _request, administrator = self.authenticate(
            admin_credentials.access_token
        )
        try:
            user = create_operator_user(
                UserCreate(
                    username="consulta",
                    display_name="Consulta de clientes",
                    password="Clave-Segura-Consulta-789",
                    role=UserRole.read_only,
                    permissions=[Capability.customers_read],
                ),
                administrator,
                self.db,
            )
        finally:
            dependency.close()

        self.assertEqual(user.permissions, [Capability.customers_read])
        allowed = require_authorized_user(
            build_operation_request("GET", "/api/v1/customers"),
            user,
        )
        self.assertEqual(allowed.id, user.id)
        with self.assertRaises(HTTPException) as write_forbidden:
            require_authorized_user(
                build_operation_request("POST", "/api/v1/customers"),
                user,
            )
        self.assertEqual(write_forbidden.exception.status_code, 403)
        with self.assertRaises(HTTPException) as unknown_forbidden:
            require_authorized_user(
                build_operation_request("GET", "/api/v1/new-module"),
                user,
            )
        self.assertEqual(unknown_forbidden.exception.status_code, 403)

        replacement = replace_operator_permissions(
            user.id,
            UserPermissionReplace(
                permissions=[Capability.services_read],
                reason="Cambio de funciones para pruebas",
            ),
            administrator,
            self.db,
        )
        self.assertEqual(replacement.permissions, [Capability.services_read])

    def test_administrator_bypasses_capability_policy(self) -> None:
        credentials = self.bootstrap()
        dependency, _request, administrator = self.authenticate(
            credentials.access_token
        )
        try:
            allowed = require_authorized_user(
                build_operation_request("DELETE", "/api/v1/new-module"),
                administrator,
            )
        finally:
            dependency.close()
        self.assertEqual(allowed.id, administrator.id)

    def test_every_business_operation_has_a_capability_policy(self) -> None:
        for route in app.routes:
            route_path = getattr(route, "path", "")
            if not route_path.startswith("/api/v1/"):
                continue
            if route_path.startswith("/api/v1/auth"):
                continue
            methods = getattr(route, "methods", set())
            for method in methods:
                with self.subTest(path=route_path, method=method):
                    self.assertIsNotNone(
                        capability_for_operation(method, route_path)
                    )

    def test_payment_decisions_and_application_require_approval(self) -> None:
        for path in (
            "/api/v1/payments/{payment_id}/verify",
            "/api/v1/payments/{payment_id}/reject",
            "/api/v1/payments/{payment_id}/cancel",
            "/api/v1/payments/{payment_id}/apply",
        ):
            with self.subTest(path=path):
                self.assertEqual(
                    capability_for_operation("POST", path),
                    Capability.billing_approve,
                )
        self.assertEqual(
            capability_for_operation("POST", "/api/v1/payments"),
            Capability.billing_write,
        )

    def test_coordinated_service_control_requires_network_control(self) -> None:
        for path in (
            "/api/v1/services/{service_id}/suspensions/coordinated",
            "/api/v1/services/{service_id}/reactivations/coordinated",
        ):
            with self.subTest(path=path):
                self.assertEqual(
                    capability_for_operation("POST", path),
                    Capability.network_control,
                )

    def test_extension_resolution_requires_billing_approval(self) -> None:
        service_path = "/api/v1/services/{service_id}/extensions"
        self.assertEqual(
            capability_for_operation("GET", service_path),
            Capability.billing_read,
        )
        self.assertEqual(
            capability_for_operation("POST", service_path),
            Capability.billing_write,
        )
        for action in ("fulfill", "cancel"):
            path = (
                f"{service_path}/{{extension_id}}/{action}"
            )
            with self.subTest(path=path):
                self.assertEqual(
                    capability_for_operation("POST", path),
                    Capability.billing_approve,
                )


if __name__ == "__main__":
    unittest.main()
