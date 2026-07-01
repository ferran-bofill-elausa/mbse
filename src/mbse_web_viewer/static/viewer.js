import { fetchJson } from "./viewer_api.js";
import {
  collectDeclaredValue,
  collectDeclaredValues,
  isDeclaredValueInputDifferent,
  renderDeclaredValueInput,
  renderDeclaredValueName,
} from "./viewer_declared_values.js";
import {
  ZOOM_INTENSITY,
  viewerState,
} from "./viewer_state.js";
import { escapeHtml } from "./viewer_utils.js";
import {
  getSessionActiveModelId,
  getSessionModelById,
  loadModelSvg,
  loadSessionSvg,
  renderModelOptions,
  saveDisplayedModelViewState,
} from "./viewer_models.js";
import {
  applyAutoCenter,
  applyDisplayedHighlight,
  applyViewMode,
  clearFocusMode,
} from "./viewer_highlights.js";
import {
  applyBreakpointClasses,
  configureBreakpoints,
  renderBreakpointList,
  renderBreakpointMarkers,
} from "./viewer_breakpoints.js";
import {
  renderDebugger,
  renderEventParametersSummary,
} from "./viewer_debugger.js";
import {
  applySidebarWidth,
  applyZoom,
  refreshFitBaseline,
  setPanInteractionState,
  syncStageSize,
} from "./viewer_viewport.js";


const PAN_START_THRESHOLD_PX = 3;


// Bootstrap.


/**
 * Load the initial viewer session, inject the SVG, and wire UI behavior.
 */
async function loadSession() {
  const session = await fetchJson("/api/session.json");
  await loadSessionSvg(session, getSessionActiveModelId(session));

  applySidebarWidth(viewerState.sidebarWidthPx);
  refreshFitBaseline({ apply: true });
  configureBreakpoints({ submitRuntimeAction, switchDisplayedModel });

  wireResetRuntimeButton();
  wireResetViewButton();
  wireViewModeForm();
  wireModelSelect();
  wireDebuggerControls();
  wireEventForm();
  wireLayoutSplitter();
  wireViewportZoom();
  wireViewportPan();
  wireBreakpointToggle();
  await renderSession(session);
}


// Event wiring.


/**
 * Attach the reset-runtime debugger button to the runtime reset endpoint.
 */
function wireResetRuntimeButton() {
  const button = document.getElementById("debugger-reset-button");
  button.addEventListener("click", async () => {
    await submitRuntimeAction("/api/runtime/reset", {});
  });
}


/**
 * Attach the reset-view button to recompute and apply the fit baseline.
 */
function wireResetViewButton() {
  const button = document.getElementById("reset-view-button");
  button.addEventListener("click", () => {
    refreshFitBaseline({ apply: true });
  });
}


/**
 * Attach the local view-mode selector and reapply diagram emphasis on change.
 */
function wireViewModeForm() {
  const select = document.getElementById("view-mode-select");
  const autoCenterCheckbox = document.getElementById("auto-center-checkbox");
  select.value = viewerState.viewMode;
  autoCenterCheckbox.checked = viewerState.autoCenterEnabled;
  select.addEventListener("change", () => {
    viewerState.viewMode = select.value;
    viewerState.lastAutoCenteredFocusKey = null;
    applyViewMode();
  });
  autoCenterCheckbox.addEventListener("change", () => {
    viewerState.autoCenterEnabled = autoCenterCheckbox.checked;
    viewerState.lastAutoCenteredFocusKey = null;
    if (viewerState.autoCenterEnabled) {
      applyViewMode();
    }
  });
}


/**
 * Attach model navigation to the session-declared model list.
 */
function wireModelSelect() {
  const select = document.getElementById("model-select");
  select.addEventListener("change", async () => {
    const model = getSessionModelById(select.value);
    if (model === null) {
      return;
    }
    await switchDisplayedModel(model.model_id, { autoCenter: false });
  });
}


/**
 * Attach debugger controls to their runtime endpoints.
 */
