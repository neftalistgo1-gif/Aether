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
        ):
            with self.subTest(endpoint=endpoint):
                self.assertIn(endpoint, script)
        self.assertIn("sessionStorage", script)
        self.assertNotIn("localStorage", script)

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
