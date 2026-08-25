/*
 * Núcleo de la interfaz: estado compartido, autenticación, carga inicial,
 * resumen operativo y utilidades reutilizables. Cargar siempre primero.
 */
const state = {
  token: sessionStorage.getItem("aether_token") || localStorage.getItem("aether_token"),
  user: null,
  customers: [],
  services: [],
  payments: [],
  dailyOperations: [],
  assets: [],
  plans: [],
  incidents: [],
  supportTickets: [],
  operatorUsers: [],
  accessPointHealth: [],
  networkDevices: [],
  networkSummary: null,
  uispConnection: null,
  mikrotikHealth: [],
  trafficHistory: null,
  trafficRange: "1h",
  bootstrapStatus: {
    configured: false,
    completed: false,
    can_bootstrap: false,
  },
  latestDailyOperationResult: null,
  selectedAssetId: null,
  selectedAssetAssignments: [],
  selectedAssetNetworkHistory: [],
  editingCustomerId: null,
  selectedPaymentId: null,
  paymentFilter: "all",
  selectedPlanId: null,
  selectedServiceId: null,
  selectedInstallation: null,
  selectedNetworkAction: null,
  selectedSuspensionDebt: null,
  selectedReactivationDebt: null,
  selectedReactivationAuthorizations: [],
  selectedExtensions: [],
  selectedExtensionBalance: null,
  selectedExtensionDueDate: null,
  selectedPaymentAgreements: [],
  selectedAgreementBalance: null,
  selectedCancellation: null,
  selectedRecovery: null,
  selectedIncidentId: null,
  selectedSupportTicketId: null,
  selectedOperatorUserId: null,
  pendingNetworkOperation: null,
  recoveryEvidencePreviewUrls: [],
};

const NETWORK_PREFLIGHT_VALIDITY_MS = 15 * 60 * 1000;
const MAX_RECOVERY_EVIDENCE_IMAGES = 6;
const MAX_RECOVERY_EVIDENCE_IMAGE_BYTES = 2 * 1024 * 1024;
const MAX_RECOVERY_EVIDENCE_REFERENCES = 20;

const USER_PERMISSION_GROUPS = [
  {
    label: "Clientes",
    permissions: [
      ["customers.read", "Consultar clientes"],
      ["customers.write", "Crear y editar clientes"],
    ],
  },
  {
    label: "Servicios",
    permissions: [
      ["services.read", "Consultar servicios"],
      ["services.write", "Crear y editar servicios"],
      ["services.cancel", "Suspender o cancelar servicios"],
    ],
  },
  {
    label: "Cobranza",
    permissions: [
      ["billing.read", "Consultar cobros"],
      ["billing.write", "Registrar cobros y movimientos"],
      ["billing.approve", "Aprobar o rechazar pagos"],
    ],
  },
  {
    label: "Contratos",
    permissions: [
      ["contracts.read", "Consultar contratos"],
      ["contracts.write", "Crear y editar contratos"],
    ],
  },
  {
    label: "Instalaciones",
    permissions: [
      ["installations.read", "Consultar instalaciones"],
      ["installations.write", "Programar o editar instalaciones"],
    ],
  },
  {
    label: "Inventario",
    permissions: [
      ["assets.read", "Consultar inventario"],
      ["assets.write", "Registrar o mover inventario"],
    ],
  },
  {
    label: "Incidencias",
    permissions: [
      ["incidents.read", "Consultar incidencias"],
      ["incidents.write", "Registrar o editar incidencias"],
      ["incidents.compensate", "Aplicar compensaciones"],
    ],
  },
  {
    label: "Red",
    permissions: [
      ["network.read", "Consultar red"],
      ["network.control", "Aplicar cortes o reactivaciones"],
    ],
  },
  {
    label: "Planes",
    permissions: [
      ["plans.read", "Consultar planes"],
      ["plans.write", "Crear y editar planes"],
    ],
  },
  {
    label: "Operación",
    permissions: [
      ["operations.read", "Consultar operaciones"],
      ["operations.run", "Ejecutar procesos diarios"],
    ],
  },
  {
    label: "Soporte",
    permissions: [
      ["support.read", "Consultar tickets de soporte"],
      ["support.write", "Registrar y clasificar tickets"],
    ],
  },
  {
    label: "Notificaciones",
    permissions: [
      ["notifications.read", "Consultar notificaciones"],
      ["notifications.write", "Enviar notificaciones"],
    ],
  },
  {
    label: "Auditoría",
    permissions: [["audit.read", "Consultar auditoría"]],
  },
];

