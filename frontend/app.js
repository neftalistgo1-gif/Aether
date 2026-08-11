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
        hasCapability("assets.write")
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
  const payments = state.payments;
  const active = services?.filter((item) => item.status === "active").length;
  const suspended = services?.filter((item) => item.status === "suspended").length;
  const pendingPayments = payments?.filter((item) => item.status === "pending").length;
  const uispAccessPoints = (state.networkDevices || []).filter((item) => item.device_type === "access_point");
  const cpes = (state.networkDevices || []).filter((item) => item.device_type === "station");
  const offlineCpes = cpes.filter((item) => item.current_status === "offline");
  const offlineAccessPoints = uispAccessPoints.filter((item) => item.current_status !== "online").length;
  const routers = state.mikrotikHealth || [];
  const onlineRouters = routers.filter((item) => item.status === "online").length;
  const uispConnected = Boolean(state.uispConnection?.connected);
  const metrics = [
    ["UISP", uispConnected ? "Conectado" : "Sin conexión"],
    ["MikroTik", routers.length ? `${onlineRouters}/${routers.length}` : "Sin registrar"],
    ["CPE desconectados", offlineCpes.length],
    ["AP en línea", `${uispAccessPoints.length - offlineAccessPoints}/${uispAccessPoints.length}`],
    ["Alertas activas", offlineCpes.length + offlineAccessPoints],
    ["Clientes", customers?.length],
    ["Servicios activos", active],
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
    ...uispAccessPoints.filter((item) => item.current_status !== "online").map((item) => ({
      title: `${item.display_name} requiere revisión`,
      detail: item.current_status === "offline" ? "AP sin conexión" : "UISP no tiene lectura actual",
      status: item.current_status,
    })),
    ...routers.filter((item) => item.status !== "online").map((item) => ({
      title: `${item.name} no está disponible`,
      detail: item.status === "disabled" ? "Router deshabilitado" : "No respondió a la comprobación",
      status: item.status,
    })),
  ];
  $("#network-alerts").innerHTML = alerts.length
    ? alerts.slice(0, 5).map((item) => `<div class="ap-health-row ${escapeText(item.status)}"><div><strong>${escapeText(item.title)}</strong><span>${escapeText(item.detail)}</span></div><b>Revisar</b></div>`).join("")
    : '<p class="empty-state success-state">Sin alertas de red activas.</p>';
  $("#overview-message").textContent = uispConnected
    ? `UISP conectado · ${state.networkSummary?.online ?? 0} equipos en línea · ${offlineCpes.length} CPE desconectados.`
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

function assetTypeLabel(value) {
  const labels = {
    antenna: "Antena",
    cpe: "CPE",
    access_point: "Punto de acceso",
    mikrotik: "MikroTik",
    pc: "PC",
    router_modem: "Router o módem",
    poe: "PoE",
    power_supply: "Fuente",
    mast: "Mástil",
    ethernet_cable: "Cable",
    other: "Otro",
  };
  return labels[value] || value;
}

function assetStatusLabel(value) {
  const labels = {
    available: "Disponible",
    quarantine: "Cuarentena",
    needs_repair: "Requiere reparación",
    defective: "Defectuoso",
    ready_for_reuse: "Listo para reutilizar",
    assigned: "Asignado",
    installed: "Instalado",
    discarded: "Descartado",
    not_recovered: "No recuperado",
    sold_to_customer: "Vendido al cliente",
  };
  return labels[value] || value;
}

function assetOwnerLabel(value) {
  return value === "customer" ? "Cliente" : "AMR";
}

function selectedAsset() {
  return state.assets?.find((item) => item.id === state.selectedAssetId);
}

function renderAssets() {
  const body = $("#assets-body");
  const empty = $("#assets-empty");
  if (!state.assets) {
    body.innerHTML = "";
    empty.textContent = "Tu cuenta no puede consultar activos.";
    empty.hidden = false;
    return;
  }
  const query = $("#asset-search")?.value.trim().toLowerCase() || "";
  const statusFilter = $("#asset-status-filter")?.value || "";
  const rows = state.assets.filter((asset) => {
    const matchesQuery = !query || [
      asset.internal_code,
      asset.description,
      asset.serial_number || "",
      asset.mac_address || "",
    ].join(" ").toLowerCase().includes(query);
    const matchesStatus = !statusFilter || asset.status === statusFilter;
    return matchesQuery && matchesStatus;
  });
  body.innerHTML = rows
    .slice()
    .sort((a, b) => a.internal_code.localeCompare(b.internal_code))
    .map((asset) => `
      <tr>
        <td>
          <strong>${escapeText(asset.internal_code)}</strong>
          <small class="table-subtitle">${escapeText(asset.description)}</small>
        </td>
        <td>${escapeText(assetTypeLabel(asset.asset_type))}</td>
        <td>
          ${escapeText(asset.serial_number || asset.mac_address || "Sin serie o MAC")}
          <small class="table-subtitle">${escapeText(asset.brand || "Sin marca")} · ${escapeText(asset.model || "Sin modelo")}</small>
        </td>
        <td>${escapeText(assetOwnerLabel(asset.owner))}</td>
        <td><span class="badge ${asset.status}">${escapeText(assetStatusLabel(asset.status))}</span></td>
        <td>
          <button
            class="row-action view-asset"
            type="button"
            data-asset-id="${asset.id}"
          >Detalle</button>
        </td>
      </tr>
    `)
    .join("");
  empty.textContent = query || statusFilter
    ? "No hay activos que coincidan con el filtro actual."
    : "Aún no hay activos registrados.";
  empty.hidden = rows.length > 0;
}

function openAssetDialog() {
  $("#asset-type").value = "antenna";
  $("#asset-owner").value = "amr";
  $("#asset-description").value = "";
  $("#asset-brand").value = "";
  $("#asset-model").value = "";
  $("#asset-serial-number").value = "";
  $("#asset-mac-address").value = "";
  $("#asset-acquired-on").value = localDateValue();
  $("#asset-notes").value = "";
  $("#asset-form-error").textContent = "";
  $("#asset-dialog").showModal();
  $("#asset-description").focus();
}

function closeAssetDialog() {
  $("#asset-dialog").close();
}

