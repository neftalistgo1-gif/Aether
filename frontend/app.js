const state = {
  token: sessionStorage.getItem("aether_token"),
  user: null,
  customers: [],
  services: [],
  payments: [],
  plans: [],
  editingCustomerId: null,
  selectedPaymentId: null,
  selectedPlanId: null,
  selectedServiceId: null,
  selectedInstallation: null,
  selectedNetworkAction: null,
  selectedSuspensionDebt: null,
  selectedReactivationDebt: null,
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
  const parsed = /^\d{4}-\d{2}-\d{2}$/.test(value)
    ? new Date(`${value}T00:00:00`)
    : new Date(value);
  return new Intl.DateTimeFormat("es-MX", { dateStyle: "medium" }).format(
    parsed
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
    loadResource("/api/v1/plans"),
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
  renderPlans();
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
  const canReadPlans = hasCapability("plans.read");
  const canWritePlans = hasCapability("plans.write");
  document.querySelector('[data-view="plans"]').hidden = !canReadPlans;
  $("#new-plan-button").hidden = !canWritePlans;
  document.querySelectorAll(".plan-action-column").forEach((column) => {
    column.hidden = !canWritePlans;
  });
  document.querySelectorAll(".service-action-column").forEach(
    (column) => {
      column.hidden = !(
        hasCapability("installations.write") ||
        hasCapability("network.control") ||
        hasCapability("notifications.write")
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
  const canReadBilling = hasCapability("billing.read");
  const canShowActions = canWrite || canReadBilling;
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
  const canShowActions = (
    canScheduleInstallation ||
    canControlNetwork ||
    canWriteNotifications ||
    canCheckSuspension ||
    canCheckReactivation
  );
  body.innerHTML = state.services
    .map((service) => `
      <tr>
        <td><strong>${escapeText(service.amr_code)}</strong></td>
        <td>${escapeText(service.plan_name)}</td>
        <td>${escapeText(service.address)}</td>
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
    const result = await api(
      `/api/v1/services/${serviceId}/suspensions/coordinated`,
      {
        method: "POST",
        body: JSON.stringify({
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
        }),
      }
    );
    closeSuspensionCheckDialog();
    setNotice(
      result.command.status === "simulated"
        ? "La suspensión comercial pasó todas las validaciones en modo seguro."
        : `La validación terminó con estado ${result.command.status}.`
    );
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
  $("#reactivation-check-error").textContent = "";
  $("#reactivation-check-dialog").showModal();
  try {
    const balance = await api(
      `/api/v1/services/${service.id}/balance`
    );
    state.selectedReactivationDebt = balance.outstanding_balance;
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
    $("#reactivation-authorized-by").focus();
  } catch (error) {
    $("#reactivation-check-error").textContent = error.message;
  }
}

function closeReactivationCheckDialog() {
  $("#reactivation-check-dialog").close();
  state.selectedServiceId = null;
  state.selectedReactivationDebt = null;
}

async function runReactivationCheck(event) {
  event.preventDefault();
  const serviceId = state.selectedServiceId;
  const submitButton = event.currentTarget.querySelector(
    'button[type="submit"]'
  );
  const errorBox = $("#reactivation-check-error");
  if (!serviceId || state.selectedReactivationDebt === null) return;
  submitButton.disabled = true;
  errorBox.textContent = "";
  try {
    const result = await api(
      `/api/v1/services/${serviceId}/reactivations/coordinated`,
      {
        method: "POST",
        body: JSON.stringify({
          reason: $("#reactivation-check-reason").value.trim(),
          authorized_by: $("#reactivation-authorized-by").value.trim(),
          performed_by: state.user.display_name,
          debt_amount: state.selectedReactivationDebt,
          idempotency_key:
            `ui-reactivation-${crypto.randomUUID()}`,
          dry_run: true,
        }),
      }
    );
    closeReactivationCheckDialog();
    setNotice(
      result.command.status === "simulated"
        ? "La reactivación comercial pasó todas las validaciones en modo seguro."
        : `La validación terminó con estado ${result.command.status}.`
    );
  } catch (error) {
    errorBox.textContent = error.message;
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
    plans: "Planes",
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
$("#service-plan").addEventListener("change", updateSelectedPlanPrice);
$("#service-form").addEventListener("submit", saveService);
$("#close-service-dialog").addEventListener("click", closeServiceDialog);
$("#cancel-service-dialog").addEventListener("click", closeServiceDialog);
$("#services-body").addEventListener("click", (event) => {
  const button = event.target.closest(".assess-installation");
  const networkButton = event.target.closest(".simulate-network-control");
  const notificationButton = event.target.closest(".record-notification");
  const suspensionButton = event.target.closest(
    ".check-commercial-suspension"
  );
  const reactivationButton = event.target.closest(
    ".check-commercial-reactivation"
  );
  if (
    !button &&
    !networkButton &&
    !notificationButton &&
    !suspensionButton &&
    !reactivationButton
  ) return;
  const service = state.services?.find(
    (item) =>
      item.id ===
      (
        button ||
        networkButton ||
        notificationButton ||
        suspensionButton ||
        reactivationButton
      ).dataset.serviceId
  );
  if (!service) return;
  if (networkButton) openNetworkSimulationDialog(service);
  else if (notificationButton) openNotificationDialog(service);
  else if (suspensionButton) openSuspensionCheckDialog(service);
  else if (reactivationButton) openReactivationCheckDialog(service);
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
$("#close-reactivation-check-dialog").addEventListener(
  "click",
  closeReactivationCheckDialog
);
$("#cancel-reactivation-check").addEventListener(
  "click",
  closeReactivationCheckDialog
);
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

if (state.token) enterApp();