const USER_ROLE_PRESETS = {
  customer_service: [
    "customers.read",
    "services.read",
    "billing.read",
    "support.read",
    "support.write",
    "notifications.read",
  ],
  network_technician: [
    "services.read",
    "services.write",
    "services.cancel",
    "network.read",
    "network.control",
    "incidents.read",
    "incidents.write",
    "operations.read",
  ],
  installer: [
    "customers.read",
    "services.read",
    "installations.read",
    "installations.write",
    "assets.read",
    "notifications.read",
  ],
  read_only: [
    "customers.read",
    "services.read",
    "billing.read",
    "contracts.read",
    "installations.read",
    "assets.read",
    "incidents.read",
    "network.read",
    "plans.read",
    "operations.read",
    "support.read",
    "notifications.read",
    "audit.read",
  ],
};

const USER_PERMISSION_LABELS = Object.fromEntries(
  USER_PERMISSION_GROUPS.flatMap((group) =>
    group.permissions.map(([permission, label]) => [permission, label])
  )
);

const $ = (selector) => document.querySelector(selector);
const loginView = $("#login-view");
const appView = $("#app-view");
const notice = $("#notice");

function getQueryParam(name) {
  return new URLSearchParams(window.location.search).get(name) || "";
}

function bootstrapLoginFromUrl() {
  const username = getQueryParam("username").trim();
  const password = getQueryParam("password");
  if (!username || !password) {
    return false;
  }
  $("#username").value = username;
  $("#password").value = password;
  void handleLogin();
  return true;
}

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  if (options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  const response = await fetch(path, { ...options, headers });
  if (response.status === 204) return null;
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload.detail;
    const validationMessage = Array.isArray(detail)
      ? detail.map((item) => item.msg).join(" ")
      : null;
    const error = new Error(
      validationMessage ||
      (typeof detail === "string"
        ? detail
        : typeof detail?.message === "string"
          ? detail.message
        : "No fue posible completar la solicitud."
      )
    );
    error.status = response.status;
    throw error;
  }
  return payload;
}

function openBootstrapDialog() {
  $("#bootstrap-secret").value = "";
  $("#bootstrap-username").value = "";
  $("#bootstrap-display-name").value = "";
  $("#bootstrap-password").value = "";
  $("#bootstrap-error").textContent = "";
  $("#bootstrap-dialog").showModal();
  $("#bootstrap-secret").focus();
}

function closeBootstrapDialog() {
  $("#bootstrap-dialog").close();
}

