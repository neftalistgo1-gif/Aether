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
        page = (frontend_directory / "index.html").read_text(
            encoding="utf-8"
        )
        for endpoint in (
            "/api/v1/auth/login",
            "/api/v1/auth/me",
            "/api/v1/auth/logout",
            "/api/v1/customers",
            "/api/v1/services",
            "/api/v1/payments",
            "/api/v1/plans",
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
        self.assertIn('hasCapability("billing.read")', script)
        self.assertIn("/balance`)", script)
        self.assertIn("/charges`)", script)
        self.assertIn("Estado de cuenta", script)
        self.assertIn('hasCapability("plans.read")', script)
        self.assertIn('hasCapability("plans.write")', script)
        self.assertIn("/prices", script)
        self.assertIn("/deactivate", script)
        self.assertIn(
            "los servicios existentes no fueron modificados",
            script,
        )
        self.assertIn('hasCapability("installations.write")', script)
        self.assertIn('hasCapability("installations.read")', script)
        self.assertIn('installation_type: "installation"', script)
        self.assertIn("coverage_result: result", script)
        self.assertIn(
            "su cargo fue generado",
            script,
        )
        self.assertIn("/reschedule", script)
        self.assertIn(
            "cancelled_by: state.user.display_name",
            script,
        )
        self.assertIn(
            "el historial quedó conservado",
            script,
        )
        self.assertIn("/complete", script)
        self.assertIn("antenna_photos: antennaPhotos", script)
        self.assertIn("modem_photos: modemPhotos", script)
        self.assertIn("navigation_confirmed:", script)
        self.assertIn(
            "el servicio fue activado",
            script,
        )
        self.assertIn('hasCapability("network.control")', script)
        self.assertIn("/network-control/${action}", script)
        self.assertIn("dry_run: true", script)
        self.assertIn(
            "MikroTik y el estado comercial no cambiaron",
            script,
        )
        self.assertIn('hasCapability("notifications.write")', script)
        self.assertIn('api("/api/v1/notifications"', script)
        self.assertIn("evidence_reference: evidenceReference", script)
        self.assertIn(
            "La entrega quedó registrada y auditada",
            script,
        )
        self.assertIn('hasCapability("notifications.read")', script)
        self.assertIn("/suspensions/coordinated", script)
        self.assertIn("grace_period_elapsed:", script)
        self.assertIn("extension_checked:", script)
        self.assertIn("openNetworkExecutionDialog", script)
        self.assertIn(
            ".check-commercial-reactivation",
            script,
        )
        self.assertIn("/reactivations/coordinated", script)
        self.assertIn(
            "debt_amount: state.selectedReactivationDebt",
            script,
        )
        self.assertIn(
            "authorized_by:",
            script,
        )
        self.assertIn("pendingNetworkOperation", script)
        self.assertIn(
            "selectedReactivationAuthorizations",
            script,
        )
        self.assertIn(
            "extension_id:",
            script,
        )
        self.assertIn(
            "payment_agreement_id:",
            script,
        )
        self.assertIn(
            "o un convenio vigente del titular actual",
            page,
        )
        self.assertIn("network-execution-form", page)
        self.assertIn("Ejecutar cambio real", page)
        self.assertIn("preflight_command_id:", script)
        self.assertIn("dry_run: false", script)
        self.assertIn(
            "Escribe exactamente ${operation.serviceCode}",
            script,
        )
        self.assertIn(
            "La orden real no fue confirmada por MikroTik",
            script,
        )
        self.assertIn(".manage-extensions", script)
        self.assertIn("/extensions`", script)
        self.assertIn(
            "original_due_date:",
            script,
        )
        self.assertIn(
            "evidence_reference:",
            script,
        )
        self.assertIn(
            '${activeExtension.id}/${action}',
            script,
        )
        self.assertIn(
            "La prórroga no elimina",
            page,
        )
        self.assertIn(".manage-payment-agreements", script)
        self.assertIn("/payment-agreements", script)
        self.assertIn(
            "promised_amount:",
            script,
        )
        self.assertIn(
            "installment_count:",
            script,
        )
        self.assertIn(
            "Sin monto, fecha ni parcialidades pactadas",
            script,
        )
        self.assertIn(
            "El convenio quedó registrado sin completar datos no acordados",
            script,
        )
        self.assertIn(
            "convenio no reduce la deuda",
            page,
        )

    def test_live_network_ui_requires_coordinated_preflight_confirmation(
        self,
    ) -> None:
        script = (frontend_directory / "app.js").read_text(
            encoding="utf-8"
        )
        page = (frontend_directory / "index.html").read_text(
            encoding="utf-8"
        )
        technical_simulation = script.split(
            "async function runNetworkSimulation",
            maxsplit=1,
        )[1].split(
            "function updateNotificationResultFields",
            maxsplit=1,
        )[0]

        self.assertIn("dry_run: true", technical_simulation)
        self.assertNotIn("dry_run: false", technical_simulation)
        self.assertIn("NETWORK_PREFLIGHT_VALIDITY_MS", script)
        self.assertIn("preflight_command_id:", script)
        self.assertIn("dry_run: false", script)
        self.assertIn("network-execution-code", page)
        self.assertIn("network-execution-confirm", page)
        self.assertIn("válida por 15 minutos", page)

    def test_cancellation_ui_preserves_staged_safe_workflow(self) -> None:
        script = (frontend_directory / "app.js").read_text(
            encoding="utf-8"
        )
        page = (frontend_directory / "index.html").read_text(
            encoding="utf-8"
        )

        self.assertIn('hasCapability("services.cancel")', script)
        self.assertIn('hasCapability("assets.write")', script)
        self.assertIn("cancellation-request-form", script)
        self.assertIn("/cancellation/coordinated", script)
        self.assertIn("/equipment-recovery/complete", script)
        self.assertIn(
            "/cancellation/network-release/coordinated",
            script,
        )
        self.assertIn("physical_disconnect_confirmed:", script)
        self.assertIn("disconnect_evidence_reference:", script)
        self.assertIn('type: "cancellation"', script)
        self.assertIn('type: "network_release"', script)
        self.assertIn("preflightCommandId: result.command.id", script)
        self.assertIn("cancellation-dialog", page)
        self.assertIn("BAJA SEGURA · FLUJO POR ETAPAS", page)

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
