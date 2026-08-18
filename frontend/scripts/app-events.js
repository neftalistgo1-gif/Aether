/*
 * Enlaces DOM. Aquí se registran eventos; la lógica de negocio vive en los
 * módulos anteriores para que un cambio de pantalla sea fácil de localizar.
 */
$("#sync-uisp-button").addEventListener("click", async () => {
  const button = $("#sync-uisp-button");
  button.disabled = true;
  try {
    await api("/api/v1/uisp/sync", { method: "POST" });
    state.assets = await loadResource("/api/v1/assets");
    state.services = await loadResource("/api/v1/services");
    state.networkDevices = await loadOptionalList("/api/v1/network/devices");
    state.networkSummary = await loadResource("/api/v1/network/daily-summary").catch(() => null);
    renderNetworkDevices();
    renderAssets();
    renderServices();
    renderOverview();
    setNotice("Telemetría UISP actualizada.");
  } catch (error) { setNotice(error.message); } finally { button.disabled = false; }
});

document.querySelectorAll("[data-traffic-range]").forEach((button) => {
  button.addEventListener("click", async () => {
    state.trafficRange = button.dataset.trafficRange;
    state.trafficHistory = await loadResource(`/api/v1/mikrotik/traffic?period=${state.trafficRange}`).catch(() => null);
    renderTrafficChart();
  });
});

const SHARE_DATABASE = "aether-share-target";
const SHARE_STORE = "receipts";

function openShareDatabase() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(SHARE_DATABASE, 1);
    request.onupgradeneeded = () => request.result.createObjectStore(SHARE_STORE, { keyPath: "id" });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function takeSharedReceipt(id) {
  const database = await openShareDatabase();
  const entry = await new Promise((resolve, reject) => {
    const transaction = database.transaction(SHARE_STORE, "readwrite");
    const store = transaction.objectStore(SHARE_STORE);
    const request = store.get(id);
    request.onsuccess = () => {
      const value = request.result || null;
      if (value) store.delete(id);
      resolve(value);
    };
    request.onerror = () => reject(request.error);
  });
  database.close();
  return entry;
}

async function openSharedReceiptIfPresent() {
  const url = new URL(window.location.href);
  const receiptId = url.searchParams.get("shared_receipt");
  const sharedError = url.searchParams.get("shared_error");
  if (!receiptId && !sharedError) return;
  history.replaceState({}, "", "/app/");
  if (sharedError) {
    setNotice("No fue posible recibir el comprobante compartido.");
    return;
  }
  if (!hasCapability("billing.write")) {
    setNotice("Esta cuenta no tiene permiso para registrar comprobantes.");
    return;
  }
  if (!Array.isArray(state.customers) || state.customers.length === 0) {
    setNotice("El comprobante fue recibido, pero aun no hay clientes registrados para asociarlo. Importa los clientes primero y compartelo de nuevo.");
    return;
  }
  try {
    const shared = await takeSharedReceipt(receiptId);
    if (!shared?.file) {
      setNotice("El comprobante compartido ya no esta disponible. Compartelo de nuevo.");
      return;
    }
    if (!openPaymentDialog()) return;
    const files = new DataTransfer();
    files.items.add(shared.file);
    $("#payment-proof-file").files = files.files;
    $("#payment-method").value = "bank_transfer";
    const detail = [shared.title, shared.text, shared.url].filter(Boolean).join(" - ");
    $("#payment-notes").value = detail
      ? `Comprobante compartido desde WhatsApp. ${detail}`.slice(0, 1000)
      : "Comprobante compartido desde WhatsApp.";
    setNotice("Comprobante recibido. Selecciona al cliente y registra el pago para enviarlo a revision.");
  } catch (error) {
    console.error("Shared receipt import failed", error);
    setNotice("No fue posible abrir el comprobante compartido.");
  }
}

async function logout(callApi = true) {
  if (callApi && state.token) {
    await api("/api/v1/auth/logout", { method: "POST" }).catch(() => {});
  }
  state.token = null;
  state.user = null;
  sessionStorage.removeItem("aether_token");
  localStorage.removeItem("aether_token");
  appView.hidden = true;
  loginView.hidden = false;
  $("#password").value = "";
}

