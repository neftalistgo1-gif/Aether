/* Operación diaria: incidencias, soporte y seguimiento técnico de atención. */
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
  const suspended = devices.filter((item) => item.suspended_in_mikrotik).length;
  const offline = devices.filter((item) => item.current_status === "offline" && !item.suspended_in_mikrotik).length;
  const online = devices.filter((item) => item.current_status === "online").length;
  $("#network-summary").textContent = devices.length
    ? `${online} en línea · ${offline} sin conexión · ${suspended} suspendidos · ${devices.length} equipos registrados`
    : "No hay información de red disponible.";
  $("#network-devices-table").innerHTML = devices.length
    ? devices.map((item) => {
        const details = item.observed_details || {};
        const lastSeen = item.last_seen_at ? new Date(item.last_seen_at).toLocaleString("es-MX") : "Sin lectura";
        const status = item.suspended_in_mikrotik ? "suspended" : item.current_status;
        const statusLabel = item.suspended_in_mikrotik ? "Suspendido" : item.current_status;
        return `<tr><td><strong>${escapeText(item.display_name)}</strong><br><span class="muted-copy">${escapeText(item.mac_address || "")}</span></td><td>${item.device_type === "access_point" ? "AP" : item.device_type === "station" ? "CPE" : "Otro"}</td><td><span class="badge ${escapeText(status)}">${escapeText(statusLabel)}</span></td><td>${escapeText(item.management_ip || "—")}</td><td>${details.signal ?? "—"}${details.signal != null ? " dBm" : ""}</td><td>${details.frequency ?? "—"}${details.frequency != null ? " MHz" : ""}</td><td>${escapeText(lastSeen)}</td></tr>`;
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
