const state = {
  token: sessionStorage.getItem("aether_token"),
  user: null,
  customers: [],
  services: [],
  payments: [],
};

const $ = (selector) => document.querySelector(selector);
const loginView = $("#login-view");
const appView = $("#app-view");
const notice = $("#notice");

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  if (options.body) headers["Content-Type"] = "application/json";
  const response = await fetch(path, { ...options, headers });
  if (response.status === 204) return null;
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(
      typeof payload.detail === "string"
        ? payload.detail
        : "No fue posible completar la solicitud."
    );
    error.status = response.status;
    throw error;
  }
  return payload;
}

function formatDate(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("es-MX", { dateStyle: "medium" }).format(
    new Date(value)
  );
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

async function loadWorkspace() {
  state.user = await api("/api/v1/auth/me");
  const [customers, services, payments] = await Promise.all([
    loadResource("/api/v1/customers"),
    loadResource("/api/v1/services"),
    loadResource("/api/v1/payments"),
  ]);
  state.customers = customers;
  state.services = services;
  state.payments = payments;
  renderUser();
  renderOverview();
  renderCustomers();
  renderServices();
  renderPayments();
}

function renderUser() {
  $("#user-name").textContent = state.user.display_name;
  $("#user-role").textContent = state.user.role.replaceAll("_", " ");
  $("#user-avatar").textContent = state.user.display_name.charAt(0).toUpperCase();
  const permissions = state.user.role === "administrator"
    ? ["Acceso administrativo total"]
    : state.user.permissions;
  $("#permission-list").innerHTML = permissions.length
    ? permissions
        .map((item) => `<span class="permission">${escapeText(item)}</span>`)
        .join("")
    : '<p class="empty-state">Esta cuenta aún no tiene capacidades asignadas.</p>';
}

function renderOverview() {
  const customers = state.customers;
  const services = state.services;
  const payments = state.payments;
  const active = services?.filter((item) => item.status === "active").length;
  const suspended = services?.filter((item) => item.status === "suspended").length;
  const pendingPayments = payments?.filter((item) => item.status === "pending").length;
  const metrics = [
    ["Clientes", customers?.length],
    ["Servicios activos", active],
    ["Servicios suspendidos", suspended],
    ["Pagos por verificar", pendingPayments],
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
  const visibleAreas = [customers, services, payments].filter(Boolean).length;
  $("#overview-message").textContent = visibleAreas
    ? `Aether muestra ${visibleAreas} áreas según los permisos de tu cuenta.`
    : "Tu cuenta está activa, pero todavía no tiene acceso a áreas operativas.";
}

function renderCustomers(query = "") {
  const body = $("#customers-body");
  const empty = $("#customers-empty");
  if (!state.customers) {
    body.innerHTML = "";
    empty.textContent = "Tu cuenta no puede consultar clientes.";
    empty.hidden = false;
    return;
  }
  const normalized = query.trim().toLowerCase();
  const rows = state.customers.filter((customer) =>
    [customer.full_name, ...(customer.phones || [])]
      .join(" ")
      .toLowerCase()
      .includes(normalized)
  );
  body.innerHTML = rows
    .map((customer) => `
      <tr>
        <td><strong>${escapeText(customer.full_name)}</strong></td>
        <td>${escapeText(customer.phones?.[0] || "—")}</td>
        <td>${escapeText(customer.email || "—")}</td>
        <td>${formatDate(customer.registered_at)}</td>
      </tr>
    `)
    .join("");
  empty.textContent = normalized
    ? "No hay clientes que coincidan con la búsqueda."
    : "Aún no hay clientes registrados.";
  empty.hidden = rows.length > 0;
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
  body.innerHTML = state.services
    .map((service) => `
      <tr>
        <td><strong>${escapeText(service.amr_code)}</strong></td>
        <td>${escapeText(service.plan_name)}</td>
        <td>${escapeText(service.address)}</td>
        <td>Día ${service.payment_day} · ${formatMoney(service.monthly_price)}</td>
        <td><span class="badge ${service.status}">${escapeText(service.status)}</span></td>
      </tr>
    `)
    .join("");
  empty.textContent = "Aún no hay servicios registrados.";
  empty.hidden = state.services.length > 0;
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
  body.innerHTML = state.payments
    .slice()
    .sort((a, b) => new Date(b.received_at) - new Date(a.received_at))
    .slice(0, 100)
    .map((payment) => `
      <tr>
        <td><strong>${escapeText(payment.reference || payment.id.slice(0, 8))}</strong></td>
        <td>${formatMoney(payment.declared_amount)}</td>
        <td>${escapeText(payment.method)}</td>
        <td>${formatDate(payment.received_at)}</td>
        <td><span class="badge ${payment.status}">${escapeText(payment.status)}</span></td>
      </tr>
    `)
    .join("");
  empty.textContent = "Aún no hay pagos registrados.";
  empty.hidden = state.payments.length > 0;
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
  } catch (error) {
    if (error.status === 401) {
      logout(false);
      return;
    }
    setNotice(error.message);
  }
}

async function logout(callApi = true) {
  if (callApi && state.token) {
    await api("/api/v1/auth/logout", { method: "POST" }).catch(() => {});
  }
  state.token = null;
  state.user = null;
  sessionStorage.removeItem("aether_token");
  appView.hidden = true;
  loginView.hidden = false;
  $("#password").value = "";
}

$("#login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = event.currentTarget.querySelector("button");
  const errorBox = $("#login-error");
  button.disabled = true;
  errorBox.textContent = "";
  try {
    const response = await api("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({
        username: $("#username").value,
        password: $("#password").value,
      }),
    });
    state.token = response.access_token;
    sessionStorage.setItem("aether_token", state.token);
    await enterApp();
  } catch (error) {
    errorBox.textContent =
      error.status === 401
        ? "El usuario o la contraseña no son correctos."
        : error.message;
  } finally {
    button.disabled = false;
  }
});

document.querySelectorAll(".nav-item").forEach((item) => {
  item.addEventListener("click", () => showView(item.dataset.view));
});
$("#customer-search").addEventListener("input", (event) => {
  renderCustomers(event.target.value);
});
$("#logout-button").addEventListener("click", () => logout());
$("#menu-button").addEventListener("click", () => {
  const sidebar = $(".sidebar");
  const open = sidebar.classList.toggle("open");
  $("#menu-button").setAttribute("aria-expanded", String(open));
});

if (state.token) enterApp();
