import unittest
from pathlib import Path

from app.main import app, frontend_directory


class FrontendShellTestCase(unittest.TestCase):
    def test_frontend_assets_exist_and_are_mounted(self) -> None:
        expected = {
            "index.html",
            "styles.css",
            "app.js",
            "assets/aether-horizontal.png",
            "assets/aether-mark.png",
        }
        for relative_path in expected:
            with self.subTest(path=relative_path):
                self.assertTrue(
                    (frontend_directory / relative_path).is_file()
                )
        mounted_paths = {
            getattr(route, "path", "")
            for route in app.routes
        }
        self.assertIn("/app", mounted_paths)

    def test_frontend_uses_real_auth_and_business_endpoints(self) -> None:
        script = (frontend_directory / "app.js").read_text(
            encoding="utf-8"
        )
        for endpoint in (
            "/api/v1/auth/login",
            "/api/v1/auth/me",
            "/api/v1/auth/logout",
            "/api/v1/customers",
            "/api/v1/services",
            "/api/v1/payments",
            "/api/v1/plans?plan_status=active",
        ):
            with self.subTest(endpoint=endpoint):
                self.assertIn(endpoint, script)
        self.assertIn("sessionStorage", script)
        self.assertNotIn("localStorage", script)
        self.assertIn('hasCapability("customers.write")', script)
        self.assertIn('method: editing ? "PATCH" : "POST"', script)
        self.assertIn('reason: $("#customer-reason").value.trim()', script)
        self.assertIn('hasCapability("services.write")', script)
        self.assertIn("plan_id: plan.id", script)
        self.assertIn('setNotice("El servicio quedó registrado como pendiente.")', script)
        self.assertIn('hasCapability("billing.write")', script)
        self.assertIn("proof_reference: optionalText", script)
        self.assertIn(
            "El pago quedó pendiente de verificación",
            script,
        )
        self.assertIn('hasCapability("billing.approve")', script)
        self.assertIn("/verify", script)
        self.assertIn("/apply", script)
        self.assertIn('decideSelectedPayment("reject")', script)
        self.assertIn('decideSelectedPayment("cancel")', script)
        self.assertIn(
            "Aún falta aplicarlo para reducir la deuda",
            script,
        )

    def test_frontend_contains_no_embedded_credentials(self) -> None:
        content = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                frontend_directory / "index.html",
                frontend_directory / "app.js",
            )
        ).lower()
        self.assertNotIn("aether_bootstrap_secret", content)
        self.assertNotIn("clave-segura", content)


if __name__ == "__main__":
    unittest.main()
