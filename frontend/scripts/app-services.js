/* Clientes y servicios: alta, instalaciones, suspensión, reactivación y bajas. */
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
  const canAssignServices = hasCapability("services.write");
  const canShowActions = canWrite || canReadBilling || canAssignServices;
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
            ${canAssignServices ? `
              <button
                class="row-action assign-service-to-customer"
                type="button"
                data-customer-id="${customer.id}"
              >Asignar servicio</button>
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
  const search = $("#service-search")?.value.trim().toLowerCase() || "";
  const statusFilter = $("#service-status-filter")?.value || "";
  const planFilter = $("#service-plan-filter")?.value || "";
  const paymentDayFilter = $("#service-payment-day-filter")?.value || "";
  const planFilterElement = $("#service-plan-filter");
  const paymentDayFilterElement = $("#service-payment-day-filter");
  if (planFilterElement) {
    const planNames = [...new Set(state.services.map((service) => service.plan_name))].sort();
    planFilterElement.innerHTML = `<option value="">Todos</option>${planNames.map((name) => `<option value="${escapeText(name)}">${escapeText(name)}</option>`).join("")}`;
    planFilterElement.value = planFilter;
  }
  if (paymentDayFilterElement) {
    const days = [...new Set(state.services.map((service) => service.payment_day))].sort((a, b) => a - b);
    paymentDayFilterElement.innerHTML = `<option value="">Todos</option>${days.map((day) => `<option value="${day}">Día ${day}</option>`).join("")}`;
    paymentDayFilterElement.value = paymentDayFilter;
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
  const canAssignHolder = hasCapability("services.write");
  const canShowActions = (
    canScheduleInstallation ||
    canControlNetwork ||
    canWriteNotifications ||
    canCheckSuspension ||
    canCheckReactivation ||
    canReadExtensions ||
    canCancelServices ||
    canManageRecovery ||
    canAssignHolder
  );
  const rows = state.services.filter((service) => {
    const matchesSearch = !search || [
      service.amr_code, service.plan_name, service.address, String(service.payment_day),
    ].join(" ").toLowerCase().includes(search);
    return matchesSearch
      && (!statusFilter || service.status === statusFilter)
      && (!planFilter || service.plan_name === planFilter)
      && (!paymentDayFilter || String(service.payment_day) === paymentDayFilter);
  });
  const serviceCounts = rows.reduce((counts, service) => {
    counts[service.status] = (counts[service.status] || 0) + 1;
    return counts;
  }, {});
  $("#service-summary").innerHTML = [
    ["Mostrando", `${rows.length} de ${state.services.length}`],
    ["Activos", serviceCounts.active || 0],
    ["Pendientes", serviceCounts.pending || 0],
    ["Suspendidos", serviceCounts.suspended || 0],
    ["Cancelados", serviceCounts.cancelled || 0],
  ].map(([label, value]) => `<span class="summary-chip"><strong>${escapeText(String(value))}</strong><span>${escapeText(label)}</span></span>`).join("");
  body.innerHTML = rows
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
            <details class="service-actions-menu">
              <summary>Acciones</summary>
              <div class="service-actions-list" aria-label="Acciones para ${escapeText(service.amr_code)}">
            ${canAssignHolder && service.status !== "cancelled" ? `
              <button
                class="row-action assign-service-holder"
                type="button"
                data-service-id="${service.id}"
              >${service.current_customer_id ? "Editar titular" : "Asignar titular"}</button>
            ` : ""}
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
              </div>
            </details>
          </td>
        ` : ""}
      </tr>
    `)
    .join("");
  empty.textContent = "Aún no hay servicios registrados.";
  if (search || statusFilter || planFilter || paymentDayFilter) {
    empty.textContent = "No hay servicios que coincidan con los filtros actuales.";
  }
  empty.hidden = rows.length > 0;
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

function serviceLabel(service) {
  return `${service.amr_code} · ${service.address}`;
}

function renderHolderAssignmentOptions(preselectedServiceId, preselectedCustomerId) {
  const serviceSelect = $("#holder-assignment-service");
  const customerSelect = $("#holder-assignment-customer");
  const services = (state.services || []).filter((service) =>
    service.status !== "cancelled" &&
    (!preselectedCustomerId || service.current_customer_id !== preselectedCustomerId)
  );
  serviceSelect.innerHTML = services.map((service) =>
    `<option value="${service.id}">${escapeText(serviceLabel(service))}</option>`
  ).join("");
  customerSelect.innerHTML = (state.customers || []).map((customer) =>
    `<option value="${customer.id}">${escapeText(customer.full_name)}</option>`
  ).join("");
  serviceSelect.value = preselectedServiceId || services[0]?.id || "";
  customerSelect.value = preselectedCustomerId || state.customers?.[0]?.id || "";
  updateHolderAssignmentContext();
}

function updateHolderAssignmentContext() {
  const service = state.services?.find(
    (item) => item.id === $("#holder-assignment-service").value
  );
  const currentCustomer = state.customers?.find(
    (item) => item.id === service?.current_customer_id
  );
  const customerSelect = $("#holder-assignment-customer");
  [...customerSelect.options].forEach((option) => {
    option.disabled = option.value === service?.current_customer_id;
  });
  if (customerSelect.value === service?.current_customer_id) {
    customerSelect.value = [...customerSelect.options].find(
      (option) => !option.disabled
    )?.value || "";
  }
  $("#holder-assignment-current").textContent = currentCustomer
    ? `Titular actual: ${currentCustomer.full_name}. Se conservará el historial y los cargos anteriores.`
    : "El servicio no tiene titular. Se enlazará sin crear otro servicio.";
}

function openHolderAssignmentDialog({ serviceId = null, customerId = null } = {}) {
  const availableServices = state.services?.some((service) =>
    service.status !== "cancelled" &&
    (!customerId || service.current_customer_id !== customerId)
  );
  if (!availableServices) {
    setNotice("No hay servicios disponibles para asignar.");
    return;
  }
  if (!state.customers?.length) {
    setNotice("No hay clientes disponibles para asignar.");
    return;
  }
  renderHolderAssignmentOptions(serviceId, customerId);
  $("#holder-assignment-reason").value = "Actualización de titular solicitada por atención a clientes";
  $("#holder-assignment-error").textContent = "";
  $("#holder-assignment-dialog").showModal();
}

function closeHolderAssignmentDialog() {
  $("#holder-assignment-dialog").close();
}

async function saveHolderAssignment(event) {
  event.preventDefault();
  const button = event.currentTarget.querySelector('button[type="submit"]');
  const errorBox = $("#holder-assignment-error");
  const service = state.services?.find(
    (item) => item.id === $("#holder-assignment-service").value
  );
  if (!service) return;
  button.disabled = true;
  errorBox.textContent = "";
  try {
    const reason = $("#holder-assignment-reason").value.trim();
    const customerId = $("#holder-assignment-customer").value;
    const endpoint = service.current_customer_id
      ? `/api/v1/services/${service.id}/holder-transfers`
      : `/api/v1/services/${service.id}/holders`;
    const body = service.current_customer_id
      ? {
          new_customer_id: customerId,
          effective_date: new Date().toISOString().slice(0, 10),
          transferred_by: state.user.display_name,
          reason,
        }
      : { customer_id: customerId, assigned_by: state.user.display_name, reason };
    await api(endpoint, { method: "POST", body: JSON.stringify(body) });
    state.services = await loadResource("/api/v1/services");
    renderServices();
    renderOverview();
    closeHolderAssignmentDialog();
    setNotice(service.current_customer_id
      ? "El titular del servicio se actualizó sin duplicar el servicio."
      : "El servicio quedó asignado al cliente sin crear un duplicado.");
  } catch (error) {
    errorBox.textContent = error.message;
  } finally {
    button.disabled = false;
  }
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