async function saveBootstrapAdministrator(event) {
  event.preventDefault();
  const submitButton = event.currentTarget.querySelector('button[type="submit"]');
  const errorBox = $("#bootstrap-error");
  submitButton.disabled = true;
  errorBox.textContent = "";
  try {
    const response = await fetch("/api/v1/auth/bootstrap", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Aether-Bootstrap": $("#bootstrap-secret").value,
      },
      body: JSON.stringify({
        username: $("#bootstrap-username").value.trim(),
        display_name: $("#bootstrap-display-name").value.trim(),
        password: $("#bootstrap-password").value,
      }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const validationDetail = Array.isArray(payload.detail)
        ? payload.detail
            .map((issue) => {
              const field = issue.loc?.at(-1);
              return field ? `${field}: ${issue.msg}` : issue.msg;
            })
            .join(". ")
        : null;
      throw new Error(
        typeof payload.detail === "string"
          ? payload.detail
          : validationDetail || "No fue posible crear el administrador."
      );
    }
    state.token = payload.access_token;
    sessionStorage.setItem("aether_token", state.token);
    state.bootstrapStatus = {
      configured: true,
      completed: true,
      can_bootstrap: false,
    };
    $("#open-bootstrap-dialog").hidden = true;
    closeBootstrapDialog();
    await enterApp();
    setNotice("El administrador inicial quedó creado.");
  } catch (error) {
    errorBox.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

async function apiBlob(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const response = await fetch(path, { ...options, headers });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const detail = payload.detail;
    const error = new Error(
      typeof detail === "string"
        ? detail
        : "No fue posible cargar el archivo solicitado."
    );
    error.status = response.status;
    throw error;
  }
  return response.blob();
}

function formatDate(value) {
  if (!value) return "—";
  const parsed = /^\d{4}-\d{2}-\d{2}$/.test(value)
    ? new Date(`${value}T00:00:00`)
    : new Date(value);
  return new Intl.DateTimeFormat("es-MX", { dateStyle: "medium" }).format(
    parsed
  );
}

function formatDateTime(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("es-MX", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function formatMoney(value) {
  return new Intl.NumberFormat("es-MX", {
    style: "currency",
    currency: "MXN",
  }).format(Number(value || 0));
}

function escapeText(value) {
  const node = document.createElement("span");
  node.textContent = value ?? "";
  return node.innerHTML;
}

function setNotice(message = "") {
  notice.textContent = message;
  notice.hidden = !message;
}

async function loadResource(path) {
  try {
    return await api(path);
  } catch (error) {
    if (error.status === 403) return null;
    throw error;
  }
}

async function loadOptionalList(path) {
  try {
    return await api(path);
  } catch (error) {
    console.warn(`Optional resource unavailable: ${path}`, error);
    return [];
  }
}

async function loadBootstrapStatus() {
  try {
    const response = await fetch("/api/v1/auth/bootstrap/status");
    if (!response.ok) {
      return {
        configured: false,
        completed: false,
        can_bootstrap: false,
      };
    }
    return await response.json();
  } catch (error) {
    console.warn("Bootstrap status unavailable", error);
    return {
      configured: false,
      completed: false,
      can_bootstrap: false,
    };
  }
}

async function loadWorkspace() {
  state.user = await api("/api/v1/auth/me");
  const [customers, services, payments, dailyOperations, assets, plans, incidents, supportTickets, operatorUsers, accessPointHealth, networkDevices, networkSummary, uispConnection, mikrotikHealth, trafficHistory] = await Promise.all([
    loadResource("/api/v1/customers"),
    loadResource("/api/v1/services"),
    loadResource("/api/v1/payments"),
    loadResource("/api/v1/operations/daily"),
    loadResource("/api/v1/assets"),
    loadResource("/api/v1/plans"),
    loadResource("/api/v1/incidents"),
    loadOptionalList("/api/v1/support-tickets"),
    loadOptionalList("/api/v1/auth/users"),
    loadOptionalList("/api/v1/mikrotik/access-points/health"),
    loadOptionalList("/api/v1/network/devices"),
    loadResource("/api/v1/network/daily-summary").catch(() => null),
    loadResource("/api/v1/uisp/connection").catch(() => null),
    loadOptionalList("/api/v1/mikrotik/routers/health"),
    loadResource("/api/v1/mikrotik/traffic?period=1h").catch(() => null),
  ]);
  state.customers = customers;
  state.services = services;
  state.payments = payments;
  state.dailyOperations = dailyOperations;
  state.latestDailyOperationResult = dailyOperations?.[0] || null;
  state.assets = assets;
  state.plans = plans;
  state.incidents = incidents;
  state.supportTickets = supportTickets;
  state.operatorUsers = operatorUsers;
  state.accessPointHealth = accessPointHealth;
  state.networkDevices = networkDevices;
  state.networkSummary = networkSummary;
  state.uispConnection = uispConnection;
  state.mikrotikHealth = mikrotikHealth;
  state.trafficHistory = trafficHistory;
  renderUser();
  renderOverview();
  renderCustomers();
  renderServices();
  renderPayments();
  renderDailyOperations();
  renderAssets();
  renderPlans();
  renderIncidents();
  renderSupportTickets();
  renderOperatorUsers();
  renderNetworkDevices();
}

function renderUser() {
  $("#user-name").textContent = state.user.display_name;
  $("#user-role").textContent = state.user.role.replaceAll("_", " ");
  $("#user-avatar").textContent = state.user.display_name.charAt(0).toUpperCase();
  const permissions = state.user.role === "administrator"
    ? ["Acceso administrativo total"]
    : state.user.permissions;
  const permissionList = $("#permission-list");
  if (permissionList) {
    permissionList.innerHTML = permissions.length
      ? permissions.map((item) => `<span class="permission">${escapeText(item)}</span>`).join("")
      : '<p class="empty-state">Esta cuenta aún no tiene capacidades asignadas.</p>';
  }
  const canWriteCustomers = hasCapability("customers.write");
  const canReadBilling = hasCapability("billing.read");
  $("#new-customer-button").hidden = !canWriteCustomers;
  document.querySelectorAll(".customer-action-column").forEach((column) => {
    column.hidden = !(canWriteCustomers || canReadBilling);
  });
  const canWriteServices = hasCapability("services.write");
  const hasServiceReferences = Boolean(
    state.customers?.length &&
    state.plans?.some(
      (plan) => plan.status === "active" && plan.current_price !== null
    )
  );
  $("#new-service-button").hidden = !(
    canWriteServices && hasServiceReferences
  );
  const serviceWriteNote = $("#service-write-note");
  serviceWriteNote.hidden = !canWriteServices || hasServiceReferences;
  serviceWriteNote.textContent = hasServiceReferences
    ? ""
    : "Para registrar servicios se necesita al menos un cliente y un plan activo visibles para esta cuenta.";
  const canWritePayments = hasCapability("billing.write");
  const hasPaymentReferences = Boolean(state.customers?.length);
  $("#new-payment-button").hidden = !(
    canWritePayments && hasPaymentReferences
  );
  const paymentWriteNote = $("#payment-write-note");
  paymentWriteNote.hidden = !canWritePayments || hasPaymentReferences;
  paymentWriteNote.textContent = hasPaymentReferences
    ? ""
    : "Para registrar pagos se necesita al menos un cliente visible para esta cuenta.";
  document.querySelectorAll(".payment-action-column").forEach((column) => {
    column.hidden = !hasCapability("billing.approve");
  });
  const canReadOperations = hasCapability("operations.read");
  const canRunOperations = hasCapability("operations.run");
  document.querySelector('[data-view="operations"]').hidden = !canReadOperations;
  $("#preview-daily-operations-button").hidden = !canRunOperations;
  $("#run-daily-operations-button").hidden = !canRunOperations;
  const operationsRunNote = $("#operations-run-note");
  operationsRunNote.hidden = canRunOperations;
  operationsRunNote.textContent = canRunOperations
    ? ""
    : "Esta cuenta puede consultar ejecuciones previas, pero no iniciar la operación diaria.";
  const canReadAssets = hasCapability("assets.read");
  const canWriteAssets = hasCapability("assets.write");
  document.querySelector('[data-view="assets"]').hidden = !canReadAssets;
  $("#new-asset-button").hidden = !canWriteAssets;
  $("#assets-write-note").hidden = canWriteAssets;
  $("#assets-write-note").textContent = canWriteAssets
    ? ""
    : "Esta cuenta puede consultar el inventario, pero no registrar ni mover activos.";
  document.querySelectorAll(".asset-action-column").forEach((column) => {
    column.hidden = !canReadAssets;
  });
  const canReadPlans = hasCapability("plans.read");
  const canWritePlans = hasCapability("plans.write");
  document.querySelector('[data-view="plans"]').hidden = !canReadPlans;
  $("#new-plan-button").hidden = !canWritePlans;
  document.querySelectorAll(".plan-action-column").forEach((column) => {
    column.hidden = !canWritePlans;
  });
  const canReadIncidents = hasCapability("incidents.read");
  const canWriteIncidents = hasCapability("incidents.write");
  document.querySelector('[data-view="incidents"]').hidden =
    !canReadIncidents;
  $("#new-incident-button").hidden = !canWriteIncidents;
  const incidentWriteNote = $("#incident-write-note");
  incidentWriteNote.hidden = !canWriteIncidents || Boolean(state.services);
  incidentWriteNote.textContent = state.services
    ? ""
    : "Puedes registrar incidencias por torre o AP; para asociar servicios se necesita acceso a servicios.";
  document.querySelectorAll(".incident-action-column").forEach((column) => {
    column.hidden = !canReadIncidents;
  });
  const canReadSupport = hasCapability("support.read");
  const canWriteSupport = hasCapability("support.write");
  document.querySelector('[data-view="support"]').hidden = !canReadSupport;
  const canReadNetwork = hasCapability("network.read");
  document.querySelector('[data-view="network"]').hidden = !canReadNetwork;
  $("#sync-uisp-button").hidden = !hasCapability("network.control");
  $("#new-support-ticket-button").hidden = !canWriteSupport;
  $("#support-write-note").hidden = canWriteSupport;
  $("#support-write-note").textContent = canWriteSupport
    ? ""
    : "Esta cuenta puede consultar tickets, pero no registrar nuevos casos.";
  document.querySelectorAll(".support-action-column").forEach((column) => {
    column.hidden = !canReadSupport;
  });
  const canManageUsers = state.user?.role === "administrator";
  document.querySelector('[data-view="users"]').hidden = !canManageUsers;
  $("#new-user-button").hidden = !canManageUsers;
  const usersNote = $("#users-note");
  usersNote.hidden = !canManageUsers;
  usersNote.textContent = canManageUsers
    ? "Solo el administrador puede crear, editar o desactivar cuentas de operadores."
    : "";
  document.querySelectorAll(".service-action-column").forEach(
    (column) => {
      column.hidden = !(
        hasCapability("installations.write") ||
        hasCapability("network.control") ||
        hasCapability("notifications.write") ||
        hasCapability("billing.read") ||
        hasCapability("services.cancel") ||
        hasCapability("assets.read") ||
        hasCapability("assets.write") ||
        hasCapability("services.write")
      );
    }
  );
}

function hasCapability(capability) {
  return (
    state.user?.role === "administrator" ||
    state.user?.permissions?.includes(capability)
  );
}

function renderOverview() {
  const customers = state.customers;
  const services = state.services;
  const suspendedServices = services?.filter((item) => item.status === "suspended") || [];
  const uispAccessPoints = (state.networkDevices || []).filter((item) => item.device_type === "access_point");
  const cpes = (state.networkDevices || []).filter((item) => item.device_type === "station");
  const suspendedDevices = (state.networkDevices || []).filter((item) => item.suspended_in_mikrotik);
  const offlineCpes = cpes.filter((item) => item.current_status === "offline" && !item.suspended_in_mikrotik);
  const offlineAccessPoints = uispAccessPoints.filter((item) => item.current_status === "offline");
  const routers = state.mikrotikHealth || [];
  const onlineRouters = routers.filter((item) => item.status === "online").length;
  const uispConnected = Boolean(state.uispConnection?.connected);
  const metrics = [
    ["UISP", uispConnected ? "Conectado" : "Sin conexión"],
    ["MikroTik", routers.length ? `${onlineRouters}/${routers.length}` : "Sin registrar"],
    ["CPE desconectados", offlineCpes.length],
    ["Equipos bloqueados", suspendedDevices.length],
    ["Servicios suspendidos", suspendedServices.length],
    ["AP en línea", `${uispAccessPoints.length - offlineAccessPoints.length}/${uispAccessPoints.length}`],
    ["Alertas activas", offlineCpes.length + offlineAccessPoints.length],
    ["Clientes", customers?.length],
    ["Servicios totales", services?.length ?? "Sin acceso"],
  ];
  $("#metric-grid").innerHTML = metrics
    .map(([label, value]) => `
      <article class="metric">
        <span>${label}</span>
        <strong>${value ?? "Sin acceso"}</strong>
      </article>
    `)
    .join("");

  if (!services) {
    $("#service-statuses").innerHTML =
      '<p class="empty-state">Tu cuenta no puede consultar servicios.</p>';
  } else {
    const counts = services.reduce((result, item) => {
      result[item.status] = (result[item.status] || 0) + 1;
      return result;
    }, {});
    const total = Math.max(services.length, 1);
    const labels = {
      active: "Activos",
      pending: "Pendientes",
      suspended: "Suspendidos",
      cancelled: "Cancelados",
    };
    $("#service-statuses").innerHTML = Object.entries(labels)
      .map(([key, label]) => {
        const count = counts[key] || 0;
        return `
          <div class="status-row">
            <span>${label}</span>
            <div class="status-bar"><i style="width:${(count / total) * 100}%"></i></div>
            <strong>${count}</strong>
          </div>
        `;
      })
      .join("");
  }
  const apHealth = uispAccessPoints.map((item) => ({
    name: item.display_name,
    ip_address: item.management_ip,
    status: item.current_status,
    observed_age: item.last_seen_at ? new Date(item.last_seen_at).toLocaleString("es-MX") : null,
  }));
  $("#access-point-health").innerHTML = !apHealth.length
    ? '<p class="empty-state">No hay APs registrados para monitorear.</p>'
    : apHealth.map((item) => `
        <div class="ap-health-row ${escapeText(item.status)}">
          <div>
            <strong>${escapeText(item.name)}</strong>
            <span>${escapeText(item.ip_address)}${item.observed_age ? ` · ${escapeText(item.observed_age)}` : ""}</span>
          </div>
          <b>${item.status === "online" ? "En línea" : item.status === "offline" ? "Sin conexión" : item.status === "attention" ? "Verificar" : "Sin lectura"}</b>
        </div>`).join("");
  const alerts = [
    ...offlineCpes.map((item) => ({
      title: `${item.display_name} sin conexión`,
      detail: item.offline_since ? `Desde ${new Date(item.offline_since).toLocaleString("es-MX")}` : "Detectado por UISP",
      status: "offline",
    })),
    ...offlineAccessPoints.map((item) => ({
      title: `${item.display_name} sin conexión`,
      detail: item.offline_since ? `AP sin telemetría desde ${new Date(item.offline_since).toLocaleString("es-MX")}` : "AP sin telemetría en UISP",
      status: "offline",
    })),
  ];
  $("#network-alerts").innerHTML = alerts.length
    ? alerts.slice(0, 5).map((item) => `<div class="ap-health-row ${escapeText(item.status)}"><div><strong>${escapeText(item.title)}</strong><span>${escapeText(item.detail)}</span></div><b>Revisar</b></div>`).join("")
    : '<p class="empty-state success-state">No hay antenas sin conexión a UISP.</p>';
  const suspendedDeviceRows = suspendedDevices.slice(0, 5).map((device) => `
    <div class="ap-health-row suspended">
      <div>
        <strong>${escapeText(device.display_name)}</strong>
        <span>${escapeText(device.management_ip || "Sin IP")} · UISP: ${escapeText(device.current_status)}</span>
      </div>
      <b>Bloqueado en MikroTik</b>
    </div>`).join("");
  const suspendedServiceRows = (services || [])
    .filter((service) => service.status === "suspended")
    .slice(0, 5)
    .map((service) => `
      <div class="ap-health-row suspended">
        <div>
          <strong>${escapeText(service.amr_code)}</strong>
          <span>${escapeText(service.plan_name)} · ${escapeText(service.address)} · Día ${service.payment_day}</span>
        </div>
        <b>Servicio suspendido</b>
      </div>`).join("");
  $("#suspended-services").innerHTML = suspendedDeviceRows || suspendedServiceRows
    ? `${suspendedDeviceRows}${suspendedServiceRows}`
    : '<p class="empty-state success-state">No hay bloqueos en MikroTik ni servicios suspendidos.</p>';
  $("#overview-message").textContent = uispConnected
    ? `UISP conectado · ${state.networkSummary?.online ?? 0} equipos en línea · ${offlineCpes.length} CPE desconectados · ${suspendedDevices.length} bloqueados en MikroTik · ${suspendedServices.length} servicios suspendidos.`
    : "UISP no está disponible en este momento; se conserva la última telemetría recibida.";
  renderTrafficChart();
}

function formatTrafficRate(value) {
  if (value >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(1)} Gbps`;
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)} Mbps`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)} Kbps`;
  return `${Math.round(value)} bps`;
}

function trafficPeriodLabel(period) {
  return {
    "1m": "Último minuto", "5m": "Últimos 5 minutos", "30m": "Últimos 30 minutos",
    "1h": "Última hora", "24h": "Últimas 24 horas", "3d": "Últimos 3 días",
    "7d": "Última semana", "30d": "Último mes", "90d": "Últimos 3 meses",
  }[period] || "Periodo seleccionado";
}

function formatTrafficTime(value, period) {
  const date = new Date(value);
  const options = ["1m", "5m", "30m"].includes(period)
    ? { hour: "2-digit", minute: "2-digit", second: "2-digit" }
    : ["1h", "24h"].includes(period)
      ? { hour: "2-digit", minute: "2-digit" }
      : ["3d", "7d"].includes(period)
        ? { weekday: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }
        : { day: "numeric", month: "short", year: "numeric" };
  return new Intl.DateTimeFormat("es-MX", options).format(date);
}

function renderTrafficChart() {
  const chart = $("#traffic-chart");
  if (!chart) return;
  const points = state.trafficHistory?.points || [];
  document.querySelectorAll("[data-traffic-range]").forEach((button) => {
    button.classList.toggle("active", button.dataset.trafficRange === state.trafficRange);
  });
  if (points.length < 2) {
    chart.innerHTML = '<p class="empty-state">Reuniendo muestras de tráfico. La gráfica aparecerá después de dos minutos.</p>';
    return;
  }
  const maximum = Math.max(1, ...points.flatMap((point) => [point.rx_bps, point.tx_bps]));
  const coordinates = (field) => points.map((point, index) => `${(index / (points.length - 1)) * 100},${96 - (point[field] / maximum) * 88}`).join(" ");
  const latest = points.at(-1);
  const average = (field) => points.reduce((total, point) => total + point[field], 0) / points.length;
  const middle = points[Math.floor((points.length - 1) / 2)];
  const recentRows = points.slice(-6).reverse().map((point) => `
    <tr><td>${formatTrafficTime(point.captured_at, state.trafficRange)}</td><td>${formatTrafficRate(point.tx_bps)}</td><td>${formatTrafficRate(point.rx_bps)}</td></tr>`).join("");
  chart.innerHTML = `
    <div class="traffic-summary">
      <div><span>Actual</span><strong>Tx ${formatTrafficRate(latest.tx_bps)} · Rx ${formatTrafficRate(latest.rx_bps)}</strong></div>
      <div><span>Promedio</span><strong>Tx ${formatTrafficRate(average("tx_bps"))} · Rx ${formatTrafficRate(average("rx_bps"))}</strong></div>
      <div><span>Máximo</span><strong>${formatTrafficRate(maximum)}</strong></div>
      <div><span>Periodo</span><strong>${trafficPeriodLabel(state.trafficRange)}</strong></div>
    </div>
    <div class="traffic-legend"><span class="traffic-tx">Tx · envío</span><span class="traffic-rx">Rx · recepción</span><small>${points.length} muestras · cada minuto</small></div>
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="Tráfico LAN"><polyline class="traffic-grid" points="0,96 100,96"></polyline><polyline class="traffic-line tx" points="${coordinates("tx_bps")}"></polyline><polyline class="traffic-line rx" points="${coordinates("rx_bps")}"></polyline></svg>
    <div class="traffic-axis"><span>${formatTrafficTime(points[0].captured_at, state.trafficRange)}</span><span>${formatTrafficTime(middle.captured_at, state.trafficRange)}</span><span>${formatTrafficTime(latest.captured_at, state.trafficRange)}</span></div>
    <details class="traffic-readings"><summary>Ver lecturas recientes (${Math.min(points.length, 6)})</summary><div class="traffic-table-wrap"><table class="traffic-table"><caption>Fecha y hora según el periodo seleccionado</caption><thead><tr><th>Fecha y hora</th><th>Tx</th><th>Rx</th></tr></thead><tbody>${recentRows}</tbody></table></div></details>`;
}

function upsertDailyOperation(saved) {
  if (!state.dailyOperations) state.dailyOperations = [];
  const index = state.dailyOperations.findIndex(
    (item) => item.run_date === saved.run_date
  );
  if (index >= 0) state.dailyOperations[index] = saved;
  else state.dailyOperations.unshift(saved);
  state.dailyOperations.sort(
    (a, b) => new Date(b.completed_at) - new Date(a.completed_at)
  );
}

function renderDailyOperations() {
  const summary = $("#operations-summary");
  const body = $("#operations-body");
  const empty = $("#operations-empty");
  const runDate = $("#operations-run-date");
  if (!runDate.value) {
    runDate.value = localDateValue();
  }
  if (!state.dailyOperations) {
    summary.innerHTML = "";
    body.innerHTML = "";
    empty.textContent = "Tu cuenta no puede consultar la operación diaria.";
    empty.hidden = false;
    return;
  }
  const latest = state.latestDailyOperationResult || state.dailyOperations[0];
  summary.innerHTML = latest
    ? `
      <div>
        <span>Fecha evaluada</span>
        <strong>${formatDate(latest.run_date)}</strong>
      </div>
      <div>
        <span>Mensualidades</span>
        <strong>${latest.monthly_charges_created}</strong>
      </div>
      <div>
        <span>Prórrogas vencidas</span>
        <strong>${latest.extensions_expired}</strong>
      </div>
      <div>
        <span>Modo</span>
        <strong>${latest.dry_run ? "Simulación" : "Ejecución real"}</strong>
      </div>
      <div>
        <span>Responsable</span>
        <strong>${escapeText(latest.executed_by)}</strong>
      </div>
      <div>
        <span>Cierre</span>
        <strong>${formatDateTime(latest.completed_at)}</strong>
      </div>
    `
    : `
      <div>
        <span>Estado</span>
        <strong>Sin ejecuciones previas</strong>
      </div>
      <div>
        <span>Qué hará</span>
        <strong>Mensualidades y vencimientos</strong>
      </div>
      <div>
        <span>Seguridad</span>
        <strong>Primero puedes simular</strong>
      </div>
    `;
  body.innerHTML = state.dailyOperations
    .map((run) => `
      <tr>
        <td><strong>${formatDate(run.run_date)}</strong></td>
        <td>${run.monthly_charges_created}</td>
        <td>${run.extensions_expired}</td>
        <td>${escapeText(run.executed_by)}</td>
        <td>${formatDateTime(run.completed_at)}</td>
        <td><span class="badge ${run.status}">${escapeText(run.status)}</span></td>
      </tr>
    `)
    .join("");
  empty.textContent = "Aún no hay ejecuciones registradas.";
  empty.hidden = state.dailyOperations.length > 0;
}
