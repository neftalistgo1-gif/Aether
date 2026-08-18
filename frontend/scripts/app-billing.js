/* Cobranza: pagos, comprobantes, aplicación de saldos y estados de cuenta. */
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
