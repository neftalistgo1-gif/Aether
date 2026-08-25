import unittest
from pathlib import Path

from app.main import app, frontend_directory


FRONTEND_SCRIPT_FILES = (
    "scripts/app-core.js",
    "scripts/app-assets.js",
    "scripts/app-services.js",
    "scripts/app-billing.js",
    "scripts/app-operations.js",
    "scripts/app-administration.js",
    "scripts/app-events.js",
)


def frontend_script() -> str:
    return "\n".join(
        (frontend_directory / path).read_text(encoding="utf-8")
        for path in FRONTEND_SCRIPT_FILES
    )


class FrontendShellTestCase(unittest.TestCase):
    def test_frontend_assets_exist_and_are_mounted(self) -> None:
        expected = {
            "index.html",
            "styles.css",
            "app.js",
            *FRONTEND_SCRIPT_FILES,
            "assets/aether-horizontal.png",
            "assets/aether-mark.png",
        }
        for relative_path in expected:
            with self.subTest(path=relative_path):
                self.assertTrue(
                    (frontend_directory / relative_path).is_file()
                )
        page = (frontend_directory / "index.html").read_text(encoding="utf-8")
        worker = (frontend_directory / "service-worker.js").read_text(
            encoding="utf-8"
        )
        for relative_path in FRONTEND_SCRIPT_FILES:
            with self.subTest(script=relative_path):
                self.assertIn(f'/app/{relative_path}', page)
                self.assertIn(f'"/app/{relative_path}"', worker)
        mounted_paths = {
            getattr(route, "path", "")
            for route in app.routes
        }
        self.assertIn("/app", mounted_paths)

    def test_frontend_uses_real_auth_and_business_endpoints(self) -> None:
        script = frontend_script()
        page = (frontend_directory / "index.html").read_text(
            encoding="utf-8"
        )
        for endpoint in (
            "/api/v1/auth/login",
            "/api/v1/auth/me",
            "/api/v1/auth/logout",
            "/api/v1/customers",
            "/api/v1/services",
            "/api/v1/postal-codes",
            "/api/v1/payments",
            "/api/v1/payments/receipts",
            "/api/v1/operations/daily",
            "/api/v1/assets",
            "/api/v1/plans",
            "/api/v1/incidents",
            "/api/v1/support-tickets",
        ):
            with self.subTest(endpoint=endpoint):
                self.assertIn(endpoint, script)
        self.assertIn("sessionStorage", script)
        self.assertIn("localStorage", script)
        self.assertIn("remember-device", page)
        self.assertIn("service-worker.js", script)
        self.assertIn("shouldRememberDeviceSession", script)
        self.assertIn("isInstalledAether", script)
        self.assertIn('id="suspended-services"', page)
        self.assertIn("Suspensiones", page)
        self.assertIn("No hay antenas sin conexión a UISP.", script)
        self.assertIn("Aun no hay clientes registrados", script)
        self.assertTrue((frontend_directory / "manifest.webmanifest").is_file())
        self.assertTrue((frontend_directory / "service-worker.js").is_file())
        self.assertIn('hasCapability("customers.write")', script)
        self.assertIn('method: editing ? "PATCH" : "POST"', script)
        self.assertIn('reason: $("#customer-reason").value.trim()', script)
        self.assertIn('hasCapability("services.write")', script)
        self.assertIn("plan_id: plan.id", script)
        self.assertIn("composeServiceAddress()", script)
        self.assertIn("renderServiceCustomerOptions", script)
        self.assertIn("updatePostalCodeFields", script)
        self.assertIn('setNotice("El servicio quedó registrado como pendiente.")', script)
        self.assertIn('hasCapability("billing.write")', script)
        self.assertIn('"proof_reference"', script)
        self.assertIn(
            "El pago quedó pendiente de verificación",
            script,
        )
        self.assertIn('hasCapability("billing.approve")', script)
        self.assertIn("/verify", script)
        self.assertIn("/apply", script)
        self.assertIn('hasCapability("operations.read")', script)
        self.assertIn('hasCapability("operations.run")', script)
        self.assertIn("runDailyOperations", script)
        self.assertIn("renderDailyOperations", script)
        self.assertIn('hasCapability("assets.read")', script)
        self.assertIn('hasCapability("assets.write")', script)
        self.assertIn("openAssetDialog", script)
        self.assertIn("assignSelectedAsset", script)
        self.assertIn("returnSelectedAsset", script)
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
        self.assertIn("service-customer-search", page)
        self.assertIn("service-postal-code", page)
        self.assertIn("service-colonia", page)
        self.assertIn("operations-run-date", page)
        self.assertIn("Operación diaria", page)
        self.assertIn("Inventario y activos", page)
        self.assertIn("asset-dialog", page)
        self.assertIn("asset-detail-dialog", page)
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
        self.assertIn('hasCapability("incidents.read")', script)
        self.assertIn('hasCapability("incidents.write")', script)
        self.assertIn('hasCapability("incidents.compensate")', script)
        self.assertIn("incident-add-impact-form", script)
        self.assertIn("/api/v1/incidents", script)
        self.assertIn("/restore", script)
        self.assertIn("/resolve", script)
        self.assertIn("/compensation", script)
        self.assertIn("payment-queue-summary", page)
        self.assertIn("payment-queue-tabs", page)
        self.assertIn("Bandeja de comprobantes", page)
        self.assertIn("payment-customer-search", page)
        self.assertIn("payment-proof-file", page)
        self.assertIn("payment-proof-preview", page)
        self.assertIn('state.paymentFilter', script)
        self.assertIn("apiBlob(", script)
        self.assertIn("syncPaymentCustomerSelection", script)
        self.assertIn("receipts", script)
        self.assertIn("Incidencias", page)
        self.assertIn("SEGUIMIENTO DE INCIDENCIA", page)
        self.assertIn("Soporte", page)
        self.assertIn("Tickets de soporte", page)
        self.assertIn("support-ticket-dialog", page)
        self.assertIn("support-ticket-detail-dialog", page)
        self.assertIn('hasCapability("support.read")', script)
        self.assertIn('hasCapability("support.write")', script)
        self.assertIn("/api/v1/support-tickets", script)
        self.assertIn("Usuarios del sistema", page)
        self.assertIn("user-dialog", page)
        self.assertIn("bootstrap-dialog", page)
        self.assertIn("/api/v1/auth/users", script)
        self.assertIn("Editar usuario", script)
        self.assertIn("Contraseña inicial", page)

    def test_live_network_ui_requires_coordinated_preflight_confirmation(
        self,
    ) -> None:
        script = frontend_script()
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
        script = frontend_script()
        page = (frontend_directory / "index.html").read_text(
            encoding="utf-8"
        )

        self.assertIn('hasCapability("services.cancel")', script)
        self.assertIn('hasCapability("assets.write")', script)
        self.assertIn("cancellation-request-form", script)
        self.assertIn("/cancellation/coordinated", script)
        self.assertIn("/equipment-recovery/complete", script)
        self.assertIn("buildRecoveryEvidenceReferences", script)
        self.assertIn("recovery-evidence-images", script)
        self.assertIn("recovery-evidence-preview", script)
        self.assertIn("renderRecoveryEvidencePreview", script)
        self.assertIn('accept="image/*"', script)
        self.assertIn(
            "/cancellation/network-release/coordinated",
            script,
        )
        self.assertIn("physical_disconnect_confirmed:", script)
        self.assertIn("disconnect_evidence_reference:", script)
        self.assertIn('type: "cancellation"', script)
        self.assertIn('type: "network_release"', script)
        self.assertIn("preflightCommandId: result.command.id", script)
        self.assertIn(
            "Puedes cerrar la visita sin imágenes",
            script,
        )
        self.assertIn("cancellation-dialog", page)
        self.assertIn("BAJA SEGURA · FLUJO POR ETAPAS", page)

    def test_network_reconciliation_ui_requires_confirmed_preflight(
        self,
    ) -> None:
        script = frontend_script()
        reconciliation = script.split(
            "async function startNetworkReconciliation",
            maxsplit=1,
        )[1].split(
            "function updateNotificationResultFields",
            maxsplit=1,
        )[0]

        self.assertIn(".reconcile-network", script)
        self.assertIn("/network-control/inspect", reconciliation)
        self.assertIn("/network-control/reconcile", reconciliation)
        self.assertLess(
            reconciliation.index("/network-control/inspect"),
            reconciliation.index("/network-control/reconcile"),
        )
        self.assertIn("inspection.matches_expected", reconciliation)
        self.assertIn(
            "network_inspection_id: inspection.id",
            reconciliation,
        )
        self.assertIn("dry_run: true", reconciliation)
        self.assertNotIn("dry_run: false", reconciliation)
        self.assertIn('type: "reconciliation"', reconciliation)
        self.assertIn("openNetworkExecutionDialog", reconciliation)
        self.assertIn(
            "RECONCILIACIÓN DE RED · CONFIRMACIÓN FINAL",
            script,
        )
        self.assertIn(
            "El estado comercial no cambiará",
            script,
        )
        self.assertIn(
            "no se requiere corrección",
            reconciliation,
        )

    def test_frontend_contains_no_embedded_credentials(self) -> None:
        content = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                frontend_directory / "index.html",
                *(frontend_directory / path for path in FRONTEND_SCRIPT_FILES),
            )
        ).lower()
        self.assertNotIn("aether_bootstrap_secret", content)
        self.assertNotIn("clave-segura", content)


if __name__ == "__main__":
    unittest.main()
