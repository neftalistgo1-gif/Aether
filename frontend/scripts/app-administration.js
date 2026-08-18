/* Administración: planes, sincronización UISP, navegación, sesión y PWA. */
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
