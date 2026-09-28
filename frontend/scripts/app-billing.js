/* Cobranza: pagos, comprobantes, aplicación de saldos y estados de cuenta. */
function paymentStage(payment) {
  if (payment.applied_at) return "applied";
  if (payment.status === "pending") return "pending_review";
  if (payment.status === "verified") return "awaiting_application";
  return "not_processed";
}

function paymentStageLabel(payment) {
  const stage = paymentStage(payment);
  if (stage === "applied") return "Aplicado";
  if (stage === "pending_review") return "Por revisar";
  if (stage === "awaiting_application") return "Por aplicar";
  return payment.status === "cancelled" ? "Cancelado" : "Rechazado";
}

function renderPayments() {
  const body = $("#payments-body");
  const empty = $("#payments-empty");
  const pagination = $("#payment-pagination");
  if (!state.payments) {
    body.innerHTML = "";
    empty.textContent = "Tu cuenta no puede consultar pagos.";
    empty.hidden = false;
    pagination.hidden = true;
    return;
  }
  const canApprove = hasCapability("billing.approve");
  const monthStart = new Date(state.paymentMonth.getFullYear(), state.paymentMonth.getMonth(), 1);
  const monthEnd = new Date(state.paymentMonth.getFullYear(), state.paymentMonth.getMonth() + 1, 1);
  const monthName = new Intl.DateTimeFormat("es-MX", { month: "long", year: "numeric" }).format(monthStart);
  const dayName = new Intl.DateTimeFormat("es-MX", { weekday: "short" });
  const monthlyPayments = state.payments.filter((payment) => {
    const received = new Date(payment.received_at);
    return received >= monthStart && received < monthEnd;
  });
  const search = (state.paymentSearch || "").trim().toLowerCase();
  const filteredPayments = monthlyPayments.filter((payment) => {
    const customer = paymentCustomerName(payment);
    const service = (state.services || []).find((item) => item.id === payment.service_id);
    const searchable = [customer, service?.amr_code, payment.reference, payment.origin_account_holder].filter(Boolean).join(" ").toLowerCase();
    return (state.paymentFilter === "all" || paymentStage(payment) === state.paymentFilter) && (!search || searchable.includes(search));
  });
  const total = (items) => items.reduce((sum, payment) => sum + Number(payment.confirmed_amount || payment.declared_amount || 0), 0);
  const applied = monthlyPayments.filter((payment) => Boolean(payment.applied_at));
  const pending = monthlyPayments.filter((payment) => payment.status === "pending");
  const verifiedWaiting = monthlyPayments.filter((payment) => payment.status === "verified" && !payment.applied_at);
  const rejected = monthlyPayments.filter((payment) => ["rejected", "cancelled"].includes(payment.status));
  const stagePriority = {
    awaiting_application: 0,
    pending_review: 1,
    applied: 2,
    not_processed: 3,
  };
  const orderedPayments = filteredPayments.slice().sort((a, b) => {
    const priority = stagePriority[paymentStage(a)] - stagePriority[paymentStage(b)];
    return priority || new Date(b.received_at) - new Date(a.received_at);
  });
  const pageSize = state.paymentPageSize || 15;
  const pageCount = Math.max(1, Math.ceil(orderedPayments.length / pageSize));
  state.paymentPage = Math.min(Math.max(state.paymentPage || 1, 1), pageCount);
  const pageStart = (state.paymentPage - 1) * pageSize;
  const visiblePayments = orderedPayments.slice(pageStart, pageStart + pageSize);
  $("#payment-month-label").textContent = monthName.charAt(0).toUpperCase() + monthName.slice(1);
  $("#payments-ledger-title").textContent = `Cobros de ${monthName}`;
  $("#payments-ledger-count").textContent = `${filteredPayments.length} de ${monthlyPayments.length} movimiento${monthlyPayments.length === 1 ? "" : "s"}`;
  $("#payment-status-filter").value = state.paymentFilter;
  $("#payment-queue-summary").innerHTML = `
    <button class="metric payment-metric collected payment-stage-filter ${state.paymentFilter === "applied" ? "active" : ""}" type="button" data-payment-stage="applied"><span>Aplicado</span><strong>${formatMoney(total(applied))}</strong><small>${applied.length} pago${applied.length === 1 ? "" : "s"}</small></button>
    <button class="metric payment-metric pending payment-stage-filter ${state.paymentFilter === "pending_review" ? "active" : ""}" type="button" data-payment-stage="pending_review"><span>Por revisar</span><strong>${formatMoney(total(pending))}</strong><small>${pending.length} pendiente${pending.length === 1 ? "" : "s"}</small></button>
    <button class="metric payment-metric verified payment-stage-filter ${state.paymentFilter === "awaiting_application" ? "active" : ""}" type="button" data-payment-stage="awaiting_application"><span>Por aplicar</span><strong>${formatMoney(total(verifiedWaiting))}</strong><small>${verifiedWaiting.length} listo${verifiedWaiting.length === 1 ? "" : "s"} para aplicar</small></button>
    <button class="metric payment-metric rejected payment-stage-filter ${state.paymentFilter === "not_processed" ? "active" : ""}" type="button" data-payment-stage="not_processed"><span>No procesado</span><strong>${formatMoney(total(rejected))}</strong><small>${rejected.length} registro${rejected.length === 1 ? "" : "s"}</small></button>
  `;
  renderPaymentMonthCalendar(monthStart, monthlyPayments, dayName);
  renderUpcomingPaymentDays(monthEnd);
  body.innerHTML = visiblePayments
    .map((payment) => `
      <tr class="payment-row payment-stage-${paymentStage(payment)}">
        <td><strong>${escapeText(paymentCustomerName(payment))}</strong><span class="table-subtitle">${escapeText(payment.reference || payment.id.slice(0, 8))}</span></td>
        <td>${escapeText((state.services || []).find((service) => service.id === payment.service_id)?.amr_code || "—")}</td>
        <td>${formatDate(payment.received_at)}</td>
        <td>${formatMoney(payment.confirmed_amount || payment.declared_amount)}</td>
        <td>
          <span class="badge ${paymentStage(payment)}">
            ${escapeText(paymentStageLabel(payment))}
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
    monthlyPayments.length === 0 ? "No hay pagos registrados en este mes." : "No hay movimientos que coincidan con los filtros.";
  empty.hidden = filteredPayments.length > 0;
  pagination.hidden = filteredPayments.length === 0;
  $("#payment-page-summary").textContent = orderedPayments.length
    ? `Mostrando ${pageStart + 1}–${Math.min(pageStart + pageSize, orderedPayments.length)} de ${orderedPayments.length}`
    : "";
  $("#previous-payment-page").disabled = state.paymentPage <= 1;
  $("#next-payment-page").disabled = state.paymentPage >= pageCount;
}

function renderPaymentMonthCalendar(monthStart, payments, dayName) {
  const daysInMonth = new Date(monthStart.getFullYear(), monthStart.getMonth() + 1, 0).getDate();
  const byDay = payments.reduce((accumulator, payment) => {
    const day = new Date(payment.received_at).getDate();
    accumulator[day] = accumulator[day] || [];
    accumulator[day].push(payment);
    return accumulator;
  }, {});
  $("#payment-month-calendar").innerHTML = Array.from({ length: daysInMonth }, (_, index) => {
    const date = new Date(monthStart.getFullYear(), monthStart.getMonth(), index + 1);
    const entries = byDay[index + 1] || [];
    const indicator = entries.some((payment) => payment.status === "verified" && !payment.applied_at) ? "verified" : entries.some((payment) => payment.status === "pending") ? "pending" : entries.some((payment) => payment.applied_at) ? "applied" : entries.length ? "rejected" : "empty";
    return `<div class="payment-calendar-day ${indicator}" title="${entries.length} pago(s) registrado(s)"><span>${dayName.format(date).replace(".", "")}</span><strong>${index + 1}</strong><i></i></div>`;
  }).join("");
}

function renderUpcomingPaymentDays(monthEnd) {
  const upcoming = (state.services || []).filter((service) => service.status === "active").map((service) => {
    const due = new Date(monthEnd.getFullYear(), monthEnd.getMonth(), Math.min(service.payment_day || 1, 28));
    return { service, due, customer: (state.customers || []).find((customer) => customer.id === service.current_customer_id) };
  }).sort((a, b) => a.due - b.due).slice(0, 6);
  $("#payment-upcoming-list").innerHTML = upcoming.length ? upcoming.map(({ service, due, customer }) => `<div class="upcoming-payment"><time><b>${String(due.getDate()).padStart(2, "0")}</b><span>${new Intl.DateTimeFormat("es-MX", { month: "short" }).format(due).replace(".", "")}</span></time><div><strong>${escapeText(customer?.full_name || "Cliente pendiente")}</strong><span>${escapeText(service.amr_code)} · Día ${service.payment_day}</span></div><b>${formatMoney(service.monthly_price)}</b></div>`).join("") : '<p class="empty-state">No hay servicios activos visibles.</p>';
}

async function downloadPaymentAccountingReport() {
  const button = $("#download-payment-accounting-report");
  const year = state.paymentMonth.getFullYear();
  const month = state.paymentMonth.getMonth() + 1;
  const originalLabel = button.textContent;
  button.disabled = true;
  button.textContent = "Preparando archivo…";
  try {
    const report = await apiBlob(
      `/api/v1/payments/accounting-report?year=${year}&month=${month}`
    );
    const url = URL.createObjectURL(report);
    const link = document.createElement("a");
    link.href = url;
    link.download = `aether_pagos_${year}-${String(month).padStart(2, "0")}.xlsx`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    setNotice("El archivo contable del mes seleccionado se descargó correctamente.");
  } catch (error) {
    setNotice(error.message);
  } finally {
    button.disabled = false;
    button.textContent = originalLabel;
  }
}

function customerDisplayLabel(customer) {
  const primaryPhone = customer.phones?.[0] || "";
  return [customer.full_name, customer.amr_code, primaryPhone]
    .filter(Boolean)
    .join(" · ");
}

function paymentLookupText(service, customer) {
  const device = (state.networkDevices || []).find((item) => item.service_id === service.id);
  return [service.amr_code, service.plan_name, service.address, device?.management_ip, device?.display_name, customer?.full_name, ...(customer?.phones || [])]
    .filter(Boolean).join(" ").toLowerCase();
}

function setPaymentSelection(customer, service = null) {
  $("#payment-customer").innerHTML = customer ? `<option value="${customer.id}"></option>` : "";
  $("#payment-customer").value = customer?.id || "";
  $("#payment-service").innerHTML = service ? `<option value="${service.id}"></option>` : "";
  $("#payment-service").value = service?.id || "";
  $("#payment-selected-customer").value = customer?.full_name || "Pendiente";
  $("#payment-selected-phone").value = customer?.phones?.join(" · ") || "Pendiente";
  $("#payment-selected-service").value = service?.amr_code || "Pendiente";
  $("#payment-selected-address").value = service?.address || "Pendiente";
}

function selectPaymentLookupResult(kind, id) {
  const service = kind === "service" ? (state.services || []).find((item) => item.id === id) : null;
  const customerId = service?.current_customer_id || (kind === "customer" ? id : null);
  const customer = (state.customers || []).find((item) => item.id === customerId) || null;
  setPaymentSelection(customer, service);
  $("#payment-lookup-input").value = service ? `${service.amr_code} · ${customer?.full_name || "Pendiente"}` : customerDisplayLabel(customer);
  $("#payment-lookup-results").innerHTML = "";
  if (!customer && service) {
    $("#payment-form-error").textContent = "Este servicio no tiene un cliente asignado. Aparecerá como pendiente hasta que se asigne un titular.";
  }
}

function renderPaymentLookupResults() {
  const query = $("#payment-lookup-input").value.trim().toLowerCase();
  const results = $("#payment-lookup-results");
  if (!query) { results.textContent = "Escribe para buscar un servicio o cliente."; return; }
  const customers = state.customers || [];
  const services = (state.services || []).filter((service) => paymentLookupText(service, customers.find((customer) => customer.id === service.current_customer_id)).includes(query)).slice(0, 8);
  const matchedCustomerIds = new Set(services.map((service) => service.current_customer_id).filter(Boolean));
  const matchingCustomers = customers.filter((customer) => !matchedCustomerIds.has(customer.id) && customerDisplayLabel(customer).toLowerCase().includes(query)).slice(0, 4);
  const items = [
    ...services.map((service) => {
      const customer = customers.find((item) => item.id === service.current_customer_id);
      const phone = customer?.phones?.[0] || "Pendiente";
      return `<button class="payment-lookup-option" type="button" data-payment-result-kind="service" data-payment-result-id="${service.id}" role="option"><strong>${escapeText(service.amr_code)}</strong><span>${escapeText(customer?.full_name || "Cliente pendiente")} · ${escapeText(phone)}<small>${escapeText(service.address || "Dirección pendiente")}</small></span></button>`;
    }),
    ...matchingCustomers.map((customer) => `<button class="payment-lookup-option" type="button" data-payment-result-kind="customer" data-payment-result-id="${customer.id}" role="option"><strong>Cliente</strong><span>${escapeText(customer.full_name)} · ${escapeText(customer.phones?.[0] || "Teléfono pendiente")}</span></button>`),
  ];
  results.innerHTML = items.length ? items.join("") : "No se encontraron servicios ni clientes con ese dato.";
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
  $("#payment-lookup-input").value = "";
  $("#payment-lookup-results").textContent = "Escribe para buscar un servicio o cliente.";
  setPaymentSelection(null, null);
  $("#payment-amount").value = "";
  $("#payment-method").value = "cash";
  $("#payment-declared-at").value = localDateTimeValue();
  updatePaymentReferenceOptions();
  $("#payment-proof-file").value = "";
  state.pendingPaymentProofFile = null;
  updatePaymentProofStatus();
  $("#payment-notes").value = "";
  $("#payment-form-error").textContent = "";
  $("#payment-dialog").showModal();
  $("#payment-lookup-input").focus();
  return true;
}

function updatePaymentProofStatus() {
  const selected = $("#payment-proof-file").files?.[0]
    || state.pendingPaymentProofFile;
  const dropzone = $("#payment-proof-dropzone");
  dropzone.classList.toggle("has-file", Boolean(selected));
  dropzone.classList.remove("drag-active");
  $("#payment-proof-status").textContent = selected
    ? `Archivo listo: ${selected.name || "comprobante"} · ${formatPaymentProofSize(selected.size)}`
    : "Imagen o PDF de hasta 10 MB.";
}

function formatPaymentProofSize(bytes) {
  if (bytes < 1024 * 1024) {
    return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function acceptPaymentProofFile(file) {
  if (!file) return false;
  const errorBox = $("#payment-form-error");
  const supportedTypes = new Set([
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/pdf",
  ]);
  const supportedName = /\.(jpe?g|png|webp|pdf)$/i.test(file.name || "");
  if (!supportedTypes.has((file.type || "").toLowerCase()) && !supportedName) {
    errorBox.textContent = "Usa una imagen JPG, PNG, WEBP o un archivo PDF.";
    return false;
  }
  if (file.size <= 0) {
    errorBox.textContent = "El archivo del comprobante está vacío.";
    return false;
  }
  if (file.size > 10 * 1024 * 1024) {
    errorBox.textContent = "El comprobante no puede superar 10 MB.";
    return false;
  }
  errorBox.textContent = "";
  attachPaymentProofFile(file);
  return true;
}

function attachPaymentProofFile(file) {
  state.pendingPaymentProofFile = file || null;
  const input = $("#payment-proof-file");
  try {
    if (file && typeof DataTransfer === "function") {
      const transfer = new DataTransfer();
      transfer.items.add(file);
      input.files = transfer.files;
    }
  } catch (error) {
    // Algunos WebView no permiten asignar FileList. El archivo se conserva en
    // el estado temporal y se adjunta al enviar el formulario.
    console.warn("El selector no permitió reflejar el archivo compartido.", error);
  }
  updatePaymentProofStatus();
}

function openSharedReceiptFallbackDialog() {
  $("#shared-receipt-fallback-file").value = "";
  $("#shared-receipt-fallback-error").textContent = "";
  $("#shared-receipt-fallback-dialog").showModal();
}

function closeSharedReceiptFallbackDialog() {
  $("#shared-receipt-fallback-dialog").close();
}

function continueSharedReceiptFallback(event) {
  event.preventDefault();
  const file = $("#shared-receipt-fallback-file").files?.[0];
  const errorBox = $("#shared-receipt-fallback-error");
  errorBox.textContent = "";
  if (!file) {
    errorBox.textContent = "Selecciona la imagen o el PDF del comprobante.";
    return;
  }
  if (file.size > 10 * 1024 * 1024) {
    errorBox.textContent = "El comprobante no puede superar 10 MB.";
    return;
  }
  closeSharedReceiptFallbackDialog();
  if (!openPaymentDialog()) return;
  attachPaymentProofFile(file);
  $("#payment-method").value = "bank_transfer";
  updatePaymentReferenceOptions();
  $("#payment-notes").value =
    "Comprobante seleccionado manualmente porque Android no entregó el archivo compartido desde WhatsApp.";
  setNotice(
    "Comprobante recuperado. Selecciona al cliente y completa los datos del pago."
  );
}

const paymentAccountReferences = [
  "BANORTE-4320",
  "BANORTE-430",
  "BANAMEX-8591",
  "BANAMEX-4302",
  "BANCOPPEL-928",
  "BANCOPPEL-4135",
  "BANCOPPEL-137",
  "BBVA-6732",
  "BBVA-5755",
  "BBVA-9460",
  "BBVA-7656",
  "BBVA-6818",
  "BBVA-6816",
  "BBVA-6826",
  "BBVA-0071",
  "BBVA-716",
  "BBVA-826",
  "BBVA-4724",
];

function updatePaymentReferenceOptions() {
  const reference = $("#payment-reference");
  const isCash = $("#payment-method").value === "cash";
  const options = isCash ? ["Efectivo"] : paymentAccountReferences;
  reference.innerHTML = options
    .map((item) => `<option value="${escapeText(item)}">${escapeText(item)}</option>`)
    .join("");
}

function closePaymentDialog() {
  $("#payment-dialog").close();
  state.pendingPaymentProofFile = null;
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
    payload.append("reference", $("#payment-reference").value);
    if (optionalText("#payment-notes")) {
      payload.append("notes", optionalText("#payment-notes"));
    }
    payload.append("received_by", state.user.display_name);
    const proofFile = $("#payment-proof-file").files?.[0]
      || state.pendingPaymentProofFile;
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
    state.pendingPaymentProofFile = null;
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
        previewBox.innerHTML = payment.proof_kind === "pdf"
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
  const customer = (state.customers || []).find(
    (item) => item.id === payment?.customer_id
  );
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
    // El estado de cuenta se consulta de nuevo después de aplicar el pago para
    // mostrar los saldos definitivos, no una copia anterior del navegador.
    if (customer && hasCapability("billing.read")) {
      await openAccountDialog(customer);
    }
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
    const services = (state.services || []).filter(
      (service) => service.current_customer_id === customer.id && service.status !== "cancelled"
    );
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
      ${services.map((service) => `
        <div>
          <span>${escapeText(service.amr_code)} · ${escapeText(service.plan_name)}</span>
          <strong>${formatMoney(service.monthly_price)} · Día ${service.payment_day}</strong>
        </div>
      `).join("")}
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