async function saveAsset(event) {
  event.preventDefault();
  const submitButton = event.currentTarget.querySelector('button[type="submit"]');
  const errorBox = $("#asset-form-error");
  submitButton.disabled = true;
  errorBox.textContent = "";
  try {
    const saved = await api("/api/v1/assets", {
      method: "POST",
      body: JSON.stringify({
        asset_type: $("#asset-type").value,
        description: $("#asset-description").value.trim(),
        brand: $("#asset-brand").value.trim() || null,
        model: $("#asset-model").value.trim() || null,
        serial_number: $("#asset-serial-number").value.trim() || null,
        mac_address: $("#asset-mac-address").value.trim() || null,
        owner: $("#asset-owner").value,
        acquired_on: $("#asset-acquired-on").value || null,
        notes: $("#asset-notes").value.trim() || null,
      }),
    });
    if (!state.assets) state.assets = [];
    state.assets.push(saved);
    renderAssets();
    closeAssetDialog();
    setNotice(`Activo registrado: ${saved.internal_code}.`);
  } catch (error) {
    errorBox.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

function renderAssetWorkspace(asset) {
  const activeAssignment = state.selectedAssetAssignments.find(
    (item) => item.returned_at === null
  );
  const activeServices = (state.services || []).filter(
    (service) => service.status === "active"
  );
  $("#asset-detail-title").textContent = asset.internal_code;
  $("#asset-detail-summary").innerHTML = `
    <div>
      <span>Tipo</span>
      <strong>${escapeText(assetTypeLabel(asset.asset_type))}</strong>
    </div>
    <div>
      <span>Estado</span>
      <strong>${escapeText(assetStatusLabel(asset.status))}</strong>
    </div>
    <div>
      <span>Propiedad</span>
      <strong>${escapeText(assetOwnerLabel(asset.owner))}</strong>
    </div>
    <div>
      <span>Serie</span>
      <strong>${escapeText(asset.serial_number || "Sin serie")}</strong>
    </div>
    <div>
      <span>MAC</span>
      <strong>${escapeText(asset.mac_address || "Sin MAC")}</strong>
    </div>
    <div>
      <span>Adquirido</span>
      <strong>${formatDate(asset.acquired_on)}</strong>
    </div>
  `;
  $("#asset-detail-workspace").innerHTML = `
    ${hasCapability("assets.write") && !activeAssignment && ["available", "ready_for_reuse"].includes(asset.status) ? `
      <form id="asset-assign-form" class="cancellation-stage-card">
        <h3>Asignar a servicio activo</h3>
        <div class="form-grid">
          <label>
            Servicio
            <select id="asset-assign-service" required>
              ${activeServices.map((service) => `
                <option value="${service.id}">
                  ${escapeText(service.amr_code)} · ${escapeText(service.plan_name)}
                </option>
              `).join("")}
            </select>
          </label>
          <label>
            Asignó
            <input id="asset-assigned-by" value="${escapeText(state.user.display_name)}" minlength="2" maxlength="150" required>
          </label>
          <label class="full-row">
            Condición de entrega
            <textarea id="asset-condition-delivery" rows="2" minlength="3" maxlength="2000" required></textarea>
          </label>
          <label class="full-row">
            Notas
            <textarea id="asset-assignment-notes" rows="2" maxlength="1000"></textarea>
          </label>
          <div class="dialog-actions full-row">
            <button class="primary-button" type="submit" ${activeServices.length ? "" : "disabled"}>Asignar activo</button>
          </div>
        </div>
      </form>
    ` : ""}
    ${hasCapability("assets.write") && activeAssignment ? `
      <form id="asset-return-form" class="cancellation-stage-card" data-service-id="${activeAssignment.service_id}" data-assignment-id="${activeAssignment.id}">
        <h3>Registrar devolución</h3>
        <div class="form-grid">
          <label>
            Devolvió
            <input id="asset-returned-by" value="${escapeText(state.user.display_name)}" minlength="2" maxlength="150" required>
          </label>
          <label>
            Resultado
            <select id="asset-return-outcome" required>
              <option value="recovered">Recuperado</option>
              <option value="not_recovered">No recuperado</option>
              <option value="sold_to_customer">Vendido al cliente</option>
            </select>
          </label>
          <label class="full-row">
            Condición de retorno
            <textarea id="asset-condition-return" rows="2" minlength="3" maxlength="2000" required></textarea>
          </label>
          <label class="full-row">
            Notas
            <textarea id="asset-return-notes" rows="2" maxlength="1000"></textarea>
          </label>
          <div class="dialog-actions full-row">
            <button class="primary-button" type="submit">Registrar devolución</button>
          </div>
        </div>
      </form>
    ` : ""}
    <section class="cancellation-stage-card">
      <div class="stage-status">
        <h3>Historial de asignaciones</h3>
        <span class="badge ${asset.status}">${escapeText(assetStatusLabel(asset.status))}</span>
      </div>
      <div class="extension-history">
        ${state.selectedAssetAssignments.length ? state.selectedAssetAssignments.map((assignment) => {
          const service = state.services?.find((item) => item.id === assignment.service_id);
          return `
            <article class="history-item">
              <div>
                <strong>${escapeText(service ? `${service.amr_code} · ${service.plan_name}` : assignment.service_id)}</strong>
                <span>${assignment.returned_at ? 'Cerrada' : 'Activa'}</span>
              </div>
              <small>
                Entregada ${formatDateTime(assignment.assigned_at)} por ${escapeText(assignment.assigned_by)}
              </small>
              <small>${escapeText(assignment.condition_on_delivery)}</small>
              <small>
                ${assignment.returned_at
                  ? `Devuelta ${formatDateTime(assignment.returned_at)} · ${escapeText(assignment.return_outcome || '')}`
                  : 'Pendiente de devolución'}
              </small>
            </article>
          `;
        }).join("") : '<p class="empty-state">Este activo aún no tiene asignaciones.</p>'}
      </div>
    </section>
  `;
}

async function openAssetDetailDialog(asset) {
  state.selectedAssetId = asset.id;
  state.selectedAssetAssignments = [];
  $("#asset-detail-error").textContent = "";
  $("#asset-detail-summary").innerHTML = "";
  $("#asset-detail-workspace").innerHTML = '<p class="empty-state">Cargando historial del activo...</p>';
  $("#asset-detail-dialog").showModal();
  try {
    state.selectedAssetAssignments = await api(`/api/v1/assets/${asset.id}/assignments`);
    renderAssetWorkspace(asset);
  } catch (error) {
    $("#asset-detail-error").textContent = error.message;
  }
}

function closeAssetDetailDialog() {
  $("#asset-detail-dialog").close();
  state.selectedAssetId = null;
  state.selectedAssetAssignments = [];
}

async function assignSelectedAsset(event) {
  event.preventDefault();
  const asset = selectedAsset();
  const errorBox = $("#asset-detail-error");
  const submitButton = event.currentTarget.querySelector('button[type="submit"]');
  if (!asset) return;
  submitButton.disabled = true;
  errorBox.textContent = "";
  try {
    await api(`/api/v1/services/${$("#asset-assign-service").value}/asset-assignments`, {
      method: "POST",
      body: JSON.stringify({
        asset_id: asset.id,
        assigned_by: $("#asset-assigned-by").value.trim(),
        condition_on_delivery: $("#asset-condition-delivery").value.trim(),
        notes: $("#asset-assignment-notes").value.trim() || null,
      }),
    });
    state.assets = await loadResource("/api/v1/assets");
    renderAssets();
    const updated = selectedAsset();
    if (updated) {
      state.selectedAssetAssignments = await api(`/api/v1/assets/${updated.id}/assignments`);
      renderAssetWorkspace(updated);
    }
    setNotice(`Activo ${asset.internal_code} asignado correctamente.`);
  } catch (error) {
    errorBox.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

async function returnSelectedAsset(event) {
  event.preventDefault();
  const asset = selectedAsset();
  const form = event.currentTarget;
  const errorBox = $("#asset-detail-error");
  const submitButton = form.querySelector('button[type="submit"]');
  if (!asset) return;
  submitButton.disabled = true;
  errorBox.textContent = "";
  try {
    await api(
      `/api/v1/services/${form.dataset.serviceId}/asset-assignments/${form.dataset.assignmentId}/return`,
      {
        method: "POST",
        body: JSON.stringify({
          returned_by: $("#asset-returned-by").value.trim(),
          condition_on_return: $("#asset-condition-return").value.trim(),
          outcome: $("#asset-return-outcome").value,
          notes: $("#asset-return-notes").value.trim() || null,
        }),
      }
    );
    state.assets = await loadResource("/api/v1/assets");
    renderAssets();
    const updated = selectedAsset();
    if (updated) {
      state.selectedAssetAssignments = await api(`/api/v1/assets/${updated.id}/assignments`);
      renderAssetWorkspace(updated);
    }
    setNotice(`Devolución registrada para ${asset.internal_code}.`);
  } catch (error) {
    errorBox.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

function setDailyOperationsBusy(busy) {
  [
    $("#preview-daily-operations-button"),
    $("#run-daily-operations-button"),
    $("#operations-run-date"),
  ].forEach((element) => {
    if (element) element.disabled = busy;
  });
}

async function runDailyOperations(dryRun) {
  const runDate = $("#operations-run-date").value;
  if (!runDate) {
    setNotice("Selecciona una fecha válida para la operación diaria.");
    return;
  }
  setDailyOperationsBusy(true);
  try {
    const result = await api("/api/v1/operations/daily", {
      method: "POST",
      body: JSON.stringify({
        run_date: runDate,
        dry_run: dryRun,
      }),
    });
    state.latestDailyOperationResult = result;
    if (!dryRun) {
      upsertDailyOperation(result);
    }
    renderDailyOperations();
    setNotice(
      dryRun
        ? `Simulación lista: ${result.monthly_charges_created} mensualidades y ${result.extensions_expired} prórrogas vencidas.`
        : `Operación diaria ejecutada: ${result.monthly_charges_created} mensualidades y ${result.extensions_expired} prórrogas vencidas.`
    );
  } catch (error) {
    setNotice(error.message);
  } finally {
    setDailyOperationsBusy(false);
  }
}

function renderCustomers(query = "") {
  const body = $("#customers-body");
  const empty = $("#customers-empty");
  const summary = $("#customer-summary");
  if (!state.customers) {
    body.innerHTML = "";
    empty.textContent = "Tu cuenta no puede consultar clientes.";
    empty.hidden = false;
    if (summary) summary.innerHTML = "";
    return;
  }
  const normalized = query.trim().toLowerCase();
  const rows = state.customers.filter((customer) =>
    [customer.full_name, ...(customer.phones || [])]
      .join(" ")
      .toLowerCase()
      .includes(normalized)
  );
  const canWrite = hasCapability("customers.write");
  const canReadBilling = hasCapability("billing.read");
  const canShowActions = canWrite || canReadBilling;
  const totalCustomers = state.customers.length;
  const filteredCount = rows.length;
  const withPhones = state.customers.filter((customer) => (customer.phones || []).length > 0).length;
  const withEmail = state.customers.filter((customer) => Boolean(customer.email)).length;
  if (summary) {
    summary.innerHTML = `
      <span class="summary-chip">Total: <strong>${totalCustomers}</strong></span>
      <span class="summary-chip">Con teléfono: <strong>${withPhones}</strong></span>
      <span class="summary-chip">Con correo: <strong>${withEmail}</strong></span>
      ${normalized ? `<span class="summary-chip">Resultados: <strong>${filteredCount}</strong></span>` : ""}
    `;
  }
  body.innerHTML = rows
    .map((customer) => `
      <tr>
        <td><strong>${escapeText(customer.full_name)}</strong></td>
        <td>${escapeText(customer.phones?.[0] || "—")}</td>
        <td>${escapeText(customer.email || "—")}</td>
        <td>${formatDate(customer.registered_at)}</td>
        ${canShowActions ? `
          <td>
            ${canReadBilling ? `
              <button
                class="row-action view-account"
                type="button"
                data-customer-id="${customer.id}"
              >Estado de cuenta</button>
            ` : ""}
            ${canWrite ? `
              <button
                class="row-action edit-customer"
                type="button"
                data-customer-id="${customer.id}"
              >Editar</button>
            ` : ""}
          </td>
        ` : ""}
      </tr>
    `)
    .join("");
  empty.textContent = normalized
    ? "No hay clientes que coincidan con la búsqueda."
    : "Aún no hay clientes registrados.";
  empty.hidden = rows.length > 0;
}

function openCustomerDialog(customer = null) {
  state.editingCustomerId = customer?.id || null;
  $("#customer-dialog-title").textContent = customer
    ? "Editar cliente"
    : "Nuevo cliente";
  $("#customer-name").value = customer?.full_name || "";
  $("#customer-phones").value = customer?.phones?.join("\n") || "";
  $("#customer-email").value = customer?.email || "";
  $("#customer-notes").value = customer?.notes || "";
  $("#customer-reason").value = "";
  $("#customer-form-error").textContent = "";
  const reasonField = $("#customer-reason-field");
  reasonField.hidden = !customer;
  $("#customer-reason").required = Boolean(customer);
  $("#customer-dialog").showModal();
  $("#customer-name").focus();
}

function closeCustomerDialog() {
  $("#customer-dialog").close();
  state.editingCustomerId = null;
}

function customerPayload() {
  const phones = $("#customer-phones").value
    .split(/[\n,;]+/)
    .map((phone) => phone.trim())
    .filter(Boolean);
  if (!phones.length) {
    throw new Error("Registra al menos un teléfono.");
  }
  return {
    full_name: $("#customer-name").value.trim(),
    phones,
    email: $("#customer-email").value.trim() || null,
    notes: $("#customer-notes").value.trim() || null,
  };
}

async function saveCustomer(event) {
  event.preventDefault();
  const submitButton = event.currentTarget.querySelector(
    'button[type="submit"]'
  );
  const errorBox = $("#customer-form-error");
  submitButton.disabled = true;
  errorBox.textContent = "";
  try {
    const editing = Boolean(state.editingCustomerId);
    const formValues = customerPayload();
    let payload = formValues;
    if (editing) {
      const original = state.customers.find(
        (item) => item.id === state.editingCustomerId
      );
      const changes = Object.fromEntries(
        Object.entries(formValues).filter(([key, value]) => {
          const previous = original[key];
          return Array.isArray(value)
            ? JSON.stringify(value) !== JSON.stringify(previous)
            : value !== previous;
        })
      );
      if (!Object.keys(changes).length) {
        throw new Error("No hay cambios para guardar.");
      }
      payload = {
        ...changes,
        reason: $("#customer-reason").value.trim(),
      };
    }
    const saved = await api(
      editing
        ? `/api/v1/customers/${state.editingCustomerId}`
        : "/api/v1/customers",
      {
        method: editing ? "PATCH" : "POST",
        body: JSON.stringify(payload),
      }
    );
    if (state.customers) {
      const index = state.customers.findIndex((item) => item.id === saved.id);
      if (index === -1) state.customers.push(saved);
      else state.customers[index] = saved;
      renderCustomers($("#customer-search").value);
      renderOverview();
    }
    closeCustomerDialog();
    setNotice(
      editing
        ? "Los datos del cliente se actualizaron correctamente."
        : "El cliente quedó registrado correctamente."
    );
  } catch (error) {
    errorBox.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

function renderServices() {
  const body = $("#services-body");
  const empty = $("#services-empty");
  if (!state.services) {
    body.innerHTML = "";
    empty.textContent = "Tu cuenta no puede consultar servicios.";
    empty.hidden = false;
    return;
  }
  const canScheduleInstallation = hasCapability("installations.write");
  const canControlNetwork = hasCapability("network.control");
  const canWriteNotifications = hasCapability("notifications.write");
  const canCheckSuspension = (
    hasCapability("network.control") &&
    hasCapability("billing.read") &&
    hasCapability("notifications.read")
  );
  const canCheckReactivation = (
    hasCapability("network.control") &&
    hasCapability("billing.read")
  );
  const canReadExtensions = hasCapability("billing.read");
  const canCancelServices = hasCapability("services.cancel");
  const canManageRecovery = (
    hasCapability("assets.read") ||
    hasCapability("assets.write")
  );
  const canShowActions = (
    canScheduleInstallation ||
    canControlNetwork ||
    canWriteNotifications ||
    canCheckSuspension ||
    canCheckReactivation ||
    canReadExtensions ||
    canCancelServices ||
    canManageRecovery
  );
  body.innerHTML = state.services
    .map((service) => `
      <tr>
        <td><strong>${escapeText(service.amr_code)}</strong></td>
        <td>${escapeText(service.plan_name)}</td>
        <td>
          ${escapeText(service.address)}
          <small class="table-subtitle">
            ${service.current_customer_id ? "Titular enlazado" : "Pendiente de titular"}
          </small>
        </td>
        <td>Día ${service.payment_day} · ${formatMoney(service.monthly_price)}</td>
        <td><span class="badge ${service.status}">${escapeText(service.status)}</span></td>
        ${canShowActions ? `
          <td>
            ${canScheduleInstallation && service.status === "pending" ? `
              <button
                class="row-action assess-installation"
                type="button"
                data-service-id="${service.id}"
              >${service.has_scheduled_installation
                ? "Ver instalación"
                : "Cobertura y agenda"}</button>
            ` : ""}
            ${canControlNetwork && ["active", "suspended"].includes(service.status) ? `
              <button
                class="row-action simulate-network-control"
                type="button"
                data-service-id="${service.id}"
              >Simular ${service.status === "active" ? "suspensión" : "reactivación"}</button>
              <button
                class="row-action reconcile-network"
                type="button"
                data-service-id="${service.id}"
              >Revisar red</button>
            ` : ""}
            ${canWriteNotifications ? `
              <button
                class="row-action record-notification"
                type="button"
                data-service-id="${service.id}"
              >Registrar aviso</button>
            ` : ""}
            ${canCheckSuspension && service.status === "active" ? `
              <button
                class="row-action check-commercial-suspension"
                type="button"
                data-service-id="${service.id}"
              >Validar suspensión</button>
            ` : ""}
            ${canCheckReactivation && service.status === "suspended" ? `
              <button
                class="row-action check-commercial-reactivation"
                type="button"
                data-service-id="${service.id}"
              >Validar reactivación</button>
            ` : ""}
            ${canReadExtensions ? `
              <button
                class="row-action manage-extensions"
                type="button"
                data-service-id="${service.id}"
              >Prórrogas</button>
              <button
                class="row-action manage-payment-agreements"
                type="button"
                data-service-id="${service.id}"
              >Convenios</button>
            ` : ""}
            ${(canCancelServices || (
              canManageRecovery && service.status === "cancelled"
            )) ? `
              <button
                class="row-action manage-cancellation"
                type="button"
                data-service-id="${service.id}"
              >Baja y retiro</button>
            ` : ""}
          </td>
        ` : ""}
      </tr>
    `)
    .join("");
  empty.textContent = "Aún no hay servicios registrados.";
  empty.hidden = state.services.length > 0;
}

function updateSelectedPlanPrice() {
  const plan = state.plans?.find(
    (item) => item.id === $("#service-plan").value
  );
  $("#service-plan-price").textContent = plan
    ? formatMoney(plan.current_price)
    : "—";
}

function renderServiceCustomerOptions(query = "") {
  const customerSelect = $("#service-customer");
  const customers = state.customers || [];
  const normalized = query.trim().toLowerCase();
  const filtered = customers.filter((customer) =>
    [customer.full_name, ...(customer.phones || [])]
      .join(" ")
      .toLowerCase()
      .includes(normalized)
  );
  customerSelect.innerHTML = [
    '<option value="">Sin titular por ahora</option>',
    ...(filtered.length
      ? filtered.map(
          (customer) =>
            `<option value="${customer.id}">${escapeText(
              customer.full_name
            )}</option>`
        )
      : ['<option value="" disabled>No hay clientes coincidentes</option>']),
  ].join("");
  customerSelect.disabled = false;
}

async function updatePostalCodeFields() {
  const postalCode = $("#service-postal-code").value.trim();
  const cityField = $("#service-city");
  const municipalityField = $("#service-municipality");
  const stateField = $("#service-state");
  const colonySelect = $("#service-colonia");

  cityField.value = "";
  municipalityField.value = "";
  stateField.value = "";
  colonySelect.innerHTML =
    '<option value="" disabled selected>Ingresa código postal</option>';
  colonySelect.disabled = true;

  if (!/^\d{5}$/.test(postalCode)) {
    return;
  }

  const matches = await api(
    `/api/v1/postal-codes?q=${encodeURIComponent(postalCode)}`
  );
  if (!matches.length) {
    colonySelect.innerHTML =
      '<option value="" disabled selected>No hay colonias para ese código postal</option>';
    return;
  }

  const first = matches[0];
  cityField.value = first.city || "";
  municipalityField.value = first.municipality || "";
  stateField.value = first.state || "";
  colonySelect.disabled = false;
  colonySelect.innerHTML = [
    '<option value="" disabled selected>Selecciona colonia</option>',
    ...matches.map(
      (item) =>
        `<option value="${escapeText(item.settlement_name)}">${escapeText(
          item.settlement_name
        )} (${escapeText(item.settlement_type || "Colonia")})</option>`
    ),
  ].join("");
}

function composeServiceAddress() {
  const street = $("#service-street").value.trim();
  const postalCode = $("#service-postal-code").value.trim();
  const settlement = $("#service-colonia").value;
  const city = $("#service-city").value.trim();
  const municipality = $("#service-municipality").value.trim();
  const state = $("#service-state").value.trim();

  if (
    !street ||
    !postalCode ||
    !settlement ||
    !city ||
    !municipality ||
    !state
  ) {
    throw new Error(
      "Completa el domicilio de instalación con código postal válido, colonia y calle."
    );
  }

  return `${street}, ${settlement}, ${city}, ${municipality}, ${state} ${postalCode}`;
}

function openServiceDialog() {
  const plans = (state.plans || []).filter(
    (plan) => plan.status === "active" && plan.current_price !== null
  );
  $("#service-customer-search").value = "";
  renderServiceCustomerOptions();
  $("#service-plan").innerHTML = plans
    .map(
      (plan) =>
        `<option value="${plan.id}">${escapeText(plan.name)} · ${escapeText(plan.speed)}</option>`
    )
    .join("");
  $("#service-amr").value = "";
  $("#service-postal-code").value = "";
  $("#service-colonia").innerHTML =
    '<option value="" disabled selected>Ingresa código postal</option>';
  $("#service-colonia").disabled = true;
  $("#service-street").value = "";
  $("#service-city").value = "";
  $("#service-municipality").value = "";
  $("#service-state").value = "";
  $("#service-payment-day").value = "5";
  $("#service-grace-days").value = "5";
  $("#service-reason").value = "Alta solicitada por el cliente";
  $("#service-form-error").textContent = "";
  updateSelectedPlanPrice();
  $("#service-dialog").showModal();
  $("#service-amr").focus();
}

function closeServiceDialog() {
  $("#service-dialog").close();
}

async function saveService(event) {
  event.preventDefault();
  const submitButton = event.currentTarget.querySelector(
    'button[type="submit"]'
  );
  const errorBox = $("#service-form-error");
  submitButton.disabled = true;
  errorBox.textContent = "";
  try {
    const plan = state.plans.find(
      (item) => item.id === $("#service-plan").value
    );
    if (!plan?.current_price) {
      throw new Error("Selecciona un plan activo con precio vigente.");
    }
    const saved = await api("/api/v1/services", {
      method: "POST",
      body: JSON.stringify({
        customer_id: $("#service-customer").value || null,
        plan_id: plan.id,
        amr_code: $("#service-amr").value.trim().toUpperCase(),
        address: composeServiceAddress(),
        plan_name: plan.name,
        monthly_price: plan.current_price,
        payment_day: Number($("#service-payment-day").value),
        grace_days: Number($("#service-grace-days").value),
        registered_by: state.user.display_name,
        reason: $("#service-reason").value.trim(),
      }),
    });
    if (state.services) {
      state.services.push(saved);
      state.services.sort((a, b) => a.amr_code.localeCompare(b.amr_code));
      renderServices();
      renderOverview();
    }
    closeServiceDialog();
    setNotice("El servicio quedó registrado como pendiente.");
  } catch (error) {
    errorBox.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

function updateInstallationFields() {
  const result = $("#installation-coverage-result").value;
  const rejected = result === "out_of_coverage";
  const special = result === "special_equipment";
  $("#installation-date-field").hidden = rejected;
  $("#installation-cost-field").hidden = rejected;
  $("#installation-scheduled-for").required = !rejected;
  $("#installation-cost").required = !rejected;
  $("#installation-special-equipment-field").hidden = !special;
  $("#installation-special-equipment").required = special;
  if (rejected) $("#installation-cost").value = "0";
}

async function openInstallationDialog(service) {
  if (hasCapability("installations.read")) {
    try {
      const installations = await api(
        `/api/v1/services/${service.id}/installations`
      );
      if (installations.some((item) => item.status === "scheduled")) {
        const scheduled = installations.find(
          (item) => item.status === "scheduled"
        );
        service.has_scheduled_installation = true;
        renderServices();
        openInstallationManageDialog(service, scheduled);
        return;
      }
    } catch (error) {
      setNotice(error.message);
      return;
    }
  }
  state.selectedServiceId = service.id;
  $("#installation-dialog-title").textContent =
    `Evaluar instalación · ${service.amr_code}`;
  $("#installation-coverage-result").value = "viable";
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  $("#installation-scheduled-for").value = localDateValue(tomorrow);
  $("#installation-cost").value = "0";
  $("#installation-special-equipment").value = "";
  $("#installation-notes").value = "";
  $("#installation-form-error").textContent = "";
  updateInstallationFields();
  $("#installation-dialog").showModal();
  $("#installation-coverage-result").focus();
}

function closeInstallationDialog() {
  $("#installation-dialog").close();
  state.selectedServiceId = null;
}

function openInstallationManageDialog(service, installation) {
  state.selectedServiceId = service.id;
  state.selectedInstallation = installation;
  $("#installation-manage-dialog-title").textContent =
    `Instalación · ${service.amr_code}`;
  $("#installation-manage-summary").innerHTML = `
    <div>
      <span>Fecha programada</span>
      <strong>${formatDate(installation.scheduled_for)}</strong>
    </div>
    <div>
      <span>Costo</span>
      <strong>${formatMoney(installation.cost)}</strong>
    </div>
    <div>
      <span>Cargo</span>
      <strong>${installation.charge_id ? "Generado" : "Sin cargo"}</strong>
    </div>
  `;
  $("#installation-new-date").value = installation.scheduled_for;
  $("#installation-change-reason").value = "";
  $("#installation-manage-error").textContent = "";
  $("#installation-manage-dialog").showModal();
}

function closeInstallationManageDialog() {
  $("#installation-manage-dialog").close();
  state.selectedServiceId = null;
  state.selectedInstallation = null;
}

function setInstallationManageBusy(busy) {
  $("#installation-manage-form")
    .querySelectorAll("button")
    .forEach((button) => {
      button.disabled = busy;
    });
}

async function rescheduleSelectedInstallation(event) {
  event.preventDefault();
  const installation = state.selectedInstallation;
  const serviceId = state.selectedServiceId;
  const errorBox = $("#installation-manage-error");
  if (!installation || !serviceId) return;
  errorBox.textContent = "";
  setInstallationManageBusy(true);
  try {
    const saved = await api(
      `/api/v1/services/${serviceId}/installations/${installation.id}/reschedule`,
      {
        method: "POST",
        body: JSON.stringify({
          new_date: $("#installation-new-date").value,
          changed_by: state.user.display_name,
          reason: $("#installation-change-reason").value.trim(),
        }),
      }
    );
    state.selectedInstallation = saved;
    closeInstallationManageDialog();
    setNotice(
      "La instalación fue reprogramada y el historial quedó conservado."
    );
  } catch (error) {
    errorBox.textContent = error.message;
  } finally {
    setInstallationManageBusy(false);
  }
}

async function cancelSelectedInstallation() {
  const installation = state.selectedInstallation;
  const serviceId = state.selectedServiceId;
  const reason = $("#installation-change-reason").value.trim();
  const errorBox = $("#installation-manage-error");
  if (!installation || !serviceId) return;
  errorBox.textContent = "";
  if (reason.length < 3) {
    errorBox.textContent =
      "Escribe un motivo de al menos tres caracteres.";
    return;
  }
  setInstallationManageBusy(true);
  try {
    await api(
      `/api/v1/services/${serviceId}/installations/${installation.id}/cancel`,
      {
        method: "POST",
        body: JSON.stringify({
          cancelled_by: state.user.display_name,
          reason,
        }),
      }
    );
    const service = state.services?.find((item) => item.id === serviceId);
    if (service) service.has_scheduled_installation = false;
    renderServices();
    closeInstallationManageDialog();
    setNotice(
      "La instalación y su cargo sin aplicaciones fueron cancelados."
    );
  } catch (error) {
    errorBox.textContent = error.message;
  } finally {
    setInstallationManageBusy(false);
  }
}

function evidenceLines(selector) {
  return $(selector).value
    .split(/\n+/)
    .map((value) => value.trim())
    .filter(Boolean);
}

function clearRecoveryEvidencePreview() {
  for (const url of state.recoveryEvidencePreviewUrls) {
    URL.revokeObjectURL(url);
  }
  state.recoveryEvidencePreviewUrls = [];
  const preview = $("#recovery-evidence-preview");
  if (preview) {
    preview.hidden = true;
    preview.innerHTML = "";
  }
}

function renderRecoveryEvidencePreview() {
  const fileInput = $("#recovery-evidence-images");
  const preview = $("#recovery-evidence-preview");
  if (!fileInput || !preview) return;

  clearRecoveryEvidencePreview();

  const files = Array.from(fileInput.files || []);
  if (!files.length) {
    return;
  }

  const urls = [];
  const cards = files.map((file) => {
    const objectUrl = URL.createObjectURL(file);
    urls.push(objectUrl);
    const safeName = escapeText(file.name);
    const safeType = escapeText(file.type || "imagen");
    const sizeKb = Math.max(1, Math.round(file.size / 1024));
    return `
      <article class="evidence-image-card">
        <img src="${objectUrl}" alt="Vista previa de ${safeName}">
        <div>
          <strong>${safeName}</strong>
          <small>${safeType} · ${sizeKb} KB</small>
        </div>
      </article>
    `;
  });

  state.recoveryEvidencePreviewUrls = urls;
  preview.innerHTML = cards.join("");
  preview.hidden = false;
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error("No fue posible leer una imagen adjunta."));
    reader.readAsDataURL(file);
  });
}

async function buildRecoveryEvidenceReferences() {
  const manualReferences = textLines($("#recovery-evidence").value);
  const imageFiles = Array.from(
    $("#recovery-evidence-images")?.files || []
  );
  if (imageFiles.length > MAX_RECOVERY_EVIDENCE_IMAGES) {
    throw new Error("Adjunta hasta seis imágenes de evidencia por visita.");
  }

  const imageReferences = [];
  for (const file of imageFiles) {
    if (!file.type.startsWith("image/")) {
      throw new Error("Solo se permiten archivos de imagen como evidencia.");
    }
    if (file.size > MAX_RECOVERY_EVIDENCE_IMAGE_BYTES) {
      throw new Error("Cada imagen debe pesar como máximo 2 MB.");
    }
    const dataUrl = await readFileAsDataUrl(file);
    const safeName = file.name.trim().replaceAll("|", "-") || "evidencia";
    imageReferences.push(
      `image:${safeName}|${file.type}|${file.size}|${dataUrl}`
    );
  }

  const references = [...manualReferences, ...imageReferences];
  if (references.length > MAX_RECOVERY_EVIDENCE_REFERENCES) {
    throw new Error("La visita acepta hasta 20 evidencias en total.");
  }
  return references;
}

function openInstallationCompleteDialog() {
  const service = state.services?.find(
    (item) => item.id === state.selectedServiceId
  );
  if (!service || !state.selectedInstallation) return;
  $("#installation-manage-dialog").close();
  $("#installation-complete-dialog-title").textContent =
    `Completar · ${service.amr_code}`;
  $("#installation-completed-at").value = localDateTimeValue();
  $("#installation-navigation-by").value = "";
  $("#installation-technicians").value = "";
  $("#installation-antenna-photos").value = "";
  $("#installation-modem-photos").value = "";
  $("#installation-navigation-confirmed").checked = false;
  $("#installation-complete-notes").value = "";
  $("#installation-complete-error").textContent = "";
  $("#installation-complete-dialog").showModal();
  $("#installation-navigation-by").focus();
}

function returnToInstallationManageDialog() {
  const service = state.services?.find(
    (item) => item.id === state.selectedServiceId
  );
  const installation = state.selectedInstallation;
  $("#installation-complete-dialog").close();
  if (service && installation) {
    openInstallationManageDialog(service, installation);
  }
}

async function completeSelectedInstallation(event) {
  event.preventDefault();
  const installation = state.selectedInstallation;
  const serviceId = state.selectedServiceId;
  const service = state.services?.find((item) => item.id === serviceId);
  const submitButton = event.currentTarget.querySelector(
    'button[type="submit"]'
  );
  const errorBox = $("#installation-complete-error");
  if (!installation || !serviceId || !service) return;
  const technicians = evidenceLines("#installation-technicians");
  const antennaPhotos = evidenceLines("#installation-antenna-photos");
  const modemPhotos = evidenceLines("#installation-modem-photos");
  if (technicians.length < 1 || technicians.length > 3) {
    errorBox.textContent = "Registra entre uno y tres técnicos.";
    return;
  }
  if (antennaPhotos.length < 2 || antennaPhotos.length > 4) {
    errorBox.textContent =
      "Registra entre dos y cuatro referencias de la antena.";
    return;
  }
  if (modemPhotos.length < 1 || modemPhotos.length > 4) {
    errorBox.textContent =
      "Registra entre una y cuatro referencias del módem.";
    return;
  }
  const completedAt = new Date($("#installation-completed-at").value);
  if (Number.isNaN(completedAt.getTime())) {
    errorBox.textContent = "Indica una fecha y hora válidas.";
    return;
  }
  submitButton.disabled = true;
  errorBox.textContent = "";
  try {
    await api(
      `/api/v1/services/${serviceId}/installations/${installation.id}/complete`,
      {
        method: "POST",
        body: JSON.stringify({
          completed_at: completedAt.toISOString(),
          technicians,
          antenna_photos: antennaPhotos,
          modem_photos: modemPhotos,
          navigation_confirmed:
            $("#installation-navigation-confirmed").checked,
          navigation_confirmed_by:
            $("#installation-navigation-by").value.trim(),
          performed_by: state.user.display_name,
          notes: $("#installation-complete-notes").value.trim() || null,
        }),
      }
    );
    service.status = "active";
    service.activation_date = completedAt.toISOString().slice(0, 10);
    service.has_scheduled_installation = false;
    renderServices();
    renderOverview();
    $("#installation-complete-dialog").close();
    state.selectedServiceId = null;
    state.selectedInstallation = null;
    setNotice(
      "La instalación quedó completada y el servicio fue activado."
    );
  } catch (error) {
    errorBox.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

function openNetworkSimulationDialog(service) {
  state.selectedServiceId = service.id;
  state.selectedNetworkAction =
    service.status === "active" ? "suspend" : "reactivate";
  $("#network-simulation-dialog-title").textContent =
    `Simular ${state.selectedNetworkAction === "suspend"
      ? "suspensión"
      : "reactivación"} · ${service.amr_code}`;
  $("#network-simulation-summary").innerHTML = `
    <div>
      <span>Servicio</span>
      <strong>${escapeText(service.amr_code)}</strong>
    </div>
    <div>
      <span>Estado actual</span>
      <strong>${escapeText(service.status)}</strong>
    </div>
    <div>
      <span>Modo</span>
      <strong>Simulación sin cambios</strong>
    </div>
  `;
  $("#network-simulation-error").textContent = "";
  $("#network-simulation-dialog").showModal();
}

function closeNetworkSimulationDialog() {
  $("#network-simulation-dialog").close();
  state.selectedServiceId = null;
  state.selectedNetworkAction = null;
}

async function runNetworkSimulation(event) {
  event.preventDefault();
  const serviceId = state.selectedServiceId;
  const action = state.selectedNetworkAction;
  const submitButton = event.currentTarget.querySelector(
    'button[type="submit"]'
  );
  const errorBox = $("#network-simulation-error");
  if (!serviceId || !action) return;
  submitButton.disabled = true;
  errorBox.textContent = "";
  try {
    const command = await api(
      `/api/v1/services/${serviceId}/network-control/${action}`,
      {
        method: "POST",
        body: JSON.stringify({
          requested_by: state.user.display_name,
          idempotency_key: `ui-${crypto.randomUUID()}`,
          dry_run: true,
        }),
      }
    );
    closeNetworkSimulationDialog();
    setNotice(
      command.status === "simulated"
        ? "La simulación fue correcta; MikroTik y el estado comercial no cambiaron."
        : `La simulación terminó con estado ${command.status}.`
    );
  } catch (error) {
    errorBox.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

async function startNetworkReconciliation(service, button) {
  button.disabled = true;
  setNotice();
  try {
    const inspection = await api(
      `/api/v1/services/${service.id}/network-control/inspect`,
      {
        method: "POST",
        body: JSON.stringify({
          requested_by: state.user.display_name,
          idempotency_key:
            `ui-network-inspection-${crypto.randomUUID()}`,
        }),
      }
    );
    if (inspection.status !== "succeeded") {
      throw new Error(
        inspection.error_message ||
        "No fue posible inspeccionar el estado real de MikroTik."
      );
    }
    if (inspection.matches_expected) {
      setNotice(
        "MikroTik ya coincide con el estado comercial de Aether; no se requiere corrección."
      );
      return;
    }
    const payload = {
      requested_by: state.user.display_name,
      idempotency_key:
        `ui-reconciliation-preflight-${crypto.randomUUID()}`,
      dry_run: true,
      network_inspection_id: inspection.id,
    };
    const command = await api(
      `/api/v1/services/${service.id}/network-control/reconcile`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      }
    );
    if (command.status !== "simulated") {
      throw new Error(
        `La simulación terminó con estado ${command.status}.`
      );
    }
    openNetworkExecutionDialog({
      type: "reconciliation",
      serviceId: service.id,
      serviceCode: service.amr_code,
      commercialStatus: service.status,
      actionLabel: "Corregir desviación de red",
      targetIp: command.target_ip,
      endpoint:
        `/api/v1/services/${service.id}/network-control/reconcile`,
      payload,
      preflightCommandId: command.id,
    });
  } catch (error) {
    setNotice(error.message);
  } finally {
    button.disabled = false;
  }
}

function updateNotificationResultFields() {
  const failed = $("#notification-status").value === "failed";
  $("#notification-failure-field").hidden = !failed;
  $("#notification-failure-reason").required = failed;
  $("#notification-evidence-field").hidden = failed;
  if (failed) $("#notification-evidence-reference").value = "";
}

function openNotificationDialog(service) {
  state.selectedServiceId = service.id;
  const customer = state.customers?.find(
    (item) => item.id === service.current_customer_id
  );
  $("#notification-dialog-title").textContent =
    `Registrar aviso · ${service.amr_code}`;
  $("#notification-purpose").value = "suspension_warning";
  $("#notification-channel").value = "whatsapp";
  $("#notification-status").value = "delivered";
  $("#notification-recipient").value =
    customer?.phones?.[0] || customer?.email || "";
  $("#notification-occurred-at").value = localDateTimeValue();
  $("#notification-provider-reference").value = "";
  $("#notification-summary").value =
    "Aviso previo de suspensión por adeudo";
  $("#notification-evidence-reference").value = "";
  $("#notification-failure-reason").value = "";
  $("#notification-form-error").textContent = "";
  updateNotificationResultFields();
  $("#notification-dialog").showModal();
  $("#notification-recipient").focus();
}

function closeNotificationDialog() {
  $("#notification-dialog").close();
  state.selectedServiceId = null;
}

async function saveNotification(event) {
  event.preventDefault();
  const service = state.services?.find(
    (item) => item.id === state.selectedServiceId
  );
  const submitButton = event.currentTarget.querySelector(
    'button[type="submit"]'
  );
  const errorBox = $("#notification-form-error");
  if (!service) return;
  const channel = $("#notification-channel").value;
  const status = $("#notification-status").value;
  const providerReference =
    $("#notification-provider-reference").value.trim() || null;
  const evidenceReference =
    $("#notification-evidence-reference").value.trim() || null;
  const digital = ["whatsapp", "sms", "email"].includes(channel);
  if (
    status === "delivered" &&
    digital &&
    !providerReference &&
    !evidenceReference
  ) {
    errorBox.textContent =
      "Una entrega digital necesita referencia del proveedor o evidencia.";
    return;
  }
  const occurredAt = new Date($("#notification-occurred-at").value);
  if (Number.isNaN(occurredAt.getTime())) {
    errorBox.textContent = "Indica una fecha y hora válidas.";
    return;
  }
  submitButton.disabled = true;
  errorBox.textContent = "";
  try {
    const saved = await api("/api/v1/notifications", {
      method: "POST",
      body: JSON.stringify({
        customer_id: service.current_customer_id,
        service_id: service.id,
        channel,
        purpose: $("#notification-purpose").value,
        status,
        recipient: $("#notification-recipient").value.trim(),
        message_summary: $("#notification-summary").value.trim(),
        provider_reference: providerReference,
        evidence_reference: evidenceReference,
        failure_reason:
          status === "failed"
            ? $("#notification-failure-reason").value.trim()
            : null,
        occurred_at: occurredAt.toISOString(),
        recorded_by: state.user.display_name,
      }),
    });
    closeNotificationDialog();
    setNotice(
      saved.status === "delivered"
        ? "La entrega quedó registrada y auditada."
        : "El intento fallido quedó registrado con su motivo."
    );
  } catch (error) {
    errorBox.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

async function openSuspensionCheckDialog(service) {
  state.selectedServiceId = service.id;
  state.selectedSuspensionDebt = null;
  $("#suspension-check-dialog-title").textContent =
    `Validar suspensión · ${service.amr_code}`;
  $("#suspension-check-summary").innerHTML =
    '<p class="empty-state">Consultando condiciones actuales…</p>';
  $("#suspension-notification").innerHTML = "";
  $("#suspension-check-reason").value =
    "Falta de pago después del periodo de tolerancia";
  $("#suspension-grace-confirmed").checked = false;
  $("#suspension-extension-checked").checked = false;
  $("#suspension-check-error").textContent = "";
  $("#suspension-check-dialog").showModal();
  try {
    const [balance, notifications] = await Promise.all([
      api(`/api/v1/services/${service.id}/balance`),
      api(
        `/api/v1/notifications?service_id=${service.id}` +
        "&purpose=suspension_warning&status=delivered"
      ),
    ]);
    state.selectedSuspensionDebt = balance.outstanding_balance;
    $("#suspension-check-summary").innerHTML = `
      <div>
        <span>Deuda total</span>
        <strong>${formatMoney(balance.outstanding_balance)}</strong>
      </div>
      <div>
        <span>Deuda vencida</span>
        <strong>${formatMoney(balance.overdue_balance)}</strong>
      </div>
      <div>
        <span>Cargos abiertos</span>
        <strong>${balance.open_charges}</strong>
      </div>
    `;
    $("#suspension-notification").innerHTML = notifications
      .map(
        (item) =>
          `<option value="${item.id}">${formatDate(item.occurred_at)} · ${escapeText(item.recipient)}</option>`
      )
      .join("");
    if (!notifications.length) {
      $("#suspension-check-error").textContent =
        "Primero registra un aviso de suspensión entregado.";
    }
  } catch (error) {
    $("#suspension-check-error").textContent = error.message;
  }
}

function closeSuspensionCheckDialog() {
  $("#suspension-check-dialog").close();
  state.selectedServiceId = null;
  state.selectedSuspensionDebt = null;
}

function textLines(value) {
  return value
    .split(/[\n,;]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

async function loadOptionalRecord(path) {
  try {
    return await api(path);
  } catch (error) {
    if ([403, 404].includes(error.status)) return null;
    throw error;
  }
}

async function openCancellationDialog(service) {
  state.selectedServiceId = service.id;
  state.selectedCancellation = null;
  state.selectedRecovery = null;
  $("#cancellation-dialog-title").textContent =
    `Baja y retiro · ${service.amr_code}`;
  $("#cancellation-summary").innerHTML = `
    <div>
      <span>Servicio</span>
      <strong>${escapeText(service.amr_code)}</strong>
    </div>
    <div>
      <span>Estado comercial</span>
      <strong>${escapeText(service.status)}</strong>
    </div>
    <div>
      <span>Etapa</span>
      <strong>Consultando…</strong>
    </div>
  `;
  $("#cancellation-workspace").innerHTML =
    '<p class="empty-state">Consultando el expediente de baja…</p>';
  $("#cancellation-error").textContent = "";
  $("#cancellation-dialog").showModal();
  try {
    state.selectedCancellation = await loadOptionalRecord(
      `/api/v1/services/${service.id}/cancellation`
    );
    if (state.selectedCancellation) {
      state.selectedRecovery = await loadOptionalRecord(
        `/api/v1/services/${service.id}/equipment-recovery`
      );
    }
    renderCancellationWorkspace();
  } catch (error) {
    $("#cancellation-error").textContent = error.message;
  }
}

function closeCancellationDialog() {
  clearRecoveryEvidencePreview();
  $("#cancellation-dialog").close();
  state.selectedServiceId = null;
  state.selectedCancellation = null;
  state.selectedRecovery = null;
  $("#cancellation-error").textContent = "";
}

function cancellationStageLabel(cancellation, recovery) {
  if (!cancellation) return "Solicitud pendiente";
  if (cancellation.status === "scheduled") return "Corte pendiente";
  if (!recovery) return "Retiro por programar";
  if (["scheduled", "pending"].includes(recovery.status)) {
    return "Retiro pendiente";
  }
  if (!cancellation.network_command_id) return "Cierre completado";
  if (!cancellation.network_release_command_id) {
    return "Liberación de IP pendiente";
  }
  return "Cierre completado";
}

function cancellationRequestMarkup(service) {
  if (!hasCapability("services.cancel")) {
    return `
      <section class="cancellation-stage-card">
        <h3>Sin solicitud de baja</h3>
        <p>Tu cuenta puede consultar el servicio, pero no iniciar una baja definitiva.</p>
      </section>
    `;
  }
  return `
    <form id="cancellation-request-form" class="cancellation-stage-card">
      <div class="stage-status">
        <h3>1. Registrar solicitud</h3>
        <span class="badge pending">Pendiente</span>
      </div>
      <p>
        Aether calculará deuda y saldo a favor. La fecha efectiva puede ser hoy
        o el final del periodo pagado.
      </p>
      <div class="form-grid">
        <label>
          Fecha efectiva
          <input
            id="cancellation-effective-date"
            type="date"
            min="${localDateValue()}"
            value="${localDateValue()}"
            required
          >
        </label>
        <label class="full-row">
          Motivo confirmado por el titular
          <textarea
            id="cancellation-reason"
            rows="3"
            minlength="3"
            maxlength="500"
            required
          ></textarea>
        </label>
        <label class="full-row">
          Equipos que deben priorizarse
          <textarea
            id="cancellation-equipment-notes"
            rows="2"
            maxlength="1000"
          >Priorizar antena, módem, PoE y fuente propiedad de AMR</textarea>
        </label>
        <label class="full-row">
          Notas internas
          <textarea id="cancellation-notes" rows="2" maxlength="1000"></textarea>
        </label>
      </div>
      <div class="dialog-actions">
        <button class="danger-button" type="submit">Registrar solicitud</button>
      </div>
    </form>
  `;
}

function recoveryScheduleMarkup(cancellation) {
  if (!hasCapability("assets.write")) {
    return `
      <section class="cancellation-stage-card">
        <h3>3. Recuperación de equipos</h3>
        <p>Aún no hay una visita registrada. Se requiere una cuenta de inventario para programarla.</p>
      </section>
    `;
  }
  const minimumDate = cancellation.effective_date > localDateValue()
    ? cancellation.effective_date
    : localDateValue();
  return `
    <form id="recovery-schedule-form" class="cancellation-stage-card">
      <div class="stage-status">
        <h3>3. Programar recuperación</h3>
        <span class="badge pending">Pendiente</span>
      </div>
      <p>La visita queda vinculada al folio y no libera la IP por sí sola.</p>
      <div class="form-grid">
        <label>
          Fecha acordada
          <input
            id="recovery-scheduled-for"
            type="date"
            min="${minimumDate}"
            value="${minimumDate}"
            required
          >
        </label>
        <label>
          Técnico asignado
          <input id="recovery-technician" minlength="2" maxlength="150" required>
        </label>
        <label class="full-row">
          Equipos esperados, uno por línea
          <textarea
            id="recovery-expected-equipment"
            rows="5"
            required
          >Antena
Módem
PoE
Fuente</textarea>
        </label>
        <label class="full-row">
          Notas
          <textarea id="recovery-schedule-notes" rows="2" maxlength="1000"></textarea>
        </label>
      </div>
      <div class="dialog-actions">
        <button class="primary-button" type="submit">Programar visita</button>
      </div>
    </form>
  `;
}

function recoveryCompletionMarkup(recovery, cancellation) {
  const canComplete = (
    hasCapability("assets.write") &&
    cancellation.status === "executed"
  );
  if (!canComplete) {
    return `
      <section class="cancellation-stage-card">
        <div class="stage-status">
          <h3>3. Recuperación programada</h3>
          <span class="badge pending">${escapeText(recovery.status)}</span>
        </div>
        <p>
          Visita para ${formatDate(recovery.scheduled_for)} ·
          ${escapeText(recovery.assigned_technician)}.
          ${cancellation.status === "executed"
            ? "Tu cuenta no puede completar el retiro."
            : "Primero debe ejecutarse la baja."}
        </p>
      </section>
    `;
  }
  return `
    <form id="recovery-complete-form" class="cancellation-stage-card">
      <div class="stage-status">
        <h3>3. Confirmar recuperación</h3>
        <span class="badge pending">Visita programada</span>
      </div>
      <p>Clasifica cada equipo. Los faltantes permanecerán en el historial.</p>
      <div class="equipment-classification">
        ${recovery.expected_equipment.map((item) => `
          <label>
            <strong>${escapeText(item)}</strong>
            <select
              class="equipment-result"
              data-equipment="${escapeText(item)}"
              required
            >
              <option value="recovered">Recuperado</option>
              <option value="missing">No recuperado</option>
            </select>
          </label>
        `).join("")}
      </div>
      <div class="form-grid">
        <label class="full-row">
          Condición y trabajo realizado
          <textarea
            id="recovery-condition-notes"
            rows="3"
            minlength="3"
            maxlength="2000"
            required
          ></textarea>
        </label>
        <label class="full-row">
          Referencias privadas de evidencia, una por línea
          <textarea id="recovery-evidence" rows="3"></textarea>
        </label>
        <label class="full-row">
          Imágenes de evidencia (opcional)
          <input
            id="recovery-evidence-images"
            type="file"
            accept="image/*"
            multiple
          >
        </label>
        <div class="full-row evidence-image-preview" id="recovery-evidence-preview" hidden></div>
        <label>
          Constancia de recepción
          <input id="recovery-receipt" maxlength="500">
        </label>
        <label class="full-row">
          Notas
          <textarea id="recovery-completion-notes" rows="2" maxlength="1000"></textarea>
        </label>
      </div>
      <p class="form-help">
        Puedes cerrar la visita sin imágenes; si adjuntas fotos, Aether las
        conserva como evidencia privada.
      </p>
      <div class="dialog-actions">
        <button class="primary-button" type="submit">Cerrar visita</button>
      </div>
    </form>
  `;
}

function networkReleaseMarkup(cancellation, recovery) {
  if (cancellation.network_release_command_id) {
    return `
      <section class="cancellation-stage-card">
        <div class="stage-status">
          <h3>4. Red liberada</h3>
          <span class="badge">Completado</span>
        </div>
        <p>
          MikroTik confirmó el retiro del bloqueo el
          ${formatDate(cancellation.network_released_at)}. La asignación IP ya
          está cerrada y su evidencia permanece privada.
        </p>
      </section>
    `;
  }
  if (!hasCapability("services.cancel")) {
    return `
      <section class="cancellation-stage-card">
        <h3>4. Liberación de IP pendiente</h3>
        <p>El retiro físico terminó. Se requiere autorización de baja para liberar la IP.</p>
      </section>
    `;
  }
  return `
    <form id="network-release-form" class="cancellation-stage-card">
      <div class="stage-status">
        <h3>4. Liberar IP reservada</h3>
        <span class="badge pending">Requiere simulación</span>
      </div>
      <p>
        Resultado del retiro: ${escapeText(recovery.status)}. La IP sólo se
        libera si MikroTik confirma que salió de la lista de suspendidos.
      </p>
      <div class="form-grid">
        <label class="full-row">
          Referencia privada de la desconexión física
          <input
            id="network-release-evidence"
            minlength="3"
            maxlength="500"
            required
          >
        </label>
        <label class="checkbox-field full-row">
          <input id="network-release-confirmed" type="checkbox" required>
          Confirmo que la instalación quedó físicamente desconectada
        </label>
      </div>
      <div class="dialog-actions">
        <button class="danger-button" type="submit">Simular liberación</button>
      </div>
    </form>
  `;
}

function renderCancellationWorkspace() {
  clearRecoveryEvidencePreview();
  const service = state.services?.find(
    (item) => item.id === state.selectedServiceId
  );
  const cancellation = state.selectedCancellation;
  const recovery = state.selectedRecovery;
  if (!service) return;
  $("#cancellation-summary").innerHTML = `
    <div>
      <span>Servicio</span>
      <strong>${escapeText(service.amr_code)}</strong>
    </div>
    <div>
      <span>Estado comercial</span>
      <strong>${escapeText(service.status)}</strong>
    </div>
    <div>
      <span>Etapa</span>
      <strong>${escapeText(cancellationStageLabel(cancellation, recovery))}</strong>
    </div>
  `;
  if (!cancellation) {
    $("#cancellation-workspace").innerHTML =
      cancellationRequestMarkup(service);
    return;
  }

  const due = cancellation.effective_date <= localDateValue();
  const finalRecovery = recovery && [
    "complete",
    "partial",
    "unrecoverable",
  ].includes(recovery.status);
  const sections = [`
    <section class="cancellation-stage-card">
      <div class="stage-status">
        <h3>1. Solicitud ${escapeText(cancellation.folio)}</h3>
        <span class="badge ${escapeText(cancellation.status)}">${escapeText(cancellation.status)}</span>
      </div>
      <p>
        Efectiva el ${formatDate(cancellation.effective_date)} ·
        deuda ${formatMoney(cancellation.pending_balance)} ·
        saldo a favor ${formatMoney(cancellation.credit_balance)}.
      </p>
    </section>
  `];
  if (cancellation.status === "scheduled") {
    sections.push(`
      <section class="cancellation-stage-card">
        <div class="stage-status">
          <h3>2. Corte de red verificado</h3>
          <span class="badge pending">${due ? "Listo para validar" : "Programado"}</span>
        </div>
        <p>
          ${due
            ? "Aether simulará el bloqueo de la IP antes de permitir la baja real."
            : `La ejecución estará disponible el ${formatDate(cancellation.effective_date)}.`}
        </p>
        ${due && hasCapability("services.cancel") ? `
          <div class="dialog-actions">
            <button
              id="${service.status === "pending"
                ? "execute-pending-cancellation"
                : "simulate-cancellation-shutdown"}"
              class="danger-button"
              type="button"
            >${service.status === "pending"
              ? "Ejecutar baja pendiente"
              : "Simular corte y baja"}</button>
          </div>
        ` : ""}
      </section>
    `);
  } else {
    sections.push(`
      <section class="cancellation-stage-card">
        <div class="stage-status">
          <h3>2. Baja ejecutada</h3>
          <span class="badge">Verificada</span>
        </div>
        <p>
          ${cancellation.network_command_id
            ? "MikroTik confirmó el bloqueo y la IP permanece reservada."
            : "El servicio no requería una asignación de red para cerrar."}
        </p>
      </section>
    `);
  }

  if (!recovery) sections.push(recoveryScheduleMarkup(cancellation));
  else if (["scheduled", "pending"].includes(recovery.status)) {
    sections.push(recoveryCompletionMarkup(recovery, cancellation));
  } else {
    sections.push(`
      <section class="cancellation-stage-card">
        <div class="stage-status">
          <h3>3. Recuperación finalizada</h3>
          <span class="badge ${escapeText(recovery.status)}">${escapeText(recovery.status)}</span>
        </div>
        <p>
          ${recovery.recovered_equipment?.length || 0} recuperados ·
          ${recovery.missing_equipment?.length || 0} no recuperados.
          La evidencia y la constancia permanecen en el expediente.
        </p>
      </section>
    `);
  }
  if (cancellation.status === "executed" && finalRecovery) {
    if (cancellation.network_command_id) {
      sections.push(networkReleaseMarkup(cancellation, recovery));
    } else {
      sections.push(`
        <section class="cancellation-stage-card">
          <div class="stage-status">
            <h3>4. Cierre completado</h3>
            <span class="badge">Sin IP reservada</span>
          </div>
          <p>Este servicio no tenía una asignación de red que liberar.</p>
        </section>
      `);
    }
  }
  $("#cancellation-workspace").innerHTML = sections.join("");
}

async function saveCancellationRequest(event) {
  event.preventDefault();
  const service = state.services?.find(
    (item) => item.id === state.selectedServiceId
  );
  const submitButton = event.currentTarget.querySelector(
    'button[type="submit"]'
  );
  if (!service) return;
  submitButton.disabled = true;
  $("#cancellation-error").textContent = "";
  try {
    state.selectedCancellation = await api(
      `/api/v1/services/${service.id}/cancellation`,
      {
        method: "POST",
        body: JSON.stringify({
          requester_customer_id: service.current_customer_id,
          requested_at: localDateValue(),
          effective_date: $("#cancellation-effective-date").value,
          reason: $("#cancellation-reason").value.trim(),
          equipment_pending_notes:
            $("#cancellation-equipment-notes").value.trim() || null,
          registered_by: state.user.display_name,
          notes: $("#cancellation-notes").value.trim() || null,
        }),
      }
    );
    if (state.selectedCancellation.status === "executed") {
      service.status = "cancelled";
      renderServices();
      renderOverview();
    }
    renderCancellationWorkspace();
    setNotice("La solicitud de baja quedó registrada con sus saldos calculados por Aether.");
  } catch (error) {
    $("#cancellation-error").textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

async function simulateCancellationShutdown(button) {
  const service = state.services?.find(
    (item) => item.id === state.selectedServiceId
  );
  if (!service) return;
  button.disabled = true;
  $("#cancellation-error").textContent = "";
  try {
    const payload = {
      performed_by: state.user.display_name,
      idempotency_key: `ui-cancellation-preflight-${crypto.randomUUID()}`,
      dry_run: true,
    };
    const result = await api(
      `/api/v1/services/${service.id}/cancellation/coordinated`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      }
    );
    if (result.command.status !== "simulated") {
      throw new Error(`La simulación terminó con estado ${result.command.status}.`);
    }
    closeCancellationDialog();
    openNetworkExecutionDialog({
      type: "cancellation",
      serviceId: service.id,
      serviceCode: service.amr_code,
      actionLabel: "Ejecutar baja definitiva",
      targetIp: result.command.target_ip,
      endpoint:
        `/api/v1/services/${service.id}/cancellation/coordinated`,
      payload,
      preflightCommandId: result.command.id,
    });
  } catch (error) {
    $("#cancellation-error").textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

async function executePendingCancellation(button) {
  const service = state.services?.find(
    (item) => item.id === state.selectedServiceId
  );
  if (!service) return;
  button.disabled = true;
  $("#cancellation-error").textContent = "";
  try {
    state.selectedCancellation = await api(
      `/api/v1/services/${service.id}/cancellation/execute`,
      {
        method: "POST",
        body: JSON.stringify({
          performed_by: state.user.display_name,
        }),
      }
    );
    service.status = "cancelled";
    renderServices();
    renderOverview();
    renderCancellationWorkspace();
    setNotice("La baja pendiente quedó ejecutada sin una asignación de red que liberar.");
  } catch (error) {
    $("#cancellation-error").textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

async function scheduleEquipmentRecovery(event) {
  event.preventDefault();
  const submitButton = event.currentTarget.querySelector(
    'button[type="submit"]'
  );
  submitButton.disabled = true;
  $("#cancellation-error").textContent = "";
  try {
    state.selectedRecovery = await api(
      `/api/v1/services/${state.selectedServiceId}/equipment-recovery`,
      {
        method: "POST",
        body: JSON.stringify({
          scheduled_for: $("#recovery-scheduled-for").value,
          assigned_technician: $("#recovery-technician").value.trim(),
          expected_equipment: textLines(
            $("#recovery-expected-equipment").value
          ),
          notes: $("#recovery-schedule-notes").value.trim() || null,
        }),
      }
    );
    renderCancellationWorkspace();
    setNotice("La recuperación de equipos quedó programada y vinculada al folio.");
  } catch (error) {
    $("#cancellation-error").textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

async function completeEquipmentRecovery(event) {
  event.preventDefault();
  const submitButton = event.currentTarget.querySelector(
    'button[type="submit"]'
  );
  const recovered = [];
  const missing = [];
  document.querySelectorAll(".equipment-result").forEach((select) => {
    const target = select.value === "recovered" ? recovered : missing;
    target.push(select.dataset.equipment);
  });
  submitButton.disabled = true;
  $("#cancellation-error").textContent = "";
  try {
    const evidenceReferences = await buildRecoveryEvidenceReferences();
    state.selectedRecovery = await api(
      `/api/v1/services/${state.selectedServiceId}/equipment-recovery/complete`,
      {
        method: "POST",
        body: JSON.stringify({
          performed_by: state.user.display_name,
          recovered_equipment: recovered,
          missing_equipment: missing,
          condition_notes: $("#recovery-condition-notes").value.trim(),
          evidence_references: evidenceReferences,
          receipt_reference: $("#recovery-receipt").value.trim() || null,
          notes: $("#recovery-completion-notes").value.trim() || null,
        }),
      }
    );
    state.selectedCancellation = await api(
      `/api/v1/services/${state.selectedServiceId}/cancellation`
    );
    renderCancellationWorkspace();
    setNotice("La visita quedó cerrada; los equipos recuperados y faltantes se conservaron.");
  } catch (error) {
    $("#cancellation-error").textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

async function simulateNetworkRelease(event) {
  event.preventDefault();
  const service = state.services?.find(
    (item) => item.id === state.selectedServiceId
  );
  const submitButton = event.currentTarget.querySelector(
    'button[type="submit"]'
  );
  if (!service) return;
  submitButton.disabled = true;
  $("#cancellation-error").textContent = "";
  try {
    const payload = {
      performed_by: state.user.display_name,
      physical_disconnect_confirmed:
        $("#network-release-confirmed").checked,
      disconnect_evidence_reference:
        $("#network-release-evidence").value.trim(),
      idempotency_key: `ui-network-release-preflight-${crypto.randomUUID()}`,
      dry_run: true,
    };
    const result = await api(
      `/api/v1/services/${service.id}/cancellation/network-release/coordinated`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      }
    );
    if (result.command.status !== "simulated") {
      throw new Error(`La simulación terminó con estado ${result.command.status}.`);
    }
    closeCancellationDialog();
    openNetworkExecutionDialog({
      type: "network_release",
      serviceId: service.id,
      serviceCode: service.amr_code,
      actionLabel: "Liberar IP reservada",
      targetIp: result.command.target_ip,
      endpoint:
        `/api/v1/services/${service.id}/cancellation/network-release/coordinated`,
      payload,
      preflightCommandId: result.command.id,
    });
  } catch (error) {
    $("#cancellation-error").textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

function openNetworkExecutionDialog(operation) {
  state.pendingNetworkOperation = {
    ...operation,
    expiresAt: Date.now() + NETWORK_PREFLIGHT_VALIDITY_MS,
  };
  const eyebrowByType = {
    suspension: "SUSPENSIÓN REAL · CONFIRMACIÓN FINAL",
    reactivation: "REACTIVACIÓN REAL · CONFIRMACIÓN FINAL",
    cancellation: "BAJA DEFINITIVA · CONFIRMACIÓN FINAL",
    network_release: "LIBERACIÓN DE IP · CONFIRMACIÓN FINAL",
    reconciliation: "RECONCILIACIÓN DE RED · CONFIRMACIÓN FINAL",
  };
  $("#network-execution-eyebrow").textContent =
    eyebrowByType[operation.type] || "CAMBIO REAL · CONFIRMACIÓN FINAL";
  $("#network-execution-dialog-title").textContent =
    `${operation.actionLabel} · ${operation.serviceCode}`;
  $("#network-execution-summary").innerHTML = `
    <div>
      <span>Servicio</span>
      <strong>${escapeText(operation.serviceCode)}</strong>
    </div>
    <div>
      <span>Acción real</span>
      <strong>${escapeText(operation.actionLabel)}</strong>
    </div>
    <div>
      <span>IP verificada</span>
      <strong>${escapeText(operation.targetIp)}</strong>
    </div>
  `;
  const impactByType = {
    suspension:
      "Aether agregará esta IP a la lista de suspendidos. El servicio sólo quedará suspendido si MikroTik confirma el bloqueo.",
    reactivation:
      "Aether retirará esta IP de la lista de suspendidos. El servicio sólo quedará activo si MikroTik confirma el acceso.",
    cancellation:
      "Aether bloqueará y verificará esta IP. Sólo entonces ejecutará la baja; la IP seguirá reservada hasta recuperar los equipos.",
    network_release:
      "Aether retirará esta IP de la lista de suspendidos. Sólo una verificación exitosa cerrará la asignación y permitirá reutilizarla.",
    reconciliation:
      operation.commercialStatus === "suspended"
        ? "Aether volverá a aplicar el bloqueo que corresponde al estado suspendido y verificará la address list. El estado comercial no cambiará."
        : "Aether retirará cualquier bloqueo manual que contradiga el estado activo y verificará la address list. El estado comercial no cambiará.",
  };
  $("#network-execution-impact").textContent =
    impactByType[operation.type] ||
    "Aether volverá a validar la operación antes de contactar MikroTik.";
  $("#network-execution-code-label").textContent =
    `Escribe ${operation.serviceCode} para confirmar`;
  $("#network-execution-code").value = "";
  $("#network-execution-confirm").checked = false;
  $("#network-execution-error").textContent = "";
  $("#network-execution-dialog").showModal();
}

function closeNetworkExecutionDialog() {
  $("#network-execution-dialog").close();
  state.pendingNetworkOperation = null;
  $("#network-execution-code").value = "";
  $("#network-execution-confirm").checked = false;
  $("#network-execution-error").textContent = "";
}

async function runSuspensionCheck(event) {
  event.preventDefault();
  const serviceId = state.selectedServiceId;
  const notificationId = $("#suspension-notification").value;
  const submitButton = event.currentTarget.querySelector(
    'button[type="submit"]'
  );
  const errorBox = $("#suspension-check-error");
  if (!serviceId || state.selectedSuspensionDebt === null) return;
  if (!notificationId) {
    errorBox.textContent =
      "Selecciona un aviso de suspensión entregado.";
    return;
  }
  submitButton.disabled = true;
  errorBox.textContent = "";
  try {
    const service = state.services?.find(
      (item) => item.id === serviceId
    );
    const payload = {
      scheduled_for: localDateValue(),
      reason: $("#suspension-check-reason").value.trim(),
      debt_amount: state.selectedSuspensionDebt,
      grace_period_elapsed:
        $("#suspension-grace-confirmed").checked,
      extension_checked:
        $("#suspension-extension-checked").checked,
      has_active_extension: false,
      notification_id: notificationId,
      performed_by: state.user.display_name,
      idempotency_key: `ui-suspension-${crypto.randomUUID()}`,
      dry_run: true,
    };
    const result = await api(
      `/api/v1/services/${serviceId}/suspensions/coordinated`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      }
    );
    closeSuspensionCheckDialog();
    if (result.command.status === "simulated" && service) {
      openNetworkExecutionDialog({
        type: "suspension",
        serviceId,
        serviceCode: service.amr_code,
        actionLabel: "Suspender servicio",
        targetIp: result.command.target_ip,
        endpoint:
          `/api/v1/services/${serviceId}/suspensions/coordinated`,
        payload,
        preflightCommandId: result.command.id,
      });
    } else {
      setNotice(
        `La validación terminó con estado ${result.command.status}.`
      );
    }
  } catch (error) {
    errorBox.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

async function openReactivationCheckDialog(service) {
  state.selectedServiceId = service.id;
  state.selectedReactivationDebt = null;
  $("#reactivation-check-dialog-title").textContent =
    `Validar reactivación · ${service.amr_code}`;
  $("#reactivation-check-summary").innerHTML =
    '<p class="empty-state">Consultando saldo actual…</p>';
  $("#reactivation-check-reason").value =
    "Pago verificado o acuerdo de pago autorizado";
  $("#reactivation-authorized-by").value = "";
  $("#reactivation-authorized-by").readOnly = false;
  $("#reactivation-basis-field").hidden = true;
  $("#reactivation-authorization-basis").disabled = true;
  $("#reactivation-authorization-basis").innerHTML = "";
  $("#reactivation-check-error").textContent = "";
  state.selectedReactivationAuthorizations = [];
  $("#reactivation-check-dialog").showModal();
  try {
    const [balance, extensions, agreements] = await Promise.all([
      api(`/api/v1/services/${service.id}/balance`),
      api(`/api/v1/services/${service.id}/extensions`),
      api(`/api/v1/services/${service.id}/payment-agreements`),
    ]);
    state.selectedReactivationDebt = balance.outstanding_balance;
    const today = localDateValue();
    state.selectedReactivationAuthorizations = [
      ...extensions
        .filter(
          (item) =>
            item.status === "active" &&
            item.customer_id === service.current_customer_id
        )
        .map((item) => ({
          type: "extension",
          id: item.id,
          authorized_by: item.authorized_by,
          label:
            `Prórroga hasta ${formatDate(item.promised_date)}`,
        })),
      ...agreements
        .filter(
          (item) =>
            item.status === "active" &&
            item.customer_id === service.current_customer_id &&
            (!item.promised_date || item.promised_date >= today)
        )
        .map((item) => ({
          type: "payment_agreement",
          id: item.id,
          authorized_by: item.authorized_by,
          label: `${item.folio} · ${item.terms.slice(0, 70)}`,
        })),
    ];
    $("#reactivation-check-summary").innerHTML = `
      <div>
        <span>Deuda total actual</span>
        <strong>${formatMoney(balance.outstanding_balance)}</strong>
      </div>
      <div>
        <span>Deuda vencida</span>
        <strong>${formatMoney(balance.overdue_balance)}</strong>
      </div>
      <div>
        <span>Cargos abiertos</span>
        <strong>${balance.open_charges}</strong>
      </div>
    `;
    if (Number(balance.outstanding_balance) > 0) {
      $("#reactivation-basis-field").hidden = false;
      $("#reactivation-authorization-basis").disabled = false;
      $("#reactivation-authorization-basis").innerHTML =
        state.selectedReactivationAuthorizations
          .map(
            (item, index) =>
              `<option value="${index}">${escapeText(item.label)}</option>`
          )
          .join("");
      $("#reactivation-authorized-by").readOnly = true;
      if (!state.selectedReactivationAuthorizations.length) {
        $("#reactivation-check-error").textContent =
          "La deuda requiere una prórroga o un convenio vigente del titular actual.";
      }
      updateReactivationAuthorizer();
      $("#reactivation-authorization-basis").focus();
    } else {
      $("#reactivation-authorized-by").focus();
    }
  } catch (error) {
    $("#reactivation-check-error").textContent = error.message;
  }
}

function closeReactivationCheckDialog() {
  $("#reactivation-check-dialog").close();
  state.selectedServiceId = null;
  state.selectedReactivationDebt = null;
  state.selectedReactivationAuthorizations = [];
}

function updateReactivationAuthorizer() {
  const index = Number($("#reactivation-authorization-basis").value);
  const authorization =
    state.selectedReactivationAuthorizations[index];
  $("#reactivation-authorized-by").value =
    authorization?.authorized_by || "";
}

async function runReactivationCheck(event) {
  event.preventDefault();
  const serviceId = state.selectedServiceId;
  const submitButton = event.currentTarget.querySelector(
    'button[type="submit"]'
  );
  const errorBox = $("#reactivation-check-error");
  if (!serviceId || state.selectedReactivationDebt === null) return;
  const hasDebt = Number(state.selectedReactivationDebt) > 0;
  const authorization = hasDebt
    ? state.selectedReactivationAuthorizations[
        Number($("#reactivation-authorization-basis").value)
      ]
    : null;
  if (hasDebt && !authorization) {
    errorBox.textContent =
      "Selecciona una prórroga o un convenio vigente.";
    return;
  }
  submitButton.disabled = true;
  errorBox.textContent = "";
  try {
    const service = state.services?.find(
      (item) => item.id === serviceId
    );
    const payload = {
      reason: $("#reactivation-check-reason").value.trim(),
      authorized_by: $("#reactivation-authorized-by").value.trim(),
      performed_by: state.user.display_name,
      debt_amount: state.selectedReactivationDebt,
      extension_id:
        authorization?.type === "extension"
          ? authorization.id
          : null,
      payment_agreement_id:
        authorization?.type === "payment_agreement"
          ? authorization.id
          : null,
      idempotency_key:
        `ui-reactivation-${crypto.randomUUID()}`,
      dry_run: true,
    };
    const result = await api(
      `/api/v1/services/${serviceId}/reactivations/coordinated`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      }
    );
    closeReactivationCheckDialog();
    if (result.command.status === "simulated" && service) {
      openNetworkExecutionDialog({
        type: "reactivation",
        serviceId,
        serviceCode: service.amr_code,
        actionLabel: "Reactivar servicio",
        targetIp: result.command.target_ip,
        endpoint:
          `/api/v1/services/${serviceId}/reactivations/coordinated`,
        payload,
        preflightCommandId: result.command.id,
      });
    } else {
      setNotice(
        `La validación terminó con estado ${result.command.status}.`
      );
    }
  } catch (error) {
    errorBox.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

async function executeConfirmedNetworkOperation(event) {
  event.preventDefault();
  const operation = state.pendingNetworkOperation;
  const submitButton = event.currentTarget.querySelector(
    'button[type="submit"]'
  );
  const errorBox = $("#network-execution-error");
  if (!operation) return;
  if (Date.now() >= operation.expiresAt) {
    errorBox.textContent =
      "La validación segura venció. Cierra esta ventana y simula nuevamente.";
    return;
  }
  if (
    $("#network-execution-code").value.trim().toUpperCase() !==
    operation.serviceCode.toUpperCase()
  ) {
    errorBox.textContent =
      `Escribe exactamente ${operation.serviceCode} para continuar.`;
    return;
  }
  if (!$("#network-execution-confirm").checked) {
    errorBox.textContent =
      "Confirma que revisaste el servicio, la acción y la IP.";
    return;
  }
  submitButton.disabled = true;
  errorBox.textContent = "";
  try {
    const result = await api(operation.endpoint, {
      method: "POST",
      body: JSON.stringify({
        ...operation.payload,
        idempotency_key:
          `ui-${operation.type}-live-${crypto.randomUUID()}`,
        dry_run: false,
        preflight_command_id: operation.preflightCommandId,
      }),
    });
    const networkCommand =
      operation.type === "reconciliation" ? result : result.command;
    const completedRecord = {
      suspension: result.suspension,
      reactivation: result.reactivation,
      cancellation: result.cancellation,
      network_release: result.cancellation,
      reconciliation: result,
    }[operation.type];
    if (
      networkCommand?.status !== "succeeded" ||
      !completedRecord
    ) {
      closeNetworkExecutionDialog();
      setNotice(
        "No se cambió el servicio. La orden real no fue confirmada por MikroTik."
      );
      return;
    }
    const service = state.services?.find(
      (item) => item.id === operation.serviceId
    );
    if (service) {
      if (operation.type === "suspension") {
        service.status = "suspended";
      } else if (operation.type === "reactivation") {
        service.status = "active";
      } else if (operation.type === "cancellation") {
        service.status = "cancelled";
      }
    }
    closeNetworkExecutionDialog();
    renderServices();
    renderOverview();
    const noticeByType = {
      suspension:
        "MikroTik confirmó el bloqueo y el servicio quedó suspendido.",
      reactivation:
        "MikroTik confirmó el acceso y el servicio quedó reactivado.",
      cancellation:
        "MikroTik confirmó el bloqueo y la baja quedó ejecutada. La IP continúa reservada.",
      network_release:
        "MikroTik confirmó el retiro del bloqueo y la asignación IP quedó cerrada.",
      reconciliation:
        "MikroTik confirmó que la red coincide con el estado comercial de Aether.",
    };
    setNotice(noticeByType[operation.type]);
  } catch (error) {
    errorBox.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

const extensionStatusLabels = {
  active: "Vigente",
  fulfilled: "Cumplida",
  expired: "Vencida",
  cancelled: "Cancelada",
};

function renderExtensionManagement() {
  const service = state.services?.find(
    (item) => item.id === state.selectedServiceId
  );
  if (!service) return;
  const extensions = state.selectedExtensions || [];
  const activeExtension = extensions.find(
    (item) => item.status === "active"
  );
  const balance = Number(state.selectedExtensionBalance || 0);
  $("#extension-summary").innerHTML = `
    <div>
      <span>Servicio</span>
      <strong>${escapeText(service.amr_code)}</strong>
    </div>
    <div>
      <span>Deuda actual</span>
      <strong>${formatMoney(balance)}</strong>
    </div>
    <div>
      <span>Prórroga vigente</span>
      <strong>${activeExtension ? "Sí" : "No"}</strong>
    </div>
  `;
  $("#extension-history").innerHTML = extensions.length
    ? extensions
        .slice()
        .reverse()
        .map(
          (item) => `
            <article class="history-item">
              <div>
                <strong>${escapeText(
                  extensionStatusLabels[item.status] || item.status
                )}</strong>
                <span>${formatDate(item.original_due_date)} → ${formatDate(item.promised_date)}</span>
              </div>
              <p>${escapeText(item.reason)}</p>
              <small>
                Autorizó ${escapeText(item.authorized_by)} ·
                Evidencia ${item.has_evidence ? "registrada" : "no registrada"}
              </small>
              ${item.resolution_reason ? `
                <small>
                  Resolución: ${escapeText(item.resolution_reason)}
                </small>
              ` : ""}
            </article>
          `
        )
        .join("")
    : '<p class="empty-state">No hay prórrogas registradas.</p>';
  const canCreate = (
    hasCapability("billing.write") &&
    ["active", "suspended"].includes(service.status) &&
    balance > 0 &&
    !activeExtension
  );
  $("#extension-create-form").hidden = !canCreate;
  const createNote = $("#extension-create-note");
  createNote.hidden = canCreate;
  if (!hasCapability("billing.write")) {
    createNote.textContent =
      "Tu cuenta puede consultar el historial, pero no crear prórrogas.";
  } else if (activeExtension) {
    createNote.textContent =
      "Ya existe una prórroga vigente; debe resolverse antes de crear otra.";
  } else if (balance <= 0) {
    createNote.textContent =
      "No se puede crear una prórroga porque el servicio no tiene deuda.";
  } else if (!["active", "suspended"].includes(service.status)) {
    createNote.textContent =
      "El estado actual del servicio no admite nuevas prórrogas.";
  } else {
    createNote.textContent = "";
  }
  const canResolve = (
    hasCapability("billing.approve") && Boolean(activeExtension)
  );
  $("#extension-resolve-form").hidden = !canResolve;
  $("#extension-resolve-note").hidden =
    canResolve || !activeExtension;
}

async function openExtensionDialog(service) {
  state.selectedServiceId = service.id;
  state.selectedExtensions = [];
  state.selectedExtensionBalance = null;
  state.selectedExtensionDueDate = null;
  $("#extension-dialog-title").textContent =
    `Prórrogas · ${service.amr_code}`;
  $("#extension-summary").innerHTML =
    '<p class="empty-state">Consultando historial y deuda…</p>';
  $("#extension-history").innerHTML = "";
  $("#extension-create-form").hidden = true;
  $("#extension-resolve-form").hidden = true;
  $("#extension-create-note").hidden = true;
  $("#extension-resolve-note").hidden = true;
  $("#extension-dialog-status").textContent = "";
  $("#extension-dialog").showModal();
  try {
    const [balance, charges, extensions] = await Promise.all([
      api(`/api/v1/services/${service.id}/balance`),
      api(`/api/v1/services/${service.id}/charges`),
      api(`/api/v1/services/${service.id}/extensions`),
    ]);
    const openCharges = charges.filter(
      (item) =>
        ["pending", "partial"].includes(item.status) &&
        Number(item.outstanding_balance) > 0
    );
    state.selectedExtensionBalance = balance.outstanding_balance;
    state.selectedExtensionDueDate =
      openCharges[0]?.due_date || localDateValue();
    state.selectedExtensions = extensions;
    $("#extension-original-due-date").value =
      state.selectedExtensionDueDate;
    $("#extension-original-due-date").max = localDateValue();
    const promised = new Date();
    promised.setDate(promised.getDate() + 3);
    $("#extension-promised-date").value = localDateValue(promised);
    $("#extension-promised-date").min = localDateValue();
    $("#extension-reason").value =
      "Cliente solicita tiempo adicional para realizar el pago";
    $("#extension-authorized-by").value = state.user.display_name;
    $("#extension-evidence-reference").value = "";
    $("#extension-notes").value = "";
    $("#extension-resolution-action").value = "fulfill";
    $("#extension-resolution-reason").value = "";
    renderExtensionManagement();
  } catch (error) {
    $("#extension-dialog-status").textContent = error.message;
  }
}

function closeExtensionDialog() {
  $("#extension-dialog").close();
  state.selectedServiceId = null;
  state.selectedExtensions = [];
  state.selectedExtensionBalance = null;
  state.selectedExtensionDueDate = null;
}

async function saveExtension(event) {
  event.preventDefault();
  const serviceId = state.selectedServiceId;
  const submitButton = event.currentTarget.querySelector(
    'button[type="submit"]'
  );
  const statusBox = $("#extension-dialog-status");
  if (!serviceId) return;
  submitButton.disabled = true;
  statusBox.textContent = "";
  try {
    const saved = await api(
      `/api/v1/services/${serviceId}/extensions`,
      {
        method: "POST",
        body: JSON.stringify({
          original_due_date: $("#extension-original-due-date").value,
          promised_date: $("#extension-promised-date").value,
          reason: $("#extension-reason").value.trim(),
          authorized_by: $("#extension-authorized-by").value.trim(),
          evidence_reference:
            $("#extension-evidence-reference").value.trim(),
          notes: $("#extension-notes").value.trim() || null,
        }),
      }
    );
    state.selectedExtensions.push(saved);
    renderExtensionManagement();
    statusBox.textContent =
      "La prórroga quedó registrada y ya protege el servicio de una suspensión.";
  } catch (error) {
    statusBox.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

async function resolveExtension(event) {
  event.preventDefault();
  const serviceId = state.selectedServiceId;
  const activeExtension = state.selectedExtensions.find(
    (item) => item.status === "active"
  );
  const submitButton = event.currentTarget.querySelector(
    'button[type="submit"]'
  );
  const statusBox = $("#extension-dialog-status");
  if (!serviceId || !activeExtension) return;
  const action = $("#extension-resolution-action").value;
  submitButton.disabled = true;
  statusBox.textContent = "";
  try {
    const saved = await api(
      `/api/v1/services/${serviceId}/extensions/` +
      `${activeExtension.id}/${action}`,
      {
        method: "POST",
        body: JSON.stringify({
          performed_by: state.user.display_name,
          reason: $("#extension-resolution-reason").value.trim(),
        }),
      }
    );
    state.selectedExtensions = state.selectedExtensions.map(
      (item) => item.id === saved.id ? saved : item
    );
    renderExtensionManagement();
    statusBox.textContent =
      action === "fulfill"
        ? "La prórroga quedó marcada como cumplida."
        : "La prórroga quedó cancelada y el historial se conservó.";
  } catch (error) {
    statusBox.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

const agreementStatusLabels = {
  active: "Vigente",
  fulfilled: "Cumplido",
  cancelled: "Cancelado",
};

function renderPaymentAgreementManagement() {
  const service = state.services?.find(
    (item) => item.id === state.selectedServiceId
  );
  if (!service) return;
  const agreements = state.selectedPaymentAgreements || [];
  const activeAgreements = agreements.filter(
    (item) => item.status === "active"
  );
  const balance = Number(state.selectedAgreementBalance || 0);
  $("#agreement-summary").innerHTML = `
    <div>
      <span>Servicio</span>
      <strong>${escapeText(service.amr_code)}</strong>
    </div>
    <div>
      <span>Deuda actual</span>
      <strong>${formatMoney(balance)}</strong>
    </div>
    <div>
      <span>Convenios vigentes</span>
      <strong>${activeAgreements.length}</strong>
    </div>
  `;
  $("#agreement-history").innerHTML = agreements.length
    ? agreements
        .slice()
        .reverse()
        .map(
          (item) => {
            const optionalTerms = [
              item.promised_amount !== null
                ? `Monto ${formatMoney(item.promised_amount)}`
                : null,
              item.promised_date
                ? `Fecha ${formatDate(item.promised_date)}`
                : null,
              item.installment_count !== null
                ? `${item.installment_count} parcialidad${
                    item.installment_count === 1 ? "" : "es"
                  }`
                : null,
            ].filter(Boolean);
            return `
              <article class="history-item">
                <div>
                  <strong>${escapeText(item.folio)}</strong>
                  <span>${escapeText(
                    agreementStatusLabels[item.status] || item.status
                  )}</span>
                </div>
                <p>${escapeText(item.terms)}</p>
                <small>
                  Autorizó ${escapeText(item.authorized_by)} ·
                  ${optionalTerms.length
                    ? optionalTerms.map(escapeText).join(" · ")
                    : "Sin monto, fecha ni parcialidades pactadas"}
                </small>
                <small>
                  Evidencia ${item.has_evidence
                    ? "registrada"
                    : "no registrada"}
                </small>
                ${item.resolution_reason ? `
                  <small>
                    Resolución: ${escapeText(item.resolution_reason)}
                  </small>
                ` : ""}
              </article>
            `;
          }
        )
        .join("")
    : '<p class="empty-state">No hay convenios registrados.</p>';
  const canCreate = (
    hasCapability("billing.write") &&
    ["active", "suspended"].includes(service.status) &&
    balance > 0
  );
  $("#agreement-create-form").hidden = !canCreate;
  const createNote = $("#agreement-create-note");
  createNote.hidden = canCreate;
  if (!hasCapability("billing.write")) {
    createNote.textContent =
      "Tu cuenta puede consultar convenios, pero no registrarlos.";
  } else if (balance <= 0) {
    createNote.textContent =
      "No se puede crear un convenio porque el servicio no tiene deuda.";
  } else if (!["active", "suspended"].includes(service.status)) {
    createNote.textContent =
      "El estado actual del servicio no admite nuevos convenios.";
  } else {
    createNote.textContent = "";
  }
  const canResolve = (
    hasCapability("billing.approve") && activeAgreements.length > 0
  );
  $("#agreement-resolve-form").hidden = !canResolve;
  $("#agreement-resolve-note").hidden =
    canResolve || activeAgreements.length === 0;
  $("#agreement-resolution-id").innerHTML = activeAgreements
    .map(
      (item) =>
        `<option value="${item.id}">${escapeText(item.folio)} · ${escapeText(item.terms.slice(0, 70))}</option>`
    )
    .join("");
}

async function openPaymentAgreementDialog(service) {
  state.selectedServiceId = service.id;
  state.selectedPaymentAgreements = [];
  state.selectedAgreementBalance = null;
  $("#agreement-dialog-title").textContent =
    `Convenios · ${service.amr_code}`;
  $("#agreement-summary").innerHTML =
    '<p class="empty-state">Consultando convenios y deuda…</p>';
  $("#agreement-history").innerHTML = "";
  $("#agreement-create-form").hidden = true;
  $("#agreement-resolve-form").hidden = true;
  $("#agreement-create-note").hidden = true;
  $("#agreement-resolve-note").hidden = true;
  $("#agreement-dialog-status").textContent = "";
  $("#agreement-dialog").showModal();
  try {
    const [balance, agreements] = await Promise.all([
      api(`/api/v1/services/${service.id}/balance`),
      api(`/api/v1/services/${service.id}/payment-agreements`),
    ]);
    state.selectedAgreementBalance = balance.outstanding_balance;
    state.selectedPaymentAgreements = agreements;
    $("#agreement-terms").value = "";
    $("#agreement-promised-amount").value = "";
    $("#agreement-promised-amount").max =
      balance.outstanding_balance;
    $("#agreement-promised-date").value = "";
    $("#agreement-promised-date").min = localDateValue();
    $("#agreement-installments").value = "";
    $("#agreement-authorized-by").value = state.user.display_name;
    $("#agreement-evidence-reference").value = "";
    $("#agreement-notes").value = "";
    $("#agreement-resolution-action").value = "fulfill";
    $("#agreement-resolution-reason").value = "";
    renderPaymentAgreementManagement();
  } catch (error) {
    $("#agreement-dialog-status").textContent = error.message;
  }
}

function closePaymentAgreementDialog() {
  $("#agreement-dialog").close();
  state.selectedServiceId = null;
  state.selectedPaymentAgreements = [];
  state.selectedAgreementBalance = null;
}

function optionalNumberValue(selector) {
  const value = $(selector).value;
  return value === "" ? null : Number(value);
}

async function savePaymentAgreement(event) {
  event.preventDefault();
  const serviceId = state.selectedServiceId;
  const submitButton = event.currentTarget.querySelector(
    'button[type="submit"]'
  );
  const statusBox = $("#agreement-dialog-status");
  if (!serviceId) return;
  submitButton.disabled = true;
  statusBox.textContent = "";
  try {
    const saved = await api(
      `/api/v1/services/${serviceId}/payment-agreements`,
      {
        method: "POST",
        body: JSON.stringify({
          terms: $("#agreement-terms").value.trim(),
          promised_amount:
            optionalNumberValue("#agreement-promised-amount"),
          promised_date:
            $("#agreement-promised-date").value || null,
          installment_count:
            optionalNumberValue("#agreement-installments"),
          authorized_by:
            $("#agreement-authorized-by").value.trim(),
          evidence_reference:
            $("#agreement-evidence-reference").value.trim() || null,
          notes: $("#agreement-notes").value.trim() || null,
        }),
      }
    );
    state.selectedPaymentAgreements.push(saved);
    renderPaymentAgreementManagement();
    statusBox.textContent =
      "El convenio quedó registrado sin completar datos no acordados.";
  } catch (error) {
    statusBox.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

async function resolvePaymentAgreement(event) {
  event.preventDefault();
  const serviceId = state.selectedServiceId;
  const agreementId = $("#agreement-resolution-id").value;
  const action = $("#agreement-resolution-action").value;
  const submitButton = event.currentTarget.querySelector(
    'button[type="submit"]'
  );
  const statusBox = $("#agreement-dialog-status");
  if (!serviceId || !agreementId) return;
  submitButton.disabled = true;
  statusBox.textContent = "";
  try {
    const saved = await api(
      `/api/v1/services/${serviceId}/payment-agreements/` +
      `${agreementId}/${action}`,
      {
        method: "POST",
        body: JSON.stringify({
          performed_by: state.user.display_name,
          reason: $("#agreement-resolution-reason").value.trim(),
        }),
      }
    );
    state.selectedPaymentAgreements =
      state.selectedPaymentAgreements.map(
        (item) => item.id === saved.id ? saved : item
      );
    renderPaymentAgreementManagement();
    statusBox.textContent =
      action === "fulfill"
        ? "El convenio quedó marcado como cumplido."
        : "El convenio quedó cancelado y su historial se conservó.";
  } catch (error) {
    statusBox.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

async function saveInstallation(event) {
  event.preventDefault();
  const service = state.services?.find(
    (item) => item.id === state.selectedServiceId
  );
  const submitButton = event.currentTarget.querySelector(
    'button[type="submit"]'
  );
  const errorBox = $("#installation-form-error");
  if (!service) return;
  submitButton.disabled = true;
  errorBox.textContent = "";
  try {
    const result = $("#installation-coverage-result").value;
    const rejected = result === "out_of_coverage";
    const saved = await api(
      `/api/v1/services/${service.id}/installations`,
      {
        method: "POST",
        body: JSON.stringify({
          installation_type: "installation",
          coverage_result: result,
          coverage_checked_by: state.user.display_name,
          coverage_checked_at: new Date().toISOString(),
          special_equipment_notes:
            $("#installation-special-equipment").value.trim() || null,
          scheduled_for: rejected
            ? null
            : $("#installation-scheduled-for").value,
          cost: rejected ? "0" : $("#installation-cost").value,
          new_address: null,
          registered_by: state.user.display_name,
          notes: $("#installation-notes").value.trim() || null,
        }),
      }
    );
    service.has_scheduled_installation = saved.status === "scheduled";
    renderServices();
    closeInstallationDialog();
    setNotice(
      saved.status === "scheduled"
        ? saved.charge_id
          ? "La instalación quedó programada y su cargo fue generado."
          : "La instalación quedó programada sin cargo."
        : "La evaluación fuera de cobertura quedó registrada sin agenda ni cargo."
    );
  } catch (error) {
    errorBox.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

function renderPayments() {
  const body = $("#payments-body");
  const empty = $("#payments-empty");
  if (!state.payments) {
    body.innerHTML = "";
    empty.textContent = "Tu cuenta no puede consultar pagos.";
    empty.hidden = false;
    return;
  }
  const canApprove = hasCapability("billing.approve");
  const methodLabels = {
    cash: "Efectivo",
    bank_transfer: "Transferencia",
    bank_deposit: "Depósito",
    card: "Tarjeta",
    other: "Otro",
  };
  const statusLabels = {
    pending: "Pendiente",
    verified: "Verificado",
    rejected: "Rechazado",
    cancelled: "Cancelado",
  };
  const filteredPayments = state.payments.filter(
    (payment) =>
      state.paymentFilter === "all" ||
      payment.status === state.paymentFilter
  );
  const counts = state.payments.reduce(
    (acc, payment) => {
      acc[payment.status] = (acc[payment.status] || 0) + 1;
      return acc;
    },
    { all: state.payments.length }
  );
  $("#payment-queue-summary").innerHTML = `
    <article class="metric"><span>Total</span><strong>${counts.all || 0}</strong></article>
    <article class="metric"><span>Pendientes</span><strong>${counts.pending || 0}</strong></article>
    <article class="metric"><span>Verificados</span><strong>${counts.verified || 0}</strong></article>
    <article class="metric"><span>Rechazados</span><strong>${counts.rejected || 0}</strong></article>
  `;
  document.querySelectorAll(".payment-queue-tabs .tab-button").forEach((button) => {
    button.classList.toggle(
      "active",
      button.dataset.paymentFilter === state.paymentFilter
    );
  });
  body.innerHTML = filteredPayments
    .slice()
    .sort((a, b) => new Date(b.received_at) - new Date(a.received_at))
    .slice(0, 100)
    .map((payment) => `
      <tr>
        <td><strong>${escapeText(payment.reference || payment.id.slice(0, 8))}</strong></td>
        <td>${formatMoney(payment.declared_amount)}</td>
        <td>${escapeText(methodLabels[payment.method] || payment.method)}</td>
        <td>${formatDate(payment.received_at)}</td>
        <td>
          <span class="badge ${payment.status}">
            ${payment.applied_at
              ? "Aplicado"
              : escapeText(statusLabels[payment.status] || payment.status)}
          </span>
        </td>
        ${canApprove ? `
          <td>
            ${payment.status === "pending" ? `
              <button
                class="row-action payment-review-action"
                type="button"
                data-payment-id="${payment.id}"
              >Revisar</button>
            ` : payment.status === "verified" && !payment.applied_at ? `
              <button
                class="row-action payment-apply-action"
                type="button"
                data-payment-id="${payment.id}"
              >Aplicar</button>
            ` : "—"}
          </td>
        ` : ""}
      </tr>
    `)
    .join("");
  empty.textContent =
    state.paymentFilter === "all"
      ? "Aún no hay pagos registrados."
      : "No hay pagos en este estado.";
  empty.hidden = filteredPayments.length > 0;
}

function updatePaymentServices() {
  const customerId = $("#payment-customer").value;
  const services = (state.services || []).filter(
    (service) => service.current_customer_id === customerId
  );
  $("#payment-service").innerHTML = [
    '<option value="">Sin servicio específico</option>',
    ...services.map(
      (service) =>
        `<option value="${service.id}">${escapeText(service.amr_code)} · ${escapeText(service.plan_name)}</option>`
    ),
  ].join("");
}

function customerDisplayLabel(customer) {
  const primaryPhone = customer.phones?.[0] || "";
  return [customer.full_name, customer.amr_code, primaryPhone]
    .filter(Boolean)
    .join(" · ");
}

function customerSearchTokens(customer) {
  return [
    customer.full_name,
    customer.amr_code,
    ...(customer.phones || []),
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function syncPaymentCustomerSelection() {
  const search = $("#payment-customer-search").value.trim().toLowerCase();
  const matched = (state.customers || []).find((customer) =>
    customerSearchTokens(customer).includes(search)
  );
  $("#payment-customer").value = matched?.id || "";
  updatePaymentServices();
  const services = (state.services || []).filter(
    (service) => service.current_customer_id === $("#payment-customer").value
  );
  if (services.length === 1) {
    $("#payment-service").value = services[0].id;
  }
}

function localDateTimeValue(date = new Date()) {
  const localTime = new Date(
    date.getTime() - date.getTimezoneOffset() * 60000
  );
  return localTime.toISOString().slice(0, 16);
}

function openPaymentDialog() {
  if (!Array.isArray(state.customers)) {
    setNotice("Tu cuenta no tiene permiso para consultar clientes y registrar pagos.");
    return false;
  }
  if (state.customers.length === 0) {
    setNotice("Aun no hay clientes registrados. Primero importa o registra clientes antes de recibir comprobantes de pago.");
    return false;
  }
  $("#payment-customer").innerHTML = (state.customers || [])
    .map(
      (customer) =>
        `<option value="${customer.id}">${escapeText(customer.full_name)}</option>`
    )
    .join("");
  $("#payment-customer-search").value = "";
  $("#payment-customer-options").innerHTML = (state.customers || [])
    .map(
      (customer) =>
        `<option value="${escapeText(customerDisplayLabel(customer))}"></option>`
    )
    .join("");
  $("#payment-amount").value = "";
  $("#payment-method").value = "cash";
  $("#payment-declared-at").value = localDateTimeValue();
  $("#payment-reference").value = "";
  $("#payment-origin-holder").value = "";
  $("#payment-proof-reference").value = "";
  $("#payment-proof-file").value = "";
  $("#payment-notes").value = "";
  $("#payment-form-error").textContent = "";
  updatePaymentServices();
  $("#payment-dialog").showModal();
  $("#payment-customer-search").focus();
  return true;
}

function closePaymentDialog() {
  $("#payment-dialog").close();
}

async function savePayment(event) {
  event.preventDefault();
  const submitButton = event.currentTarget.querySelector(
    'button[type="submit"]'
  );
  const errorBox = $("#payment-form-error");
  submitButton.disabled = true;
  errorBox.textContent = "";
  try {
    const declaredAt = new Date($("#payment-declared-at").value);
    if (Number.isNaN(declaredAt.getTime())) {
      throw new Error("Indica una fecha válida para el pago.");
    }
    if (!$("#payment-customer").value) {
      throw new Error("Selecciona un cliente válido de la lista.");
    }
    const optionalText = (selector) => $(selector).value.trim() || null;
    const payload = new FormData();
    payload.append("customer_id", $("#payment-customer").value);
    if ($("#payment-service").value) {
      payload.append("service_id", $("#payment-service").value);
    }
    payload.append("declared_amount", $("#payment-amount").value);
    payload.append("declared_at", declaredAt.toISOString());
    payload.append("method", $("#payment-method").value);
    if (optionalText("#payment-reference")) {
      payload.append("reference", optionalText("#payment-reference"));
    }
    if (optionalText("#payment-origin-holder")) {
      payload.append(
        "origin_account_holder",
        optionalText("#payment-origin-holder")
      );
    }
    if (optionalText("#payment-proof-reference")) {
      payload.append(
        "proof_reference",
        optionalText("#payment-proof-reference")
      );
    }
    if (optionalText("#payment-notes")) {
      payload.append("notes", optionalText("#payment-notes"));
    }
    payload.append("received_by", state.user.display_name);
    const proofFile = $("#payment-proof-file").files?.[0];
    if (proofFile) {
      payload.append("proof_file", proofFile);
    }
    const saved = await api("/api/v1/payments/receipts", {
      method: "POST",
      body: payload,
    });
    if (state.payments) {
      state.payments.push(saved);
      renderPayments();
      renderOverview();
    }
    closePaymentDialog();
    setNotice(
      "El pago quedó pendiente de verificación; la deuda todavía no cambió."
    );
  } catch (error) {
    errorBox.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

async function loadPaymentProof(payment) {
  const blob = await apiBlob(`/api/v1/payments/${payment.id}/proof`);
  return URL.createObjectURL(blob);
}

function paymentCustomerName(payment) {
  return (
    state.customers?.find(
      (customer) => customer.id === payment.customer_id
    )?.full_name || "Cliente no visible"
  );
}

function paymentSummary(payment, amount) {
  return `
    <div>
      <span>Cliente</span>
      <strong>${escapeText(paymentCustomerName(payment))}</strong>
    </div>
    <div>
      <span>Monto</span>
      <strong>${formatMoney(amount)}</strong>
    </div>
    <div>
      <span>Comprobante</span>
      <strong>${payment.has_proof ? "Registrado" : "No registrado"}</strong>
    </div>
  `;
}

function selectedPayment() {
  return state.payments?.find(
    (payment) => payment.id === state.selectedPaymentId
  );
}

function replacePayment(saved) {
  const index = state.payments?.findIndex(
    (payment) => payment.id === saved.id
  );
  if (index >= 0) state.payments[index] = saved;
  renderPayments();
  renderOverview();
}

function openPaymentReviewDialog(payment) {
  state.selectedPaymentId = payment.id;
  $("#payment-review-summary").innerHTML = paymentSummary(
    payment,
    payment.declared_amount
  );
  $("#payment-confirmed-amount").value = payment.declared_amount;
  $("#payment-decision-notes").value = "";
  $("#payment-review-error").textContent = "";
  $("#payment-review-dialog").showModal();
  $("#payment-confirmed-amount").focus();
  const previewBox = $("#payment-proof-preview");
  previewBox.textContent = payment.has_proof
    ? "Cargando comprobante..."
    : "Sin archivo adjunto.";
  if (payment.has_proof) {
    void (async () => {
      try {
        const proofUrl = await loadPaymentProof(payment);
        const fileExt = (payment.proof_reference || "")
          .split(".")
          .pop()
          ?.toLowerCase();
        previewBox.innerHTML = fileExt === "pdf"
          ? `<iframe class="proof-preview-frame" src="${proofUrl}" title="Comprobante de pago"></iframe>`
          : `<img class="proof-preview-image" src="${proofUrl}" alt="Comprobante de pago">`;
      } catch (error) {
        previewBox.textContent = error.message;
      }
    })();
  }
}

function closePaymentReviewDialog() {
  $("#payment-review-dialog").close();
  state.selectedPaymentId = null;
  $("#payment-proof-preview").textContent = "Sin archivo adjunto.";
}

function setPaymentReviewBusy(busy) {
  $("#payment-review-form")
    .querySelectorAll("button")
    .forEach((button) => {
      button.disabled = busy;
    });
}

async function verifySelectedPayment(event) {
  event.preventDefault();
  const payment = selectedPayment();
  const errorBox = $("#payment-review-error");
  const notes = $("#payment-decision-notes").value.trim();
  const confirmedAmount = $("#payment-confirmed-amount").value;
  errorBox.textContent = "";
  if (!payment) return;
  if (
    Number(confirmedAmount) !== Number(payment.declared_amount) &&
    !notes
  ) {
    errorBox.textContent =
      "Explica por qué el monto confirmado es distinto al declarado.";
    return;
  }
  setPaymentReviewBusy(true);
  try {
    const saved = await api(`/api/v1/payments/${payment.id}/verify`, {
      method: "POST",
      body: JSON.stringify({
        confirmed_amount: confirmedAmount,
        verified_by: state.user.display_name,
        notes: notes || null,
      }),
    });
    replacePayment(saved);
    closePaymentReviewDialog();
    setNotice(
      "El pago quedó verificado. Aún falta aplicarlo para reducir la deuda."
    );
  } catch (error) {
    errorBox.textContent = error.message;
  } finally {
    setPaymentReviewBusy(false);
  }
}

async function decideSelectedPayment(action) {
  const payment = selectedPayment();
  const errorBox = $("#payment-review-error");
  const reason = $("#payment-decision-notes").value.trim();
  errorBox.textContent = "";
  if (!payment) return;
  if (reason.length < 3) {
    errorBox.textContent =
      "Escribe un motivo de al menos tres caracteres.";
    return;
  }
  setPaymentReviewBusy(true);
  try {
    const saved = await api(`/api/v1/payments/${payment.id}/${action}`, {
      method: "POST",
      body: JSON.stringify({
        performed_by: state.user.display_name,
        reason,
      }),
    });
    replacePayment(saved);
    closePaymentReviewDialog();
    setNotice(
      action === "reject"
        ? "El pago fue rechazado y permanece en el historial."
        : "El registro del pago fue cancelado y permanece en el historial."
    );
  } catch (error) {
    errorBox.textContent = error.message;
  } finally {
    setPaymentReviewBusy(false);
  }
}

function openPaymentApplyDialog(payment) {
  state.selectedPaymentId = payment.id;
  $("#payment-apply-summary").innerHTML = paymentSummary(
    payment,
    payment.confirmed_amount
  );
  $("#payment-apply-reason").value =
    "Aplicación automática a los cargos abiertos más antiguos";
  $("#payment-apply-error").textContent = "";
  $("#payment-apply-dialog").showModal();
  $("#payment-apply-reason").focus();
}

function closePaymentApplyDialog() {
  $("#payment-apply-dialog").close();
  state.selectedPaymentId = null;
}

async function applySelectedPayment(event) {
  event.preventDefault();
  const payment = selectedPayment();
  const submitButton = event.currentTarget.querySelector(
    'button[type="submit"]'
  );
  const errorBox = $("#payment-apply-error");
  errorBox.textContent = "";
  if (!payment) return;
  submitButton.disabled = true;
  try {
    const result = await api(`/api/v1/payments/${payment.id}/apply`, {
      method: "POST",
      body: JSON.stringify({
        applied_by: state.user.display_name,
        reason: $("#payment-apply-reason").value.trim(),
      }),
    });
    payment.applied_at = new Date().toISOString();
    payment.applied_by = state.user.display_name;
    renderPayments();
    closePaymentApplyDialog();
    setNotice(
      `Pago aplicado: ${formatMoney(result.allocated_amount)} a deuda` +
      ` y ${formatMoney(result.credit_generated)} a saldo a favor.`
    );
  } catch (error) {
    errorBox.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

async function openAccountDialog(customer) {
  $("#account-dialog-title").textContent = customer.full_name;
  $("#account-summary").innerHTML = "";
  $("#account-charges-body").innerHTML = "";
  $("#account-empty").hidden = true;
  $("#account-error").textContent = "";
  $("#account-dialog").showModal();
  try {
    const [balance, charges] = await Promise.all([
      api(`/api/v1/customers/${customer.id}/balance`),
      api(`/api/v1/customers/${customer.id}/charges`),
    ]);
    $("#account-summary").innerHTML = `
      <div>
        <span>Deuda total</span>
        <strong>${formatMoney(balance.outstanding_balance)}</strong>
      </div>
      <div>
        <span>Deuda vencida</span>
        <strong>${formatMoney(balance.overdue_balance)}</strong>
      </div>
      <div>
        <span>Saldo a favor</span>
        <strong>${formatMoney(balance.credit_balance)}</strong>
      </div>
    `;
    $("#account-charges-body").innerHTML = charges
      .slice()
      .sort((a, b) => new Date(b.due_date) - new Date(a.due_date))
      .map((charge) => `
        <tr>
          <td><strong>${escapeText(charge.description)}</strong></td>
          <td>${formatDate(charge.due_date)}</td>
          <td>${formatMoney(charge.amount)}</td>
          <td>${formatMoney(charge.outstanding_balance)}</td>
          <td>
            <span class="badge ${charge.status}">
              ${escapeText(charge.status)}
            </span>
          </td>
        </tr>
      `)
      .join("");
    $("#account-empty").textContent = "Este cliente aún no tiene cargos.";
    $("#account-empty").hidden = charges.length > 0;
  } catch (error) {
    $("#account-error").textContent = error.message;
  }
}

function closeAccountDialog() {
  $("#account-dialog").close();
}

function localDateTimeValue(date = new Date()) {
  const localTime = new Date(
    date.getTime() - date.getTimezoneOffset() * 60000
  );
  return localTime.toISOString().slice(0, 16);
}

function incidentServiceLabel(serviceId) {
  const service = state.services?.find((item) => item.id === serviceId);
  return service
    ? `${service.amr_code} · ${service.plan_name}`
    : serviceId;
}

function selectedIncident() {
  return state.incidents?.find((item) => item.id === state.selectedIncidentId);
}

function upsertIncident(saved) {
  if (!state.incidents) state.incidents = [];
  const index = state.incidents.findIndex((item) => item.id === saved.id);
  if (index >= 0) state.incidents[index] = saved;
  else state.incidents.push(saved);
  state.incidents.sort(
    (a, b) => new Date(b.started_at) - new Date(a.started_at)
  );
  renderIncidents();
}

function renderIncidents() {
  const body = $("#incidents-body");
  const empty = $("#incidents-empty");
  if (!state.incidents) {
    body.innerHTML = "";
    empty.textContent = "Tu cuenta no puede consultar incidencias.";
    empty.hidden = false;
    return;
  }
  const canRead = hasCapability("incidents.read");
  body.innerHTML = state.incidents
    .map((incident) => `
      <tr>
        <td>
          <strong>${escapeText(incident.title)}</strong>
          <small class="table-subtitle">
            ${escapeText(incident.cause || incident.notes || "Sin causa registrada")}
          </small>
        </td>
        <td>
          ${escapeText(incident.tower_name || "Sin torre")}
          <small class="table-subtitle">
            ${escapeText(incident.access_point_name || "Sin AP")}
          </small>
        </td>
        <td>${formatDate(incident.started_at)}</td>
        <td>${incident.impacts?.length || 0}</td>
        <td><span class="badge ${incident.status}">${escapeText(incident.status)}</span></td>
        ${canRead ? `
          <td>
            <button
              class="row-action view-incident"
              type="button"
              data-incident-id="${incident.id}"
            >Seguimiento</button>
          </td>
        ` : ""}
      </tr>
    `)
    .join("");
  empty.textContent = "Aun no hay incidencias registradas.";
  empty.hidden = state.incidents.length > 0;
}

function openIncidentDialog() {
  $("#incident-title").value = "";
  $("#incident-tower").value = "";
  $("#incident-ap").value = "";
  $("#incident-started-at").value = localDateTimeValue();
  $("#incident-reported-by").value = state.user.display_name;
  $("#incident-notes").value = "";
  $("#incident-services").innerHTML = (state.services || [])
    .map((service) => `
      <option value="${service.id}">
        ${escapeText(service.amr_code)} · ${escapeText(service.plan_name)}
      </option>
    `)
    .join("");
  $("#incident-form-error").textContent = "";
  $("#incident-dialog").showModal();
  $("#incident-title").focus();
}

function closeIncidentDialog() {
  $("#incident-dialog").close();
}

async function saveIncident(event) {
  event.preventDefault();
  const submitButton = event.currentTarget.querySelector(
    'button[type="submit"]'
  );
  const errorBox = $("#incident-form-error");
  const serviceIds = Array.from($("#incident-services").selectedOptions)
    .map((option) => option.value);
  submitButton.disabled = true;
  errorBox.textContent = "";
  try {
    const saved = await api("/api/v1/incidents", {
      method: "POST",
      body: JSON.stringify({
        title: $("#incident-title").value.trim(),
        tower_name: $("#incident-tower").value.trim() || null,
        access_point_name: $("#incident-ap").value.trim() || null,
        started_at: new Date($("#incident-started-at").value).toISOString(),
        reported_by: $("#incident-reported-by").value.trim(),
        service_ids: serviceIds,
        notes: $("#incident-notes").value.trim() || null,
      }),
    });
    upsertIncident(saved);
    closeIncidentDialog();
    setNotice("La incidencia quedo registrada para seguimiento operativo.");
  } catch (error) {
    errorBox.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

function renderIncidentWorkspace(incident) {
  const canWrite = hasCapability("incidents.write");
  const canCompensate = hasCapability("incidents.compensate");
  const open = incident.status === "open";
  const affectedIds = new Set(
    (incident.impacts || []).map((impact) => impact.service_id)
  );
  const availableServices = (state.services || [])
    .filter((service) => !affectedIds.has(service.id));
  $("#incident-detail-title").textContent = incident.title;
  $("#incident-detail-summary").innerHTML = `
    <div>
      <span>Estado</span>
      <strong>${escapeText(incident.status)}</strong>
    </div>
    <div>
      <span>Inicio</span>
      <strong>${formatDate(incident.started_at)}</strong>
    </div>
    <div>
      <span>Duracion</span>
      <strong>${incident.duration_minutes ?? "Abierta"} min</strong>
    </div>
  `;
  $("#incident-workspace").innerHTML = `
    <section class="cancellation-stage-card">
      <div class="stage-status">
        <h3>Servicios afectados</h3>
        <span class="badge ${incident.status}">${escapeText(incident.status)}</span>
      </div>
      <div class="extension-history">
        ${(incident.impacts || []).map((impact) => `
          <article class="history-item">
            <strong>${escapeText(incidentServiceLabel(impact.service_id))}</strong>
            <span>
              Afectado ${formatDate(impact.affected_from)} ·
              ${impact.restored_at
                ? `restaurado ${formatDate(impact.restored_at)}`
                : "pendiente de restauracion"}
            </span>
            <span>Compensacion: ${formatMoney(impact.compensation_amount)}</span>
            ${canWrite && open && !impact.restored_at ? `
              <form class="incident-restore-form" data-impact-id="${impact.id}">
                <div class="form-grid">
                  <label>
                    Restaurado en
                    <input
                      name="restored_at"
                      type="datetime-local"
                      value="${localDateTimeValue()}"
                      required
                    >
                  </label>
                  <div class="dialog-actions">
                    <button class="primary-button" type="submit">
                      Registrar restauracion
                    </button>
                  </div>
                </div>
              </form>
            ` : ""}
            ${canCompensate && incident.status === "resolved" && !impact.compensation_movement_id ? `
              <form class="incident-compensation-form" data-impact-id="${impact.id}">
                <div class="form-grid">
                  <label>
                    Monto
                    <input name="amount" type="number" min="0.01" step="0.01" required>
                  </label>
                  <label>
                    Autorizo
                    <input
                      name="authorized_by"
                      value="${escapeText(state.user.display_name)}"
                      minlength="2"
                      maxlength="150"
                      required
                    >
                  </label>
                  <label class="full-row">
                    Motivo
                    <textarea name="reason" rows="2" minlength="3" maxlength="1000" required></textarea>
                  </label>
                  <div class="dialog-actions full-row">
                    <button class="primary-button" type="submit">
                      Aplicar compensacion
                    </button>
                  </div>
                </div>
              </form>
            ` : ""}
          </article>
        `).join("") || '<p class="empty-state">Sin servicios afectados.</p>'}
      </div>
    </section>
    ${canWrite && open ? `
      <form id="incident-add-impact-form" class="cancellation-stage-card">
        <h3>Agregar servicio afectado</h3>
        <div class="form-grid">
          <label>
            Servicio
            <select id="incident-impact-service" required>
              ${availableServices.map((service) => `
                <option value="${service.id}">
                  ${escapeText(service.amr_code)} · ${escapeText(service.plan_name)}
                </option>
              `).join("")}
            </select>
          </label>
          <label>
            Afectado desde
            <input
              id="incident-impact-from"
              type="datetime-local"
              value="${localDateTimeValue()}"
              required
            >
          </label>
          <label class="full-row">
            Notas
            <textarea id="incident-impact-notes" rows="2" maxlength="1000"></textarea>
          </label>
          <div class="dialog-actions full-row">
            <button
              class="primary-button"
              type="submit"
              ${availableServices.length ? "" : "disabled"}
            >Agregar afectacion</button>
          </div>
        </div>
      </form>
      <form id="incident-resolve-form" class="cancellation-stage-card">
        <h3>Cerrar incidencia</h3>
        <div class="form-grid">
          <label>
            Resuelta en
            <input
              id="incident-resolved-at"
              type="datetime-local"
              value="${localDateTimeValue()}"
              required
            >
          </label>
          <label>
            Responsable
            <input
              id="incident-responsible"
              value="${escapeText(state.user.display_name)}"
              minlength="2"
              maxlength="150"
              required
            >
          </label>
          <label class="full-row">
            Causa
            <textarea id="incident-cause" rows="3" minlength="3" maxlength="2000" required></textarea>
          </label>
          <div class="dialog-actions full-row">
            <button class="primary-button" type="submit">Cerrar incidencia</button>
          </div>
        </div>
      </form>
    ` : ""}
  `;
}

function supportCustomerLabel(customer) {
  const amr = state.services?.find((service) => service.current_customer_id === customer.id)?.amr_code;
  return `${customer.full_name}${amr ? ` · ${amr}` : ""}`;
}

function supportServiceOptions(customerId) {
  return (state.services || [])
    .filter((service) => service.current_customer_id === customerId)
    .map(
      (service) =>
        `<option value="${service.id}">${escapeText(service.amr_code)} · ${escapeText(service.address)}</option>`
    )
    .join("");
}

function selectedSupportTicket() {
  return state.supportTickets?.find(
    (item) => item.id === state.selectedSupportTicketId
  );
}

function upsertSupportTicket(saved) {
  if (!state.supportTickets) state.supportTickets = [];
  const index = state.supportTickets.findIndex((item) => item.id === saved.id);
  if (index >= 0) state.supportTickets[index] = saved;
  else state.supportTickets.push(saved);
  state.supportTickets.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  renderSupportTickets();
}

function renderSupportTickets() {
  const body = $("#support-tickets-body");
  const empty = $("#support-tickets-empty");
  if (!state.supportTickets) {
    body.innerHTML = "";
    empty.textContent = "Tu cuenta no puede consultar tickets de soporte.";
    empty.hidden = false;
    return;
  }
  const canRead = hasCapability("support.read");
  body.innerHTML = state.supportTickets.map((ticket) => `
    <tr>
      <td><strong>${escapeText(ticket.title)}</strong><small class="table-subtitle">${escapeText(ticket.description.slice(0, 70))}${ticket.description.length > 70 ? "…" : ""}</small></td>
      <td>${escapeText(supportCustomerLabel(state.customers?.find((customer) => customer.id === ticket.customer_id) || { full_name: ticket.customer_id }))}</td>
      <td>${escapeText(ticket.category)}</td>
      <td>${escapeText(ticket.priority)}</td>
      <td><span class="badge ${ticket.status}">${escapeText(ticket.status)}</span></td>
      ${canRead ? `<td><button class="row-action view-support-ticket" type="button" data-support-ticket-id="${ticket.id}">Seguimiento</button></td>` : ""}
    </tr>
  `).join("");
  empty.textContent = "Aún no hay tickets de soporte.";
  empty.hidden = state.supportTickets.length > 0;
}

function roleLabel(role) {
  const labels = {
    administrator: "Administrador",
    customer_service: "Atención a clientes",
    network_technician: "Técnico de red",
    installer: "Instalador",
    read_only: "Solo lectura",
  };
  return labels[role] || role;
}

function permissionsText(user) {
  return user.permissions?.length
    ? user.permissions
        .map((permission) => USER_PERMISSION_LABELS[permission] || permission)
        .join(", ")
    : "Sin permisos explícitos";
}

function renderUserPermissionsGrid(selectedPermissions = [], selectedRole = null) {
  const container = $("#user-permissions-grid");
  if (!container) return;
  const selected = new Set(selectedPermissions);
  container.innerHTML = `
    <div class="permission-presets">
      ${Object.entries(USER_ROLE_PRESETS)
        .map(
          ([role, permissions]) => `
            <button
              type="button"
              class="preset-chip ${role === selectedRole ? "active" : ""}"
              data-role-preset="${role}"
            >
              ${escapeText(roleLabel(role))}
              <small>${permissions.length} permisos base</small>
            </button>
          `
        )
        .join("")}
    </div>
    ${USER_PERMISSION_GROUPS.map(
      (group) => `
        <section class="permission-group">
          <header class="permission-group-header">
            <h3>${escapeText(group.label)}</h3>
            <span>${group.permissions.length} opciones</span>
          </header>
          <div class="permission-group-options">
            ${group.permissions
              .map(
                ([permission, label]) => `
                  <label class="permission-option">
                    <input
                      type="checkbox"
                      name="user-permission"
                      value="${permission}"
                      ${selected.has(permission) ? "checked" : ""}
                    >
                    <span>
                      <strong>${escapeText(label)}</strong>
                    </span>
                  </label>
                `
              )
              .join("")}
          </div>
        </section>
      `
    ).join("")}
  `;
}

function applyUserRolePreset(role) {
  $("#user-role").value = role;
  renderUserPermissionsGrid(USER_ROLE_PRESETS[role] || [], role);
}

function renderOperatorUsers() {
  const body = $("#users-body");
  const empty = $("#users-empty");
  const actionHeader = document.querySelector(".user-action-column");
  if (!state.operatorUsers) {
    body.innerHTML = "";
    empty.textContent = "Tu cuenta no puede consultar usuarios.";
    empty.hidden = false;
    if (actionHeader) actionHeader.hidden = true;
    return;
  }
  const isAdmin = state.user?.role === "administrator";
  if (actionHeader) actionHeader.hidden = !isAdmin;
  body.innerHTML = state.operatorUsers
    .map((user) => `
      <tr>
        <td>
          <strong>${escapeText(user.display_name)}</strong>
          <small class="table-subtitle">${escapeText(user.username)}</small>
        </td>
        <td>${escapeText(roleLabel(user.role))}</td>
        <td><span class="badge ${user.is_active ? "active" : "cancelled"}">${user.is_active ? "Activo" : "Inactivo"}</span></td>
        <td>${escapeText(permissionsText(user))}</td>
        ${isAdmin ? `
          <td>
            <button class="row-action edit-user" type="button" data-user-id="${user.id}">Editar</button>
            <button class="row-action reset-user-password" type="button" data-user-id="${user.id}">Contraseña</button>
            <button class="row-action revoke-user-sessions" type="button" data-user-id="${user.id}">Cerrar dispositivos</button>
            ${user.is_active ? `<button class="row-action deactivate-user" type="button" data-user-id="${user.id}">Desactivar</button>` : ""}
          </td>
        ` : ""}
      </tr>
    `)
    .join("");
  empty.textContent = "Aún no hay usuarios registrados.";
  empty.hidden = state.operatorUsers.length > 0;
}

function openUserDialog(user = null) {
  state.selectedOperatorUserId = user?.id || null;
  $("#user-dialog-title").textContent = user ? "Editar usuario" : "Nuevo usuario";
  $("#user-username").value = user?.username || "";
  $("#user-display-name").value = user?.display_name || "";
  $("#user-role").value = user?.role || "customer_service";
  $("#user-password").value = "";
  $("#user-password").required = !user;
  $("#user-password").placeholder = user
    ? "Dejar vacío para conservar la contraseña actual"
    : "";
  renderUserPermissionsGrid(user?.permissions || [], $("#user-role").value);
  $("#user-form-error").textContent = "";
  $("#user-dialog").showModal();
  $("#user-username").focus();
}

function closeUserDialog() {
  $("#user-dialog").close();
  state.selectedOperatorUserId = null;
}

async function saveUser(event) {
  event.preventDefault();
  const submitButton = event.currentTarget.querySelector('button[type="submit"]');
  const errorBox = $("#user-form-error");
  const isEditing = Boolean(state.selectedOperatorUserId);
  submitButton.disabled = true;
  errorBox.textContent = "";
  try {
    const permissions = Array.from(
      document.querySelectorAll('input[name="user-permission"]:checked')
    ).map((input) => input.value);
    const payload = {
      username: $("#user-username").value.trim(),
      display_name: $("#user-display-name").value.trim(),
      role: $("#user-role").value,
    };
    let saved;
    if (state.selectedOperatorUserId) {
      saved = await api(`/api/v1/auth/users/${state.selectedOperatorUserId}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      saved = await api(`/api/v1/auth/users/${state.selectedOperatorUserId}/permissions`, {
        method: "PUT",
        body: JSON.stringify({
          permissions,
          reason: "Actualización desde la UI administrativa",
        }),
      });
    } else {
      saved = await api("/api/v1/auth/users", {
        method: "POST",
        body: JSON.stringify({
          ...payload,
          password: $("#user-password").value,
          permissions,
        }),
      });
    }
    if (state.operatorUsers) {
      const index = state.operatorUsers.findIndex((item) => item.id === saved.id);
      if (index >= 0) state.operatorUsers[index] = saved;
      else state.operatorUsers.push(saved);
      state.operatorUsers.sort((a, b) => a.display_name.localeCompare(b.display_name));
      renderOperatorUsers();
    }
    closeUserDialog();
    setNotice(isEditing ? "El usuario quedó actualizado." : "El usuario quedó registrado.");
  } catch (error) {
    errorBox.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

async function editSelectedUser(user) {
  openUserDialog(user);
}

async function resetSelectedUserPassword(user) {
  const newPassword = window.prompt(`Nueva contraseña para ${user.display_name}`);
  if (!newPassword) return;
  await api(`/api/v1/auth/users/${user.id}/password`, {
    method: "POST",
    body: JSON.stringify({
      new_password: newPassword,
      reason: "Restablecimiento solicitado desde UI",
    }),
  });
  setNotice("La contraseña quedó restablecida.");
}

async function deactivateSelectedUser(user) {
  await api(`/api/v1/auth/users/${user.id}/deactivate`, {
    method: "POST",
    body: JSON.stringify({
      reason: "Desactivado desde UI",
    }),
  });
  const index = state.operatorUsers?.findIndex((item) => item.id === user.id);
  if (index >= 0) state.operatorUsers[index].is_active = false;
  renderOperatorUsers();
  setNotice("El usuario quedó desactivado.");
}

async function revokeOtherUserSessions(user) {
  const label = user.id === state.user?.id
    ? "Se cerraran las sesiones de tus otros dispositivos. Esta sesion continuara abierta."
    : `Se cerraran todas las sesiones activas de ${user.display_name}. Tendra que iniciar sesion nuevamente.`;
  if (!window.confirm(label)) return;
  const result = await api(`/api/v1/auth/users/${user.id}/sessions/revoke-others`, {
    method: "POST",
  });
  const count = result.revoked_sessions || 0;
  setNotice(count
    ? `Se cerraron ${count} sesion(es) en otros dispositivos.`
    : "No habia otras sesiones activas para cerrar.");
}

function renderNetworkDevices() {
  const devices = state.networkDevices || [];
  const summary = state.networkSummary;
  $("#network-summary").textContent = summary
    ? `${summary.online} en línea · ${summary.offline} sin conexión · ${summary.total_devices} equipos registrados`
    : "No hay información de red disponible.";
  $("#network-devices-table").innerHTML = devices.length
    ? devices.map((item) => {
        const details = item.observed_details || {};
        const lastSeen = item.last_seen_at ? new Date(item.last_seen_at).toLocaleString("es-MX") : "Sin lectura";
        return `<tr><td><strong>${escapeText(item.display_name)}</strong><br><span class="muted-copy">${escapeText(item.mac_address || "")}</span></td><td>${item.device_type === "access_point" ? "AP" : item.device_type === "station" ? "CPE" : "Otro"}</td><td><span class="badge ${escapeText(item.current_status)}">${escapeText(item.current_status)}</span></td><td>${escapeText(item.management_ip || "—")}</td><td>${details.signal ?? "—"}${details.signal != null ? " dBm" : ""}</td><td>${details.frequency ?? "—"}${details.frequency != null ? " MHz" : ""}</td><td>${escapeText(lastSeen)}</td></tr>`;
      }).join("")
    : '<tr><td colspan="7" class="empty-state">Aún no hay dispositivos sincronizados.</td></tr>';
}

function openSupportTicketDialog() {
  $("#support-ticket-customer").innerHTML = (state.customers || [])
    .map((customer) => `<option value="${customer.id}">${escapeText(supportCustomerLabel(customer))}</option>`)
    .join("");
  const customerId = $("#support-ticket-customer").value;
  $("#support-ticket-service").innerHTML = `<option value="">Sin servicio específico</option>${supportServiceOptions(customerId)}`;
  $("#support-ticket-title").value = "";
  $("#support-ticket-description").value = "";
  $("#support-ticket-evidence").value = "";
  $("#support-ticket-reported-by").value = state.user.display_name;
  $("#support-ticket-form-error").textContent = "";
  $("#support-ticket-dialog").showModal();
}

function closeSupportTicketDialog() {
  $("#support-ticket-dialog").close();
}

async function saveSupportTicket(event) {
  event.preventDefault();
  const submitButton = event.currentTarget.querySelector('button[type="submit"]');
  const errorBox = $("#support-ticket-form-error");
  submitButton.disabled = true;
  errorBox.textContent = "";
  try {
    const saved = await api("/api/v1/support-tickets", {
      method: "POST",
      body: JSON.stringify({
        customer_id: $("#support-ticket-customer").value,
        service_id: $("#support-ticket-service").value || null,
        category: $("#support-ticket-category").value,
        priority: $("#support-ticket-priority").value,
        title: $("#support-ticket-title").value.trim(),
        description: $("#support-ticket-description").value.trim(),
        evidence_reference: $("#support-ticket-evidence").value.trim() || null,
        reported_by: $("#support-ticket-reported-by").value.trim(),
        created_by: state.user.display_name,
      }),
    });
    upsertSupportTicket(saved);
    closeSupportTicketDialog();
    setNotice("El ticket quedó registrado para atención y clasificación.");
  } catch (error) {
    errorBox.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

function renderSupportTicketWorkspace(ticket) {
  $("#support-ticket-detail-title").textContent = ticket.title;
  $("#support-ticket-detail-summary").innerHTML = `
    <div><span>Estado</span><strong>${escapeText(ticket.status)}</strong></div>
    <div><span>Categoría</span><strong>${escapeText(ticket.category)}</strong></div>
    <div><span>Prioridad</span><strong>${escapeText(ticket.priority)}</strong></div>
  `;
  const canWrite = hasCapability("support.write");
  const canResolve = hasCapability("support.write");
  $("#support-ticket-workspace").innerHTML = `
    <section class="cancellation-stage-card">
      <div class="stage-status">
        <h3>Descripción</h3>
        <span class="badge ${ticket.status}">${escapeText(ticket.status)}</span>
      </div>
      <div class="extension-history">
        <article class="history-item">
          <strong>${escapeText(ticket.description)}</strong>
          <span>Reportado por ${escapeText(ticket.reported_by)} · ${formatDateTime(ticket.created_at)}</span>
          <span>Evidencia: ${escapeText(ticket.evidence_reference || "Sin referencia")}</span>
        </article>
      </div>
    </section>
    ${canWrite && ticket.status !== "resolved" && ticket.status !== "closed" ? `
      <form id="support-ticket-classify-form" class="cancellation-stage-card">
        <h3>Clasificar</h3>
        <div class="form-grid">
          <label>
            Asignar a
            <select id="support-ticket-assignee" required>
              <option value="customer_service">Atención a clientes</option>
              <option value="network_technician">Técnico de red</option>
              <option value="installer">Instalación</option>
            </select>
          </label>
          <label>
            Clasificado por
            <input id="support-ticket-classified-by" value="${escapeText(state.user.display_name)}" required>
          </label>
          <label class="full-row">
            Notas
            <textarea id="support-ticket-classification-notes" rows="2" maxlength="2000"></textarea>
          </label>
          <div class="dialog-actions full-row">
            <button class="primary-button" type="submit">Guardar clasificación</button>
          </div>
        </div>
      </form>
      <form id="support-ticket-resolve-form" class="cancellation-stage-card">
        <h3>Resolver</h3>
        <div class="form-grid">
          <label>
            Resuelto por
            <input id="support-ticket-resolved-by" value="${escapeText(state.user.display_name)}" required>
          </label>
          <label class="full-row">
            Resolución
            <textarea id="support-ticket-resolution-notes" rows="3" minlength="3" maxlength="4000" required></textarea>
          </label>
          <div class="dialog-actions full-row">
            <button class="primary-button" type="submit">Cerrar ticket</button>
          </div>
        </div>
      </form>
    ` : ""}
  `;
}

function openSupportTicketDetailDialog(ticket) {
  state.selectedSupportTicketId = ticket.id;
  $("#support-ticket-detail-error").textContent = "";
  renderSupportTicketWorkspace(ticket);
  $("#support-ticket-detail-dialog").showModal();
}

function closeSupportTicketDetailDialog() {
  $("#support-ticket-detail-dialog").close();
  state.selectedSupportTicketId = null;
}

async function refreshSelectedSupportTicket() {
  const ticket = selectedSupportTicket();
  if (!ticket) return null;
  const saved = await api(`/api/v1/support-tickets/${ticket.id}`);
  upsertSupportTicket(saved);
  renderSupportTicketWorkspace(saved);
  return saved;
}

async function classifySelectedSupportTicket(event) {
  event.preventDefault();
  const ticket = selectedSupportTicket();
  const errorBox = $("#support-ticket-detail-error");
  if (!ticket) return;
  const submitButton = event.target.querySelector('button[type="submit"]');
  submitButton.disabled = true;
  errorBox.textContent = "";
  try {
    await api(`/api/v1/support-tickets/${ticket.id}/classify`, {
      method: "POST",
      body: JSON.stringify({
        assigned_to: $("#support-ticket-assignee").value,
        classified_by: $("#support-ticket-classified-by").value.trim(),
        classification_notes:
          $("#support-ticket-classification-notes").value.trim() || null,
      }),
    });
    await refreshSelectedSupportTicket();
    setNotice("El ticket quedó clasificado.");
  } catch (error) {
    errorBox.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

async function resolveSelectedSupportTicket(event) {
  event.preventDefault();
  const ticket = selectedSupportTicket();
  const errorBox = $("#support-ticket-detail-error");
  if (!ticket) return;
  const submitButton = event.target.querySelector('button[type="submit"]');
  submitButton.disabled = true;
  errorBox.textContent = "";
  try {
    const saved = await api(`/api/v1/support-tickets/${ticket.id}/resolve`, {
      method: "POST",
      body: JSON.stringify({
        resolved_by: $("#support-ticket-resolved-by").value.trim(),
        resolution_notes: $("#support-ticket-resolution-notes").value.trim(),
      }),
    });
    upsertSupportTicket(saved);
    renderSupportTicketWorkspace(saved);
    setNotice("El ticket quedó resuelto y cerrado.");
  } catch (error) {
    errorBox.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

function openIncidentDetailDialog(incident) {
  state.selectedIncidentId = incident.id;
  $("#incident-detail-error").textContent = "";
  renderIncidentWorkspace(incident);
  $("#incident-detail-dialog").showModal();
}

function closeIncidentDetailDialog() {
  $("#incident-detail-dialog").close();
  state.selectedIncidentId = null;
}

async function refreshSelectedIncident() {
  const incident = selectedIncident();
  if (!incident) return null;
  const saved = await api(`/api/v1/incidents/${incident.id}`);
  upsertIncident(saved);
  renderIncidentWorkspace(saved);
  return saved;
}

async function addIncidentImpact(event) {
  event.preventDefault();
  const incident = selectedIncident();
  const errorBox = $("#incident-detail-error");
  if (!incident) return;
  const submitButton = event.target.querySelector('button[type="submit"]');
  submitButton.disabled = true;
  errorBox.textContent = "";
  try {
    await api(`/api/v1/incidents/${incident.id}/impacts`, {
      method: "POST",
      body: JSON.stringify({
        service_id: $("#incident-impact-service").value,
        affected_from: new Date($("#incident-impact-from").value).toISOString(),
        notes: $("#incident-impact-notes").value.trim() || null,
      }),
    });
    await refreshSelectedIncident();
    setNotice("El servicio quedo agregado a la incidencia.");
  } catch (error) {
    errorBox.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

async function restoreIncidentImpact(event) {
  event.preventDefault();
  const incident = selectedIncident();
  const errorBox = $("#incident-detail-error");
  if (!incident) return;
  const form = event.target;
  const submitButton = form.querySelector('button[type="submit"]');
  submitButton.disabled = true;
  errorBox.textContent = "";
  try {
    await api(
      `/api/v1/incidents/${incident.id}/impacts/${form.dataset.impactId}/restore`,
      {
        method: "POST",
        body: JSON.stringify({
          restored_at: new Date(form.elements.restored_at.value).toISOString(),
        }),
      }
    );
    await refreshSelectedIncident();
    setNotice("La restauracion del servicio quedo registrada.");
  } catch (error) {
    errorBox.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

async function resolveIncident(event) {
  event.preventDefault();
  const incident = selectedIncident();
  const errorBox = $("#incident-detail-error");
  if (!incident) return;
  const submitButton = event.target.querySelector('button[type="submit"]');
  submitButton.disabled = true;
  errorBox.textContent = "";
  try {
    const saved = await api(`/api/v1/incidents/${incident.id}/resolve`, {
      method: "POST",
      body: JSON.stringify({
        resolved_at: new Date($("#incident-resolved-at").value).toISOString(),
        cause: $("#incident-cause").value.trim(),
        responsible: $("#incident-responsible").value.trim(),
      }),
    });
    upsertIncident(saved);
    renderIncidentWorkspace(saved);
    setNotice("La incidencia quedo cerrada con sus tiempos consistentes.");
  } catch (error) {
    errorBox.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

async function compensateIncidentImpact(event) {
  event.preventDefault();
  const incident = selectedIncident();
  const errorBox = $("#incident-detail-error");
  if (!incident) return;
  const form = event.target;
  const submitButton = form.querySelector('button[type="submit"]');
  submitButton.disabled = true;
  errorBox.textContent = "";
  try {
    await api(
      `/api/v1/incidents/${incident.id}/impacts/${form.dataset.impactId}/compensation`,
      {
        method: "POST",
        body: JSON.stringify({
          amount: form.elements.amount.value,
          authorized_by: form.elements.authorized_by.value.trim(),
          reason: form.elements.reason.value.trim(),
        }),
      }
    );
    await refreshSelectedIncident();
    setNotice("La compensacion quedo aplicada como ajuste autorizado.");
  } catch (error) {
    errorBox.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

function localDateValue(date = new Date()) {
  const localTime = new Date(
    date.getTime() - date.getTimezoneOffset() * 60000
  );
  return localTime.toISOString().slice(0, 10);
}

function renderPlans() {
  const body = $("#plans-body");
  const empty = $("#plans-empty");
  if (!state.plans) {
    body.innerHTML = "";
    empty.textContent = "Tu cuenta no puede consultar el catálogo de planes.";
    empty.hidden = false;
    return;
  }
  const canWrite = hasCapability("plans.write");
  const today = localDateValue();
  body.innerHTML = state.plans
    .map((plan) => {
      const current = plan.prices?.find(
        (price) => price.valid_until === null
      );
      const canChangePrice = current?.valid_from < today;
      return `
        <tr>
          <td>
            <strong>${escapeText(plan.name)}</strong>
            <small class="table-subtitle">${escapeText(plan.description || "")}</small>
          </td>
          <td>${escapeText(plan.speed)}</td>
          <td>${plan.current_price === null ? "—" : formatMoney(plan.current_price)}</td>
          <td><span class="badge ${plan.status}">${escapeText(plan.status)}</span></td>
          ${canWrite ? `
            <td>
              ${plan.status === "active" ? `
                ${canChangePrice ? `
                  <button
                    class="row-action change-plan-price"
                    type="button"
                    data-plan-id="${plan.id}"
                  >Cambiar tarifa</button>
                ` : ""}
                <button
                  class="row-action deactivate-plan"
                  type="button"
                  data-plan-id="${plan.id}"
                >Desactivar</button>
              ` : "—"}
            </td>
          ` : ""}
        </tr>
      `;
    })
    .join("");
  empty.textContent = "Aún no hay planes registrados.";
  empty.hidden = state.plans.length > 0;
}

function replacePlan(saved) {
  const index = state.plans?.findIndex((plan) => plan.id === saved.id);
  if (index >= 0) state.plans[index] = saved;
  else state.plans?.push(saved);
  state.plans?.sort((a, b) => a.name.localeCompare(b.name));
  renderPlans();
  renderUser();
}

function openPlanDialog() {
  $("#plan-name").value = "";
  $("#plan-speed").value = "";
  $("#plan-price").value = "";
  $("#plan-valid-from").value = localDateValue();
  $("#plan-description").value = "";
  $("#plan-create-reason").value = "Alta de oferta comercial";
  $("#plan-form-error").textContent = "";
  $("#plan-dialog").showModal();
  $("#plan-name").focus();
}

function closePlanDialog() {
  $("#plan-dialog").close();
}

async function savePlan(event) {
  event.preventDefault();
  const submitButton = event.currentTarget.querySelector(
    'button[type="submit"]'
  );
  const errorBox = $("#plan-form-error");
  submitButton.disabled = true;
  errorBox.textContent = "";
  try {
    const saved = await api("/api/v1/plans", {
      method: "POST",
      body: JSON.stringify({
        name: $("#plan-name").value.trim(),
        speed: $("#plan-speed").value.trim(),
        description: $("#plan-description").value.trim() || null,
        monthly_price: $("#plan-price").value,
        valid_from: $("#plan-valid-from").value,
        created_by: state.user.display_name,
        reason: $("#plan-create-reason").value.trim(),
      }),
    });
    replacePlan(saved);
    closePlanDialog();
    setNotice("El plan y su primera tarifa quedaron registrados.");
  } catch (error) {
    errorBox.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

function selectedPlan() {
  return state.plans?.find((plan) => plan.id === state.selectedPlanId);
}

function openPlanPriceDialog(plan) {
  state.selectedPlanId = plan.id;
  $("#plan-price-dialog-title").textContent = `Nueva tarifa · ${plan.name}`;
  $("#plan-new-price").value = "";
  $("#plan-price-effective-from").value = localDateValue();
  $("#plan-price-reason").value = "";
  $("#plan-price-error").textContent = "";
  $("#plan-price-dialog").showModal();
  $("#plan-new-price").focus();
}

function closePlanPriceDialog() {
  $("#plan-price-dialog").close();
  state.selectedPlanId = null;
}

async function savePlanPrice(event) {
  event.preventDefault();
  const plan = selectedPlan();
  const submitButton = event.currentTarget.querySelector(
    'button[type="submit"]'
  );
  const errorBox = $("#plan-price-error");
  if (!plan) return;
  submitButton.disabled = true;
  errorBox.textContent = "";
  try {
    const saved = await api(`/api/v1/plans/${plan.id}/prices`, {
      method: "POST",
      body: JSON.stringify({
        monthly_price: $("#plan-new-price").value,
        effective_from: $("#plan-price-effective-from").value,
        changed_by: state.user.display_name,
        reason: $("#plan-price-reason").value.trim(),
      }),
    });
    replacePlan(saved);
    closePlanPriceDialog();
    setNotice(
      "La tarifa publicada cambió; los servicios existentes no fueron modificados."
    );
  } catch (error) {
    errorBox.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

function openPlanDeactivateDialog(plan) {
  state.selectedPlanId = plan.id;
  $("#plan-deactivate-dialog-title").textContent =
    `Desactivar · ${plan.name}`;
  $("#plan-deactivate-reason").value = "";
  $("#plan-deactivate-error").textContent = "";
  $("#plan-deactivate-dialog").showModal();
  $("#plan-deactivate-reason").focus();
}

function closePlanDeactivateDialog() {
  $("#plan-deactivate-dialog").close();
  state.selectedPlanId = null;
}

async function deactivateSelectedPlan(event) {
  event.preventDefault();
  const plan = selectedPlan();
  const submitButton = event.currentTarget.querySelector(
    'button[type="submit"]'
  );
  const errorBox = $("#plan-deactivate-error");
  if (!plan) return;
  submitButton.disabled = true;
  errorBox.textContent = "";
  try {
    const saved = await api(`/api/v1/plans/${plan.id}/deactivate`, {
      method: "POST",
      body: JSON.stringify({
        deactivated_by: state.user.display_name,
        reason: $("#plan-deactivate-reason").value.trim(),
      }),
    });
    replacePlan(saved);
    closePlanDeactivateDialog();
    setNotice(
      "El plan fue retirado de nuevas altas; los servicios existentes se conservaron."
    );
  } catch (error) {
    errorBox.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

function showView(name) {
  document.querySelectorAll(".view-panel").forEach((panel) => {
    panel.hidden = panel.id !== `${name}-panel`;
  });
  document.querySelectorAll(".nav-item").forEach((item) => {
    item.classList.toggle("active", item.dataset.view === name);
  });
  const titles = {
    overview: "Resumen",
    customers: "Clientes",
    services: "Servicios",
    payments: "Pagos",
    operations: "Operación diaria",
    assets: "Inventario",
    plans: "Planes",
    incidents: "Incidencias",
    support: "Soporte",
    network: "Red UISP",
    users: "Usuarios",
  };
  $("#page-title").textContent = titles[name];
  $(".sidebar").classList.remove("open");
  $("#menu-button").setAttribute("aria-expanded", "false");
}

async function enterApp() {
  loginView.hidden = true;
  appView.hidden = false;
  setNotice();
  try {
    await loadWorkspace();
    await openSharedReceiptIfPresent();
  } catch (error) {
    if (error.status === 401) {
      logout(false);
      return;
    }
    setNotice(error.message);
  }
}

$("#sync-uisp-button").addEventListener("click", async () => {
  const button = $("#sync-uisp-button");
  button.disabled = true;
  try {
    await api("/api/v1/uisp/sync", { method: "POST" });
    state.networkDevices = await loadOptionalList("/api/v1/network/devices");
    state.networkSummary = await loadResource("/api/v1/network/daily-summary").catch(() => null);
    renderNetworkDevices();
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