let loginInFlight = false;

function isInstalledAether() {
  return window.matchMedia("(display-mode: standalone)").matches
    || window.navigator.standalone === true;
}

function shouldRememberDeviceSession() {
  return $("#remember-device").checked || isInstalledAether();
}

if (isInstalledAether()) {
  $("#remember-device").checked = true;
}

async function handleLogin(event) {
  if (event) {
    event.preventDefault();
  }
  if (loginInFlight) {
    return;
  }
  const form = $("#login-form");
  const button = form?.querySelector("button");
  const errorBox = $("#login-error");
  if (!form || !button) {
    return;
  }
  if (!form.checkValidity()) {
    form.reportValidity();
    return;
  }
  loginInFlight = true;
  button.disabled = true;
  errorBox.textContent = "";
  try {
    const response = await api("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({
        username: $("#username").value.trim(),
        password: $("#password").value,
      }),
    });
    state.token = response.access_token;
    sessionStorage.setItem("aether_token", state.token);
    if (shouldRememberDeviceSession()) {
      localStorage.setItem("aether_token", state.token);
    } else {
      localStorage.removeItem("aether_token");
    }
    await enterApp();
  } catch (error) {
    errorBox.textContent =
      error.status === 401
        ? "El usuario o la contraseña no son correctos."
        : error.message;
  } finally {
    button.disabled = false;
    loginInFlight = false;
  }
}

$("#login-form").addEventListener("submit", handleLogin);
$("#login-form button").addEventListener("click", (event) => {
  if (event.detail !== 0) {
    handleLogin(event);
  }
});
$("#open-bootstrap-dialog").addEventListener("click", openBootstrapDialog);
$("#bootstrap-form").addEventListener("submit", saveBootstrapAdministrator);
$("#close-bootstrap-dialog").addEventListener("click", closeBootstrapDialog);
$("#cancel-bootstrap-dialog").addEventListener("click", closeBootstrapDialog);

window.addEventListener("load", () => {
  const bootstrappedFromUrl = bootstrapLoginFromUrl();
  void (async () => {
    state.bootstrapStatus = await loadBootstrapStatus();
    $("#open-bootstrap-dialog").hidden = !state.bootstrapStatus.can_bootstrap;
    if (
      state.bootstrapStatus.can_bootstrap &&
      !state.token &&
      !bootstrappedFromUrl
    ) {
      openBootstrapDialog();
    }
  })();
  if (state.token) {
    void enterApp();
    return;
  }
});