function wireDebuggerControls() {
  document.getElementById("debugger-play-button").addEventListener("click", async () => {
    await submitRuntimeAction("/api/runtime/play", {});
  });
  document.getElementById("debugger-pause-button").addEventListener("click", async () => {
    await submitRuntimeAction("/api/runtime/pause", {});
  });
  document.getElementById("debugger-step-into-button").addEventListener("click", async () => {
    await submitRuntimeAction("/api/runtime/step-into", {});
  });
  document.getElementById("debugger-step-over-button").addEventListener("click", async () => {
    await submitRuntimeAction("/api/runtime/step-over", {});
  });
  document.getElementById("debugger-step-out-button").addEventListener("click", async () => {
    await submitRuntimeAction("/api/runtime/step-out", {});
  });
}


/**
 * Attach event-form submission to the runtime event endpoint.
 */
function wireEventForm() {
  const form = document.getElementById("event-form");
  const select = document.getElementById("event-select");

  select.addEventListener("change", () => {
    clearEventDraft();
    renderEventParameterList();
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const eventId = select.value;
    const eventDefinition = getSelectedEventDefinition();
    const parameters = eventDefinition === null
      ? {}
      : collectDeclaredValues(
        eventDefinition.parameters || [],
        document.getElementById("event-form"),
      );

    if (parameters === null) {
      return;
    }

    storeEventDraft(eventId, parameters);

    const payload = { event_id: eventId };
    if (eventDefinition !== null && (eventDefinition.parameters || []).length > 0) {
      payload.parameters = parameters;
    }
    await submitRuntimeAction("/api/runtime/events", payload);
  });
}


/**
 * Attach drag-based resizing for the left sidebar.
 */
function wireLayoutSplitter() {
  const splitter = document.getElementById("layout-splitter");
  let resizeStartX = 0;
  let resizeStartSidebarWidthPx = viewerState.sidebarWidthPx;

  /**
   * Update the sidebar width from the cursor movement since drag start.
   */
  function updateSidebarWidth(event) {
    applySidebarWidth(resizeStartSidebarWidthPx + event.clientX - resizeStartX);
  }

  /**
   * Stop resizing and recompute the fit baseline after layout changes.
   */
  function stopResizing() {
    document.removeEventListener("mousemove", updateSidebarWidth);
    document.removeEventListener("mouseup", stopResizing);
    document.body.classList.remove("is-resizing-sidebar");
    refreshFitBaseline({ apply: false });
    syncStageSize();
  }

  splitter.addEventListener("mousedown", (event) => {
    event.preventDefault();
    resizeStartX = event.clientX;
    resizeStartSidebarWidthPx = viewerState.sidebarWidthPx;
    document.body.classList.add("is-resizing-sidebar");
    document.addEventListener("mousemove", updateSidebarWidth);
    document.addEventListener("mouseup", stopResizing);
  });
}


/**
 * Attach wheel-based zoom behavior to the SVG viewport.
 */
function wireViewportZoom() {
  const viewport = document.getElementById("svg-viewport");
  viewport.addEventListener("wheel", (event) => {
    event.preventDefault();
    const zoomFactor = Math.exp(-event.deltaY * ZOOM_INTENSITY);
    applyZoom(viewerState.zoomScale * zoomFactor, {
      viewport,
      clientX: event.clientX,
      clientY: event.clientY,
    });
  });
}


/**
 * Attach drag-to-pan behavior to the SVG viewport.
 */
