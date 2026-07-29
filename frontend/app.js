const state = {
  token: sessionStorage.getItem("aether_token"),
  user: null,
  customers: [],
  services: [],
  payments: [],
  plans: [],
  editingCustomerId: null,
  selectedPaymentId: null,
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
  const [customers, services, payments, plans] = await Promise.all([
    loadResource("/api/v1/customers"),
    loadResource("/api/v1/services"),
    loadResource("/api/v1/payments"),
    loadResource("/api/v1/plans?plan_status=active"),
  ]);
  state.customers = customers;
  state.services = services;
  state.payments = payments;
  state.plans = plans;
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
  const canWriteCustomers = hasCapability("customers.write");
  $("#new-customer-button").hidden = !canWriteCustomers;
  document.querySelectorAll(".customer-action-column").forEach((column) => {
    column.hidden = !canWriteCustomers;
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
  const canWrite = hasCapability("customers.write");
  body.innerHTML = rows
    .map((customer) => `
      <tr>
        <td><strong>${escapeText(customer.full_name)}</strong></td>
        <td>${escapeText(customer.phones?.[0] || "—")}</td>
        <td>${escapeText(customer.email || "—")}</td>
        <td>${formatDate(customer.registered_at)}</td>
        ${canWrite ? `
          <td>
            <button
              class="row-action edit-customer"
              type="button"
              data-customer-id="${customer.id}"
            >Editar</button>
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

function updateSelectedPlanPrice() {
  const plan = state.plans?.find(
    (item) => item.id === $("#service-plan").value
  );
  $("#service-plan-price").textContent = plan
    ? formatMoney(plan.current_price)
    : "—";
}

function openServiceDialog() {
  const customers = state.customers || [];
  const plans = (state.plans || []).filter(
    (plan) => plan.status === "active" && plan.current_price !== null
  );
  $("#service-customer").innerHTML = customers
    .map(
      (customer) =>
        `<option value="${customer.id}">${escapeText(customer.full_name)}</option>`
    )
    .join("");
  $("#service-plan").innerHTML = plans
    .map(
      (plan) =>
        `<option value="${plan.id}">${escapeText(plan.name)} · ${escapeText(plan.speed)}</option>`
    )
    .join("");
  $("#service-amr").value = "";
  $("#service-address").value = "";
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
        customer_id: $("#service-customer").value,
        plan_id: plan.id,
        amr_code: $("#service-amr").value.trim().toUpperCase(),
        address: $("#service-address").value.trim(),
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
  body.innerHTML = state.payments
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
  empty.textContent = "Aún no hay pagos registrados.";
  empty.hidden = state.payments.length > 0;
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

function localDateTimeValue(date = new Date()) {
  const localTime = new Date(
    date.getTime() - date.getTimezoneOffset() * 60000
  );
  return localTime.toISOString().slice(0, 16);
}

function openPaymentDialog() {
  $("#payment-customer").innerHTML = (state.customers || [])
    .map(
      (customer) =>
        `<option value="${customer.id}">${escapeText(customer.full_name)}</option>`
    )
    .join("");
  $("#payment-amount").value = "";
  $("#payment-method").value = "cash";
  $("#payment-declared-at").value = localDateTimeValue();
  $("#payment-reference").value = "";
  $("#payment-origin-holder").value = "";
  $("#payment-proof-reference").value = "";
  $("#payment-notes").value = "";
  $("#payment-form-error").textContent = "";
  updatePaymentServices();
  $("#payment-dialog").showModal();
  $("#payment-amount").focus();
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
    const optionalText = (selector) => $(selector).value.trim() || null;
    const saved = await api("/api/v1/payments", {
      method: "POST",
      body: JSON.stringify({
        customer_id: $("#payment-customer").value,
        service_id: $("#payment-service").value || null,
        declared_amount: $("#payment-amount").value,
        declared_at: declaredAt.toISOString(),
        method: $("#payment-method").value,
        reference: optionalText("#payment-reference"),
        proof_reference: optionalText("#payment-proof-reference"),
        origin_account_holder: optionalText("#payment-origin-holder"),
        received_by: state.user.display_name,
        notes: optionalText("#payment-notes"),
      }),
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
}

function closePaymentReviewDialog() {
  $("#payment-review-dialog").close();
  state.selectedPaymentId = null;
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
$("#new-customer-button").addEventListener("click", () => {
  openCustomerDialog();
});
$("#customers-body").addEventListener("click", (event) => {
  const button = event.target.closest(".edit-customer");
  if (!button) return;
  const customer = state.customers?.find(
    (item) => item.id === button.dataset.customerId
  );
  if (customer) openCustomerDialog(customer);
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
$("#service-plan").addEventListener("change", updateSelectedPlanPrice);
$("#service-form").addEventListener("submit", saveService);
$("#close-service-dialog").addEventListener("click", closeServiceDialog);
$("#cancel-service-dialog").addEventListener("click", closeServiceDialog);
$("#new-payment-button").addEventListener("click", openPaymentDialog);
$("#payment-customer").addEventListener("change", updatePaymentServices);
$("#payment-form").addEventListener("submit", savePayment);
$("#close-payment-dialog").addEventListener("click", closePaymentDialog);
$("#cancel-payment-dialog").addEventListener("click", closePaymentDialog);
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
$("#logout-button").addEventListener("click", () => logout());
$("#menu-button").addEventListener("click", () => {
  const sidebar = $(".sidebar");
  const open = sidebar.classList.toggle("open");
  $("#menu-button").setAttribute("aria-expanded", String(open));
});

if (state.token) enterApp();