document.querySelectorAll(".nav-item").forEach((item) => {
  item.addEventListener("click", () => showView(item.dataset.view));
});
$("#customer-search").addEventListener("input", (event) => {
  renderCustomers(event.target.value);
});
$("#new-customer-button").addEventListener("click", () => {
  openCustomerDialog();
});
$("#customers-body").addEventListener("click", (event) => {
  const button = event.target.closest(".edit-customer");
  const accountButton = event.target.closest(".view-account");
  if (!button && !accountButton) return;
  const customer = state.customers?.find(
    (item) => item.id === (button || accountButton).dataset.customerId
  );
  if (!customer) return;
  if (accountButton) openAccountDialog(customer);
  else openCustomerDialog(customer);
});
$("#customer-form").addEventListener("submit", saveCustomer);
$("#close-customer-dialog").addEventListener(
  "click",
  closeCustomerDialog
);
$("#cancel-customer-dialog").addEventListener(
  "click",
  closeCustomerDialog
);
$("#new-service-button").addEventListener("click", openServiceDialog);
$("#service-search").addEventListener("input", renderServices);
$("#service-status-filter").addEventListener("change", renderServices);
$("#service-plan-filter").addEventListener("change", renderServices);
$("#service-payment-day-filter").addEventListener("change", renderServices);
$("#service-customer-search").addEventListener("input", (event) => {
  renderServiceCustomerOptions(event.target.value);
});
$("#service-plan").addEventListener("change", updateSelectedPlanPrice);
$("#service-postal-code").addEventListener("input", () => {
  void updatePostalCodeFields();
});
$("#service-form").addEventListener("submit", saveService);
$("#close-service-dialog").addEventListener("click", closeServiceDialog);
$("#cancel-service-dialog").addEventListener("click", closeServiceDialog);
$("#services-body").addEventListener("click", (event) => {
  const button = event.target.closest(".assess-installation");
  const networkButton = event.target.closest(".simulate-network-control");
  const reconciliationButton = event.target.closest(".reconcile-network");
  const notificationButton = event.target.closest(".record-notification");
  const suspensionButton = event.target.closest(
    ".check-commercial-suspension"
  );
  const reactivationButton = event.target.closest(
    ".check-commercial-reactivation"
  );
  const extensionButton = event.target.closest(".manage-extensions");
  const agreementButton = event.target.closest(
    ".manage-payment-agreements"
  );
  const cancellationButton = event.target.closest(
    ".manage-cancellation"
  );
  if (
    !button &&
    !networkButton &&
    !reconciliationButton &&
    !notificationButton &&
    !suspensionButton &&
    !reactivationButton &&
    !extensionButton &&
    !agreementButton &&
    !cancellationButton
  ) return;
  const service = state.services?.find(
    (item) =>
      item.id ===
      (
        button ||
        networkButton ||
        reconciliationButton ||
        notificationButton ||
        suspensionButton ||
        reactivationButton ||
        extensionButton ||
        agreementButton ||
        cancellationButton
      ).dataset.serviceId
  );
  if (!service) return;
  if (networkButton) openNetworkSimulationDialog(service);
  else if (reconciliationButton) {
    startNetworkReconciliation(service, reconciliationButton);
  } else if (notificationButton) openNotificationDialog(service);
  else if (suspensionButton) openSuspensionCheckDialog(service);
  else if (reactivationButton) openReactivationCheckDialog(service);
  else if (extensionButton) openExtensionDialog(service);
  else if (agreementButton) openPaymentAgreementDialog(service);
  else if (cancellationButton) openCancellationDialog(service);
  else openInstallationDialog(service);
});
$("#installation-coverage-result").addEventListener(
  "change",
  updateInstallationFields
);
$("#installation-form").addEventListener("submit", saveInstallation);
$("#close-installation-dialog").addEventListener(
  "click",
  closeInstallationDialog
);
$("#cancel-installation-dialog").addEventListener(
  "click",
  closeInstallationDialog
);
$("#installation-manage-form").addEventListener(
  "submit",
  rescheduleSelectedInstallation
);
$("#cancel-scheduled-installation").addEventListener(
  "click",
  cancelSelectedInstallation
);
$("#close-installation-manage-dialog").addEventListener(
  "click",
  closeInstallationManageDialog
);
$("#dismiss-installation-manage").addEventListener(
  "click",
  closeInstallationManageDialog
);
$("#open-installation-complete").addEventListener(
  "click",
  openInstallationCompleteDialog
);
$("#installation-complete-form").addEventListener(
  "submit",
  completeSelectedInstallation
);
$("#close-installation-complete-dialog").addEventListener(
  "click",
  returnToInstallationManageDialog
);
$("#cancel-installation-complete").addEventListener(
  "click",
  returnToInstallationManageDialog
);
$("#network-simulation-form").addEventListener(
  "submit",
  runNetworkSimulation
);
$("#close-network-simulation-dialog").addEventListener(
  "click",
  closeNetworkSimulationDialog
);
$("#cancel-network-simulation").addEventListener(
  "click",
  closeNetworkSimulationDialog
);
$("#notification-status").addEventListener(
  "change",
  updateNotificationResultFields
);
$("#notification-form").addEventListener("submit", saveNotification);
$("#close-notification-dialog").addEventListener(
  "click",
  closeNotificationDialog
);
$("#cancel-notification-dialog").addEventListener(
  "click",
  closeNotificationDialog
);
$("#suspension-check-form").addEventListener(
  "submit",
  runSuspensionCheck
);
$("#close-suspension-check-dialog").addEventListener(
  "click",
  closeSuspensionCheckDialog
);
$("#cancel-suspension-check").addEventListener(
  "click",
  closeSuspensionCheckDialog
);
$("#reactivation-check-form").addEventListener(
  "submit",
  runReactivationCheck
);
$("#reactivation-authorization-basis").addEventListener(
  "change",
  updateReactivationAuthorizer
);
$("#close-reactivation-check-dialog").addEventListener(
  "click",
  closeReactivationCheckDialog
);
$("#cancel-reactivation-check").addEventListener(
  "click",
  closeReactivationCheckDialog
);
$("#network-execution-form").addEventListener(
  "submit",
  executeConfirmedNetworkOperation
);
$("#close-network-execution-dialog").addEventListener(
  "click",
  closeNetworkExecutionDialog
);
$("#cancel-network-execution").addEventListener(
  "click",
  closeNetworkExecutionDialog
);
$("#close-cancellation-dialog").addEventListener(
  "click",
  closeCancellationDialog
);
$("#dismiss-cancellation-dialog").addEventListener(
  "click",
  closeCancellationDialog
);
$("#cancellation-workspace").addEventListener("submit", (event) => {
  if (event.target.id === "cancellation-request-form") {
    saveCancellationRequest(event);
  } else if (event.target.id === "recovery-schedule-form") {
    scheduleEquipmentRecovery(event);
  } else if (event.target.id === "recovery-complete-form") {
    completeEquipmentRecovery(event);
  } else if (event.target.id === "network-release-form") {
    simulateNetworkRelease(event);
  }
});
$("#cancellation-workspace").addEventListener("click", (event) => {
  const simulationButton = event.target.closest(
    "#simulate-cancellation-shutdown"
  );
  const pendingButton = event.target.closest(
    "#execute-pending-cancellation"
  );
  if (simulationButton) {
    simulateCancellationShutdown(simulationButton);
  } else if (pendingButton) {
    executePendingCancellation(pendingButton);
  }
});
$("#cancellation-workspace").addEventListener("change", (event) => {
  if (event.target.id === "recovery-evidence-images") {
    renderRecoveryEvidencePreview();
  }
});
$("#extension-create-form").addEventListener("submit", saveExtension);
$("#extension-resolve-form").addEventListener(
  "submit",
  resolveExtension
);
$("#close-extension-dialog").addEventListener(
  "click",
  closeExtensionDialog
);
$("#dismiss-extension-dialog").addEventListener(
  "click",
  closeExtensionDialog
);
$("#agreement-create-form").addEventListener(
  "submit",
  savePaymentAgreement
);
$("#agreement-resolve-form").addEventListener(
  "submit",
  resolvePaymentAgreement
);
$("#close-agreement-dialog").addEventListener(
  "click",
  closePaymentAgreementDialog
);
$("#dismiss-agreement-dialog").addEventListener(
  "click",
  closePaymentAgreementDialog
);
$("#new-payment-button").addEventListener("click", openPaymentDialog);
$("#payment-customer-search").addEventListener(
  "input",
  syncPaymentCustomerSelection
);
$("#payment-customer").addEventListener("change", updatePaymentServices);
$("#payment-form").addEventListener("submit", savePayment);
$("#close-payment-dialog").addEventListener("click", closePaymentDialog);
$("#cancel-payment-dialog").addEventListener("click", closePaymentDialog);
$("#preview-daily-operations-button").addEventListener("click", () => {
  void runDailyOperations(true);
});
$("#run-daily-operations-button").addEventListener("click", () => {
  void runDailyOperations(false);
});
$("#asset-search").addEventListener("input", renderAssets);
$("#asset-status-filter").addEventListener("change", renderAssets);
$("#asset-type-filter").addEventListener("change", renderAssets);
$("#new-asset-button").addEventListener("click", openAssetDialog);
$("#asset-form").addEventListener("submit", saveAsset);
$("#close-asset-dialog").addEventListener("click", closeAssetDialog);
$("#cancel-asset-dialog").addEventListener("click", closeAssetDialog);
$("#assets-body").addEventListener("click", (event) => {
  const button = event.target.closest(".view-asset");
  if (!button) return;
  const asset = state.assets?.find((item) => item.id === button.dataset.assetId);
  if (asset) void openAssetDetailDialog(asset);
});
$("#asset-detail-workspace").addEventListener("submit", (event) => {
  if (event.target.id === "asset-assign-form") {
    assignSelectedAsset(event);
  } else if (event.target.id === "asset-return-form") {
    returnSelectedAsset(event);
  }
});
$("#close-asset-detail-dialog").addEventListener("click", closeAssetDetailDialog);
$("#dismiss-asset-detail-dialog").addEventListener("click", closeAssetDetailDialog);
$("#payments-body").addEventListener("click", (event) => {
  const reviewButton = event.target.closest(".payment-review-action");
  const applyButton = event.target.closest(".payment-apply-action");
  const button = reviewButton || applyButton;
  if (!button) return;
  const payment = state.payments?.find(
    (item) => item.id === button.dataset.paymentId
  );
  if (!payment) return;
  if (reviewButton) openPaymentReviewDialog(payment);
  else openPaymentApplyDialog(payment);
});
$("#payment-review-form").addEventListener(
  "submit",
  verifySelectedPayment
);
document.querySelectorAll(".payment-queue-tabs .tab-button").forEach((button) => {
  button.addEventListener("click", () => {
    state.paymentFilter = button.dataset.paymentFilter;
    renderPayments();
  });
});
$("#reject-payment-button").addEventListener("click", () => {
  decideSelectedPayment("reject");
});
$("#cancel-pending-payment-button").addEventListener("click", () => {
  decideSelectedPayment("cancel");
});
$("#close-payment-review-dialog").addEventListener(
  "click",
  closePaymentReviewDialog
);
$("#dismiss-payment-review").addEventListener(
  "click",
  closePaymentReviewDialog
);
$("#payment-apply-form").addEventListener("submit", applySelectedPayment);
$("#close-payment-apply-dialog").addEventListener(
  "click",
  closePaymentApplyDialog
);
$("#cancel-payment-apply").addEventListener(
  "click",
  closePaymentApplyDialog
);
$("#close-account-dialog").addEventListener("click", closeAccountDialog);
$("#new-plan-button").addEventListener("click", openPlanDialog);
$("#plan-form").addEventListener("submit", savePlan);
$("#close-plan-dialog").addEventListener("click", closePlanDialog);
$("#cancel-plan-dialog").addEventListener("click", closePlanDialog);
$("#plans-body").addEventListener("click", (event) => {
  const priceButton = event.target.closest(".change-plan-price");
  const deactivateButton = event.target.closest(".deactivate-plan");
  const button = priceButton || deactivateButton;
  if (!button) return;
  const plan = state.plans?.find(
    (item) => item.id === button.dataset.planId
  );
  if (!plan) return;
  if (priceButton) openPlanPriceDialog(plan);
  else openPlanDeactivateDialog(plan);
});
$("#new-incident-button").addEventListener("click", openIncidentDialog);
$("#incident-form").addEventListener("submit", saveIncident);
$("#close-incident-dialog").addEventListener("click", closeIncidentDialog);
$("#cancel-incident-dialog").addEventListener("click", closeIncidentDialog);
$("#incidents-body").addEventListener("click", (event) => {
  const button = event.target.closest(".view-incident");
  if (!button) return;
  const incident = state.incidents?.find(
    (item) => item.id === button.dataset.incidentId
  );
  if (incident) openIncidentDetailDialog(incident);
});
$("#incident-workspace").addEventListener("submit", (event) => {
  if (event.target.id === "incident-add-impact-form") {
    addIncidentImpact(event);
  } else if (event.target.id === "incident-resolve-form") {
    resolveIncident(event);
  } else if (event.target.classList.contains("incident-restore-form")) {
    restoreIncidentImpact(event);
  } else if (
    event.target.classList.contains("incident-compensation-form")
  ) {
    compensateIncidentImpact(event);
  }
});
$("#close-incident-detail-dialog").addEventListener(
  "click",
  closeIncidentDetailDialog
);
$("#dismiss-incident-detail-dialog").addEventListener(
  "click",
  closeIncidentDetailDialog
);
$("#new-support-ticket-button").addEventListener("click", openSupportTicketDialog);
$("#support-ticket-form").addEventListener("submit", saveSupportTicket);
$("#close-support-ticket-dialog").addEventListener("click", closeSupportTicketDialog);
$("#cancel-support-ticket-dialog").addEventListener("click", closeSupportTicketDialog);
$("#support-tickets-body").addEventListener("click", (event) => {
  const button = event.target.closest(".view-support-ticket");
  if (!button) return;
  const ticket = state.supportTickets?.find(
    (item) => item.id === button.dataset.supportTicketId
  );
  if (ticket) openSupportTicketDetailDialog(ticket);
});
$("#support-ticket-workspace").addEventListener("submit", (event) => {
  if (event.target.id === "support-ticket-classify-form") {
    classifySelectedSupportTicket(event);
  } else if (event.target.id === "support-ticket-resolve-form") {
    resolveSelectedSupportTicket(event);
  }
});
$("#close-support-ticket-detail-dialog").addEventListener(
  "click",
  closeSupportTicketDetailDialog
);
$("#dismiss-support-ticket-detail-dialog").addEventListener(
  "click",
  closeSupportTicketDetailDialog
);
$("#new-user-button").addEventListener("click", () => openUserDialog());
$("#user-role").addEventListener("change", (event) => {
  applyUserRolePreset(event.target.value);
});
$("#user-permissions-grid").addEventListener("click", (event) => {
  const button = event.target.closest("[data-role-preset]");
  if (!button) return;
  applyUserRolePreset(button.dataset.rolePreset);
});
$("#users-body").addEventListener("click", (event) => {
  const editButton = event.target.closest(".edit-user");
  const resetButton = event.target.closest(".reset-user-password");
  const revokeSessionsButton = event.target.closest(".revoke-user-sessions");
  const deactivateButton = event.target.closest(".deactivate-user");
  const button = editButton || resetButton || revokeSessionsButton || deactivateButton;
  if (!button) return;
  const user = state.operatorUsers?.find(
    (item) => item.id === button.dataset.userId
  );
  if (!user) return;
  if (editButton) openUserDialog(user);
  else if (resetButton) void resetSelectedUserPassword(user);
  else if (revokeSessionsButton) void revokeOtherUserSessions(user);
  else void deactivateSelectedUser(user);
});
$("#user-form").addEventListener("submit", saveUser);
$("#close-user-dialog").addEventListener("click", closeUserDialog);
$("#cancel-user-dialog").addEventListener("click", closeUserDialog);
$("#plan-price-form").addEventListener("submit", savePlanPrice);
$("#close-plan-price-dialog").addEventListener(
  "click",
  closePlanPriceDialog
);
$("#cancel-plan-price-dialog").addEventListener(
  "click",
  closePlanPriceDialog
);
$("#plan-deactivate-form").addEventListener(
  "submit",
  deactivateSelectedPlan
);
$("#close-plan-deactivate-dialog").addEventListener(
  "click",
  closePlanDeactivateDialog
);
$("#cancel-plan-deactivate-dialog").addEventListener(
  "click",
  closePlanDeactivateDialog
);
$("#logout-button").addEventListener("click", () => logout());
$("#menu-button").addEventListener("click", () => {
  const sidebar = $(".sidebar");
  const open = sidebar.classList.toggle("open");
  $("#menu-button").setAttribute("aria-expanded", String(open));
});

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/app/service-worker.js").catch((error) => {
      console.warn("No fue posible preparar Aether para uso instalable.", error);
    });
  });
}

if (state.token) enterApp();