function wireViewportPan() {
  const viewport = document.getElementById("svg-viewport");
  let isPanPending = false;

  /**
   * Move the viewport scroll position while the user drags the diagram.
   */
  function handlePanMove(event) {
    if (!isPanPending && !viewerState.isDragging) {
      return;
    }

    const deltaX = event.clientX - viewerState.dragStartX;
    const deltaY = event.clientY - viewerState.dragStartY;
    if (!viewerState.isDragging) {
      if (Math.hypot(deltaX, deltaY) < PAN_START_THRESHOLD_PX) {
        return;
      }
      viewerState.isDragging = true;
      setPanInteractionState(true);
    }

    event.preventDefault?.();
    viewport.scrollLeft =
      viewerState.dragStartScrollLeft - deltaX;
    viewport.scrollTop =
      viewerState.dragStartScrollTop - deltaY;
  }

  /**
   * Stop an active pan gesture and clear the temporary document listeners.
   */
  function stopDragging() {
    if (!isPanPending && !viewerState.isDragging) {
      return;
    }
    isPanPending = false;
    viewerState.isDragging = false;
    document.removeEventListener("mousemove", handlePanMove);
    document.removeEventListener("mouseup", stopDragging);
    setPanInteractionState(false);
  }

  viewport.addEventListener("mousedown", (event) => {
    if (event.button !== 0) {
      return;
    }
    event.preventDefault?.();
    isPanPending = true;
    viewerState.isDragging = false;
    viewerState.dragStartX = event.clientX;
    viewerState.dragStartY = event.clientY;
    viewerState.dragStartScrollLeft = viewport.scrollLeft;
    viewerState.dragStartScrollTop = viewport.scrollTop;
    document.addEventListener("mousemove", handlePanMove);
    document.addEventListener("mouseup", stopDragging);
  });
}


/**
 * Toggle debugger breakpoints by clicking marked SVG text targets.
 */
function wireBreakpointToggle() {
  document.getElementById("svg-root").addEventListener("click", async (event) => {
    const target = event.target.closest?.("[data-breakpoint-id]");
    if (target === undefined || target === null) {
      return;
    }
    event.preventDefault?.();
    event.stopPropagation?.();
    await submitRuntimeAction("/api/debugger/breakpoints/toggle", {
      breakpoint_id: target.dataset.breakpointId,
    }, {
      autoCenter: false,
      syncDisplayedModel: false,
    });
  });
}


// Runtime requests.


/**
 * Submit one runtime mutation and refresh the rendered session afterwards.
 */
