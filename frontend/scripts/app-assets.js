/* Inventario físico: listado, alta, detalle, asignación y devolución de equipos. */
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
  const typeFilter = $("#asset-type-filter")?.value || "";
  const rows = state.assets.filter((asset) => {
    const matchesQuery = !query || [
      asset.internal_code,
      asset.description,
      asset.device_name || "",
      asset.management_ip || "",
      asset.serial_number || "",
      asset.mac_address || "",
    ].join(" ").toLowerCase().includes(query);
    const matchesStatus = !statusFilter || asset.status === statusFilter;
    const matchesType = !typeFilter || asset.asset_type === typeFilter;
    return matchesQuery && matchesStatus && matchesType;
  });
  const assetCounts = rows.reduce((counts, asset) => {
    counts[asset.asset_type] = (counts[asset.asset_type] || 0) + 1;
    return counts;
  }, {});
  $("#asset-summary").innerHTML = [
    ["Mostrando", `${rows.length} de ${state.assets.length}`],
    ["CPE", assetCounts.cpe || 0],
    ["AP", assetCounts.access_point || 0],
    ["Routers", (assetCounts.mikrotik || 0) + (assetCounts.router_modem || 0)],
  ].map(([label, value]) => `<span class="summary-chip"><strong>${escapeText(String(value))}</strong><span>${escapeText(label)}</span></span>`).join("");
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
  empty.textContent = query || statusFilter || typeFilter
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
      <span>Nombre de equipo</span>
      <strong>${escapeText(asset.device_name || asset.description)}</strong>
    </div>
    <div>
      <span>IP de administración</span>
      <strong>${escapeText(asset.management_ip || "Sin IP")}</strong>
    </div>
    <div>
      <span>Adquirido</span>
      <strong>${formatDate(asset.acquired_on)}</strong>
    </div>
  `;
  $("#asset-detail-workspace").innerHTML = `
    <section class="cancellation-stage-card">
      <div class="stage-status"><h3>Historial de red</h3></div>
      <div class="extension-history">
        ${state.selectedAssetNetworkHistory.length ? state.selectedAssetNetworkHistory.map((change) => `
          <article class="history-item">
            <div><strong>${escapeText(change.new_device_name || "Sin nombre")} / ${escapeText(change.new_management_ip || "Sin IP")}</strong><span>UISP</span></div>
            <small>${formatDateTime(change.changed_at)}</small>
            <small>Antes: ${escapeText(change.previous_device_name || "Sin nombre")} / ${escapeText(change.previous_management_ip || "Sin IP")}</small>
          </article>
        `).join("") : '<p class="empty-state">Aún no hay cambios de IP o nombre registrados.</p>'}
      </div>
    </section>
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
  state.selectedAssetNetworkHistory = [];
  $("#asset-detail-error").textContent = "";
  $("#asset-detail-summary").innerHTML = "";
  $("#asset-detail-workspace").innerHTML = '<p class="empty-state">Cargando historial del activo...</p>';
  $("#asset-detail-dialog").showModal();
  try {
    [state.selectedAssetAssignments, state.selectedAssetNetworkHistory] = await Promise.all([
      api(`/api/v1/assets/${asset.id}/assignments`),
      api(`/api/v1/assets/${asset.id}/network-history`),
    ]);
    renderAssetWorkspace(asset);
  } catch (error) {
    $("#asset-detail-error").textContent = error.message;
  }
}

function closeAssetDetailDialog() {
  $("#asset-detail-dialog").close();
  state.selectedAssetId = null;
  state.selectedAssetAssignments = [];
  state.selectedAssetNetworkHistory = [];
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