async function submitRuntimeAction(url, payload, options = {}) {
  const autoCenter = options.autoCenter ?? true;
  const syncDisplayedModel = options.syncDisplayedModel
    ?? !url.startsWith("/api/debugger/breakpoints/");
  const session = await fetchJson(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  await renderSession(session, { autoCenter, syncDisplayedModel });
}


/**
 * Refresh the session model from the server and re-render the UI.
 */
async function refreshSession() {
  const session = await fetchJson("/api/session.json");
  await renderSession(session);
}


/**
 * Switch to one declared model and reapply all visual state for its fresh SVG.
 */
async function switchDisplayedModel(modelId, { autoCenter }) {
  const model = getSessionModelById(modelId);
  if (model === null) {
    return;
  }
  await loadModelSvg(model, { preserveViewState: true });
  rehydrateDisplayedSvg({ autoCenter });
}


// Session rendering.


/**
 * Render one full server session into the viewer UI and highlight state.
 */
async function renderSession(
  session,
  { autoCenter = true, syncDisplayedModel = true } = {},
) {
  renderExecutionLog(session.execution_log || []);
  renderEventHistory(session.debugger?.event_history || []);
  viewerState.sessionModels = session.models || [];
  viewerState.activeModelId = getSessionActiveModelId(session);
  if (
    viewerState.displayedModelId === null
    || (syncDisplayedModel && viewerState.displayedModelId !== viewerState.activeModelId)
  ) {
    await loadSessionSvg(session, viewerState.activeModelId);
  }
  viewerState.sessionEvents = session.events || [];
  viewerState.sessionEnums = session.enums || [];
  viewerState.sessionVariables = session.variables || [];
  viewerState.changedVariableIds = session.changed_variable_ids || [];
  viewerState.breakpointTargets = session.breakpoints || [];
  viewerState.highlightsByModel = session.highlights_by_model || {};
  viewerState.isPaused = Boolean(session.debugger?.is_paused);
  viewerState.hasPendingExecution = Boolean(session.debugger?.has_pending_execution);
  renderEventOptions(viewerState.sessionEvents);
  renderModelOptions(
    viewerState.sessionModels,
    viewerState.displayedModelId || viewerState.activeModelId,
  );
  renderEventParameterList();
  renderVariableList(
    viewerState.sessionVariables,
    session.variable_values,
    viewerState.sessionEnums,
    viewerState.changedVariableIds,
  );
  renderDebugger(session.debugger || {}, session.state || null);
  renderBreakpointList(viewerState.breakpointTargets);
  viewerState.focusStateRelatedIds = session.focus?.state_related_ids || [];
  viewerState.focusTraceRelatedIds = session.focus?.trace_related_ids || [];
  viewerState.viewportStateFocusIds = session.focus?.state_viewport_focus_ids || [];
  viewerState.viewportTraceFocusIds = session.focus?.trace_viewport_focus_ids || [];
  rehydrateDisplayedSvg({ autoCenter });
}


/**
 * Reapply derived visual state after loading a clean SVG.
 */
function rehydrateDisplayedSvg({ autoCenter }) {
  renderBreakpointMarkers(viewerState.breakpointTargets);
  clearFocusMode();
  applyDisplayedHighlight();
  applyBreakpointClasses(viewerState.breakpointTargets);
  applyViewMode();
  if (autoCenter) {
    applyAutoCenter();
  }
  saveDisplayedModelViewState();
}


/**
 * Render the historical list of executed runtime events.
 */
function renderEventHistory(eventHistory) {
  const container = document.getElementById("event-history-box");
  if (eventHistory.length === 0) {
    container.innerHTML = '<p class="trace-entry">No executed events.</p>';
    return;
  }

  container.innerHTML = eventHistory.map((event, index) => `
    <div class="debugger-queue-item">
      ${escapeHtml(String(index + 1))}. <strong>${escapeHtml(event.event_id || "<init>")}</strong>
      ${renderEventParametersSummary(event.parameters || {})}
    </div>
  `).join("");
}


/**
 * Render the runtime execution log as formatted JSON for inspection.
 */
function renderExecutionLog(executionLog) {
  const container = document.getElementById("trace-box");
  if (executionLog.length === 0) {
    container.innerHTML = '<p class="trace-entry">No trace entries.</p>';
    return;
  }

  container.innerHTML = `<pre class="trace-entry">${escapeHtml(
    JSON.stringify(executionLog, null, 2),
  )}</pre>`;
}


/**
 * Render the declared variable list and wire each inline set-value form.
 */
function renderVariableList(variableDefinitions, variableValues, enums, changedVariableIds) {
  const container = document.getElementById("variable-list");
  if (variableDefinitions.length === 0) {
    container.innerHTML = '<p class="trace-entry">No declared variables.</p>';
    return;
  }

  container.innerHTML = variableDefinitions
    .map((variableDefinition) => renderVariableRow(
      variableDefinition,
      variableValues[variableDefinition.name],
      enums,
      changedVariableIds.includes(variableDefinition.name),
    ))
    .join("");

  for (const form of container.querySelectorAll(".variable-row")) {
    const variableId = form.dataset.variableId || "";
    const variableDefinition = getDeclaredVariableByName(variableId);
    if (variableDefinition === null) {
      continue;
    }
    const sessionValue = variableValues[variableId];
    const input = form.querySelector("[name='value']");
    input?.addEventListener("input", () => {
      updateVariableDraftState(form, variableDefinition, sessionValue);
    });
    input?.addEventListener("change", () => {
      updateVariableDraftState(form, variableDefinition, sessionValue);
    });

    form.addEventListener("submit", async (event) => {
      event.preventDefault();

      const value = collectDeclaredValue(variableDefinition, form);
      if (value === null) {
        return;
      }

      await submitRuntimeAction("/api/runtime/variables", {
        variable_id: variableId,
        value,
      }, {
        autoCenter: false,
      });
    });
  }
}


/**
 * Return the HTML markup for one variable row form.
 */
function renderVariableRow(variableDefinition, value, enums, isChanged) {
  const variableId = variableDefinition.name;
  return `
    <form
      class="variable-row${isChanged ? " is-variable-changed" : ""}"
      data-variable-id="${escapeHtml(variableId)}"
    >
      <div class="variable-row-main">
        ${renderDeclaredValueName(variableDefinition, { inputId: `${variableId}-input` })}
        <div class="variable-row-input">
          ${renderDeclaredValueInput(variableDefinition, value, enums, { inputId: `${variableId}-input` })}
        </div>
        <button type="submit">Set</button>
      </div>
    </form>
  `;
}


/**
 * Mark one variable row as a local draft when its input no longer matches session state.
 */
function updateVariableDraftState(form, variableDefinition, sessionValue) {
  form.classList.toggle(
    "is-variable-draft",
    isDeclaredValueInputDifferent(variableDefinition, form, sessionValue),
  );
}


/**
 * Render the available event options while preserving selection when possible.
 */
function renderEventOptions(events) {
  const select = document.getElementById("event-select");
  const currentValue = select.value;
  select.innerHTML = "";
  for (const eventDefinition of events) {
    const option = document.createElement("option");
    option.value = eventDefinition.id;
    option.textContent = eventDefinition.label || eventDefinition.id;
    select.appendChild(option);
  }
  if (events.some((eventDefinition) => eventDefinition.id === currentValue)) {
    select.value = currentValue;
  }
  select.disabled = events.length === 0;
  select.closest("form").querySelector("button").disabled = events.length === 0;
}


/**
 * Render the parameter inputs for the currently selected event.
 */
function renderEventParameterList() {
  const container = document.getElementById("event-parameter-list");
  const eventDefinition = getSelectedEventDefinition();
  const parameters = eventDefinition?.parameters || [];
  const draftParameters = getCurrentEventDraft();

  if (parameters.length === 0) {
    container.innerHTML = "";
    return;
  }

  container.innerHTML = parameters
    .map((parameterDefinition) => `
      <div class="event-parameter-row">
        ${renderDeclaredValueName(parameterDefinition, {
          inputId: `event-parameter-${parameterDefinition.name}`,
          className: "event-parameter-name",
        })}
        ${renderDeclaredValueInput(parameterDefinition, draftParameters?.[parameterDefinition.name], viewerState.sessionEnums, {
          inputId: `event-parameter-${parameterDefinition.name}`,
          inputName: parameterDefinition.name,
        })}
      </div>
    `)
    .join("");

  for (const input of container.querySelectorAll("input, select")) {
    input.addEventListener("input", storeCurrentEventParameterDraft);
    input.addEventListener("change", storeCurrentEventParameterDraft);
  }
}


// Formatting helpers.


/**
 * Return the selected event definition from the current session state.
 */
function getSelectedEventDefinition() {
  const eventId = document.getElementById("event-select").value;
  return viewerState.sessionEvents.find((eventDefinition) => eventDefinition.id === eventId) || null;
}


/**
 * Persist the latest successfully submitted parameters for the current event.
 */
function storeEventDraft(eventId, parameters) {
  viewerState.eventDraftEventId = eventId;
  viewerState.eventDraftParameters = { ...parameters };
}


/**
 * Persist the current event-parameter form as raw draft input values.
 */
function storeCurrentEventParameterDraft() {
  const eventDefinition = getSelectedEventDefinition();
  if (eventDefinition === null) {
    return;
  }

  const draftParameters = {};
  const form = document.getElementById("event-form");
  for (const parameterDefinition of eventDefinition.parameters || []) {
    const input = form.querySelector(`[name="${parameterDefinition.name}"]`);
    if (input === null) {
      continue;
    }
    draftParameters[parameterDefinition.name] = parameterDefinition.type === "bool"
      ? Boolean(input.checked)
      : input.value;
  }
  storeEventDraft(eventDefinition.id, draftParameters);
}


/**
 * Clear any remembered event parameters after switching to a different event.
 */
function clearEventDraft() {
  viewerState.eventDraftEventId = null;
  viewerState.eventDraftParameters = null;
}


/**
 * Return the remembered parameters only for the currently selected event.
 */
function getCurrentEventDraft() {
  const eventDefinition = getSelectedEventDefinition();
  if (eventDefinition === null || viewerState.eventDraftEventId !== eventDefinition.id) {
    return null;
  }
  return viewerState.eventDraftParameters;
}


/**
 * Return one declared variable definition by name.
 */
function getDeclaredVariableByName(variableName) {
  return viewerState.sessionVariables.find((variable) => variable.name === variableName) || null;
}


void loadSession();
