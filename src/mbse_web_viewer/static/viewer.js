const DEFAULT_ZOOM = 1;
const MIN_ZOOM = 0.5;
const MAX_ZOOM = 2;
const ZOOM_INTENSITY = 0.0015;
const DEFAULT_SIDEBAR_WIDTH_PX = 288;
const ACTIVE_STATE_CLASS = "is-active-state";
const ACTIVE_TRANSITION_CLASS = "is-active-transition";
const ACTIVE_TEXT_CLASS = "is-active-text";
const CURRENT_STEP_CLASS = "is-current-step";
const CURRENT_STEP_TEXT_CLASS = "is-current-step-text";
const FOCUS_RELATED_CLASS = "is-focus-related";
const FOCUS_DIMMED_CLASS = "is-focus-dimmed";
const PAN_ACTIVE_CLASS = "is-pan-active";

const viewerState = {
  zoomScale: DEFAULT_ZOOM,
  isDragging: false,
  dragStartX: 0,
  dragStartY: 0,
  dragStartScrollLeft: 0,
  dragStartScrollTop: 0,
  sidebarWidthPx: DEFAULT_SIDEBAR_WIDTH_PX,
  viewMode: "normal",
  autoCenterEnabled: true,
  focusStateRelatedIds: [],
  focusTraceRelatedIds: [],
  viewportStateFocusIds: [],
  viewportTraceFocusIds: [],
  lastAutoCenteredFocusKey: null,
  sessionEvents: [],
  sessionEnums: [],
  sessionVariables: [],
  isPaused: true,
  hasPendingExecution: false,
  eventDraftEventId: null,
  eventDraftParameters: null,
  fitBaseline: {
    zoomScale: DEFAULT_ZOOM,
    scrollLeft: 0,
    scrollTop: 0,
  },
};


// Bootstrap.


/**
 * Load the initial viewer session, inject the SVG, and wire UI behavior.
 */
async function loadSession() {
  const session = await fetchJson("/api/session.json");
  const svgText = await fetchText(session.svg_url);
  document.getElementById("svg-root").innerHTML = svgText;

  applySidebarWidth(viewerState.sidebarWidthPx);
  refreshFitBaseline({ apply: true });

  wireResetForm();
  wireResetViewButton();
  wireViewModeForm();
  wireDebuggerControls();
  wireEventForm();
  wireLayoutSplitter();
  wireViewportZoom();
  wireViewportPan();
  renderSession(session);
}


// Event wiring.


/**
 * Attach reset-runtime form submission to the runtime reset endpoint.
 */
function wireResetForm() {
  const form = document.getElementById("reset-form");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
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
 * Attach the debugger play and step buttons to their runtime endpoints.
 */
function wireDebuggerControls() {
  document.getElementById("debugger-play-button").addEventListener("click", async () => {
    await submitRuntimeAction("/api/runtime/play", {});
  });
  document.getElementById("debugger-pause-button").addEventListener("click", async () => {
    await submitRuntimeAction("/api/runtime/pause", {});
  });
  document.getElementById("debugger-step-button").addEventListener("click", async () => {
    await submitRuntimeAction("/api/runtime/step", {});
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

  /**
   * Update the sidebar width from the current cursor position.
   */
  function updateSidebarWidth(event) {
    applySidebarWidth(event.clientX);
  }

  /**
   * Stop resizing and recompute the fit baseline after layout changes.
   */
  function stopResizing() {
    document.removeEventListener("mousemove", updateSidebarWidth);
    document.removeEventListener("mouseup", stopResizing);
    refreshFitBaseline({ apply: true });
  }

  splitter.addEventListener("mousedown", (event) => {
    updateSidebarWidth(event);
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

  /**
   * Move the viewport scroll position while the user drags the diagram.
   */
  function handlePanMove(event) {
    if (!viewerState.isDragging) {
      return;
    }
    event.preventDefault?.();
    viewport.scrollLeft =
      viewerState.dragStartScrollLeft + (viewerState.dragStartX - event.clientX);
    viewport.scrollTop =
      viewerState.dragStartScrollTop + (viewerState.dragStartY - event.clientY);
  }

  /**
   * Stop an active pan gesture and clear the temporary document listeners.
   */
  function stopDragging() {
    if (!viewerState.isDragging) {
      return;
    }
    viewerState.isDragging = false;
    document.removeEventListener("mousemove", handlePanMove);
    document.removeEventListener("mouseup", stopDragging);
    setPanInteractionState(false);
  }

  viewport.addEventListener("mousedown", (event) => {
    event.preventDefault?.();
    viewerState.isDragging = true;
    viewerState.dragStartX = event.clientX;
    viewerState.dragStartY = event.clientY;
    viewerState.dragStartScrollLeft = viewport.scrollLeft;
    viewerState.dragStartScrollTop = viewport.scrollTop;
    setPanInteractionState(true);
    document.addEventListener("mousemove", handlePanMove);
    document.addEventListener("mouseup", stopDragging);
  });
}


// Runtime requests.


/**
 * Submit one runtime mutation and refresh the rendered session afterwards.
 */
async function submitRuntimeAction(url, payload) {
  try {
    const session = await fetchJson(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    renderSession(session);
  } catch (error) {
    // Fall back to a full session refresh so the UI re-synchronizes after failures.
    await refreshSession();
  }
}


/**
 * Refresh the session model from the server and re-render the UI.
 */
async function refreshSession() {
  const session = await fetchJson("/api/session.json");
  renderSession(session);
}


// Session rendering.


/**
 * Render one full server session into the viewer UI and highlight state.
 */
function renderSession(session) {
  renderState(session.state);
  renderExecutionLog(session.execution_log || []);
  renderEventHistory(session.debugger?.event_history || []);
  viewerState.sessionEvents = session.events || [];
  viewerState.sessionEnums = session.enums || [];
  viewerState.sessionVariables = session.variables || [];
  viewerState.isPaused = Boolean(session.debugger?.is_paused);
  viewerState.hasPendingExecution = Boolean(session.debugger?.has_pending_execution);
  renderEventOptions(viewerState.sessionEvents);
  renderEventParameterList();
  renderVariableList(viewerState.sessionVariables, session.variable_values, viewerState.sessionEnums);
  renderDebugger(session.debugger || {});
  viewerState.focusStateRelatedIds = session.focus?.state_related_ids || [];
  viewerState.focusTraceRelatedIds = session.focus?.trace_related_ids || [];
  viewerState.viewportStateFocusIds = session.focus?.state_viewport_focus_ids || [];
  viewerState.viewportTraceFocusIds = session.focus?.trace_viewport_focus_ids || [];
  clearHighlights();
  clearFocusMode();
  applyHighlightClass(session.highlight.state_ids || [], ACTIVE_STATE_CLASS);
  applyHighlightClass(session.highlight.transition_ids || [], ACTIVE_TRANSITION_CLASS);
  applyHighlightClass(session.highlight.text_ids || [], ACTIVE_TEXT_CLASS);
  applyHighlightClass(session.highlight.current_transition_ids || [], CURRENT_STEP_CLASS);
  applyHighlightClass(session.highlight.current_text_ids || [], CURRENT_STEP_TEXT_CLASS);
  applyViewMode();
  applyAutoCenter();
}


/**
 * Render the runtime debugger panel and action enablement.
 */
function renderDebugger(debuggerState) {
  const currentEvent = document.getElementById("debugger-current-event");
  const status = document.getElementById("debugger-status");
  const queue = document.getElementById("debugger-queue");
  const playButton = document.getElementById("debugger-play-button");
  const pauseButton = document.getElementById("debugger-pause-button");
  const stepButton = document.getElementById("debugger-step-button");
  const activeEvent = debuggerState.current_event;
  const queuedEvents = debuggerState.queued_events || [];
  const hasPendingExecution = Boolean(debuggerState.has_pending_execution);
  const canStep = Boolean(debuggerState.can_step);
  const isPaused = Boolean(debuggerState.is_paused);

  playButton.disabled = !isPaused && !hasPendingExecution && queuedEvents.length === 0;
  pauseButton.disabled = isPaused;
  stepButton.disabled = !canStep;

  currentEvent.innerHTML = activeEvent === null
    ? '<div class="debugger-queue-item">Current event: idle</div>'
    : `
      <div class="debugger-queue-item">Current event: <strong>${escapeHtml(activeEvent.event_id || "<init>")}</strong></div>
      ${renderEventParametersSummary(activeEvent.parameters || {})}
    `;

  if (!isPaused) {
    status.textContent = "Running";
  } else if (hasPendingExecution) {
    status.textContent = "Paused during current event";
  } else if (queuedEvents.length > 0) {
    status.textContent = "Paused between events";
  } else {
    status.textContent = "Paused and idle";
  }

  if (queuedEvents.length === 0) {
    queue.innerHTML = '<div class="debugger-queue-item">Queued events: 0</div>';
    return;
  }

  queue.innerHTML = [
    `<div class="debugger-queue-item">Queued events: ${queuedEvents.length}</div>`,
    ...queuedEvents.map((event) => (
      `
        <div class="debugger-queue-item">${escapeHtml(event.event_id || "<init>")}</div>
        ${renderEventParametersSummary(event.parameters || {})}
      `
    )),
  ].join("");
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
 * Render the current active state summary in the sidebar.
 */
function renderState(state) {
  const container = document.getElementById("state-box");
  if (!state || state.id === null) {
    container.innerHTML = '<p class="trace-entry">Uninitialized</p>';
    return;
  }
  container.innerHTML = `
    <div><strong>${escapeHtml(state.id)}</strong></div>
    <div>${escapeHtml(state.label || "")}</div>
  `;
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
function renderVariableList(variableDefinitions, variableValues, enums) {
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
    ))
    .join("");

  for (const form of container.querySelectorAll(".variable-row")) {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const variableId = form.dataset.variableId || "";
      const variableDefinition = getDeclaredVariableByName(variableId);
      if (variableDefinition === null) {
        return;
      }

      const value = collectDeclaredValue(variableDefinition, form);
      if (value === null) {
        return;
      }

      await submitRuntimeAction("/api/runtime/variables", {
        variable_id: variableId,
        value,
      });
    });
  }
}


/**
 * Return the HTML markup for one variable row form.
 */
function renderVariableRow(variableDefinition, value, enums) {
  const variableId = variableDefinition.name;
  return `
    <form class="variable-row" data-variable-id="${escapeHtml(variableId)}">
      <div class="variable-row-label">${escapeHtml(formatDeclaredValueLabel(variableDefinition))}</div>
      <div class="variable-row-main">
        <strong>${escapeHtml(variableId)}</strong>
        <div class="variable-row-input">
          ${renderDeclaredValueInput(variableDefinition, value, enums)}
        </div>
        <button type="submit">Set</button>
      </div>
    </form>
  `;
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
        <label class="event-parameter-label" for="event-parameter-${escapeHtml(parameterDefinition.name)}">
          ${escapeHtml(formatDeclaredValueLabel(parameterDefinition))}
        </label>
        ${renderDeclaredValueInput(parameterDefinition, draftParameters?.[parameterDefinition.name], viewerState.sessionEnums, {
          inputId: `event-parameter-${parameterDefinition.name}`,
          inputName: parameterDefinition.name,
        })}
      </div>
    `)
    .join("");
}


// Viewport layout and navigation.


/**
 * Apply one new interactive zoom level and resize the stage accordingly.
 */
function applyZoom(nextZoom, anchor = null) {
  const viewport = anchor?.viewport || document.getElementById("svg-viewport");
  const svgRoot = document.getElementById("svg-root");
  const previousZoomScale = viewerState.zoomScale;
  let anchoredContentPoint = null;

  if (anchor !== null && previousZoomScale > 0) {
    const viewportRect = viewport.getBoundingClientRect();
    const offsetX = anchor.clientX - viewportRect.left;
    const offsetY = anchor.clientY - viewportRect.top;

    // Preserve the diagram point under the cursor while zooming.
    anchoredContentPoint = {
      offsetX,
      offsetY,
      x: (viewport.scrollLeft + offsetX) / previousZoomScale,
      y: (viewport.scrollTop + offsetY) / previousZoomScale,
    };
  }

  viewerState.zoomScale = clampInteractiveZoom(nextZoom);
  svgRoot.style.transform = `scale(${viewerState.zoomScale})`;
  syncStageSize();

  if (anchoredContentPoint !== null) {
    viewport.scrollLeft =
      (anchoredContentPoint.x * viewerState.zoomScale) - anchoredContentPoint.offsetX;
    viewport.scrollTop =
      (anchoredContentPoint.y * viewerState.zoomScale) - anchoredContentPoint.offsetY;
  }
}


/**
 * Apply one sidebar width in pixels, clamped to a minimum usable size.
 */
function applySidebarWidth(nextWidthPx) {
  const layout = document.getElementById("layout");
  viewerState.sidebarWidthPx = Math.max(220, nextWidthPx);
  layout.style.setProperty("--sidebar-width", `${viewerState.sidebarWidthPx}px`);
}


/**
 * Compute the zoom and scroll offsets needed to fit the full SVG into the viewport.
 */
function computeFitBaseline() {
  const viewportSize = measureViewportContentSize();
  const svg = document.getElementById("svg-root").querySelector("svg");
  const svgSize = measureSvgSize(svg);
  if (svgSize.width <= 0 || svgSize.height <= 0) {
    return { zoomScale: DEFAULT_ZOOM, scrollLeft: 0, scrollTop: 0 };
  }

  const widthScale = viewportSize.width / svgSize.width;
  const heightScale = viewportSize.height / svgSize.height;
  const zoomScale = Math.min(widthScale, heightScale);
  return {
    zoomScale,
    scrollLeft: Math.max(0, ((svgSize.width * zoomScale) - viewportSize.width) / 2),
    scrollTop: Math.max(0, ((svgSize.height * zoomScale) - viewportSize.height) / 2),
  };
}


/**
 * Measure the usable viewport content area excluding CSS padding.
 */
function measureViewportContentSize() {
  const viewport = document.getElementById("svg-viewport");
  const styles = globalThis.getComputedStyle?.(viewport);
  const horizontalPadding =
    parsePixelSize(styles?.paddingLeft) + parsePixelSize(styles?.paddingRight);
  const verticalPadding =
    parsePixelSize(styles?.paddingTop) + parsePixelSize(styles?.paddingBottom);
  return {
    width: Math.max(0, viewport.clientWidth - horizontalPadding),
    height: Math.max(0, viewport.clientHeight - verticalPadding),
  };
}


/**
 * Parse one CSS pixel value to a finite number.
 */
function parsePixelSize(value) {
  const numeric = Number.parseFloat(value || "0");
  return Number.isFinite(numeric) ? numeric : 0;
}


/**
 * Measure the unscaled SVG size using rendered geometry first, then static metadata.
 */
function measureSvgSize(svg) {
  if (!svg) {
    return { width: 0, height: 0 };
  }

  const renderedSize = measureRenderedSvgSize(svg);
  if (renderedSize.width > 0 && renderedSize.height > 0) {
    return renderedSize;
  }

  if (svg.viewBox && svg.viewBox.baseVal) {
    const width = Number(svg.viewBox.baseVal.width);
    const height = Number(svg.viewBox.baseVal.height);
    if (width > 0 && height > 0) {
      return { width, height };
    }
  }

  return { width: Number(svg.clientWidth) || 0, height: Number(svg.clientHeight) || 0 };
}


/**
 * Measure the currently rendered SVG size and divide out the active zoom scale.
 */
function measureRenderedSvgSize(svg) {
  if (typeof svg.getBoundingClientRect !== "function") {
    return { width: 0, height: 0 };
  }

  const rect = svg.getBoundingClientRect();
  const zoomScale = viewerState.zoomScale > 0 ? viewerState.zoomScale : 1;
  return { width: Number(rect.width) / zoomScale, height: Number(rect.height) / zoomScale };
}


/**
 * Apply one computed fit baseline to the viewport and stage.
 */
function applyViewBaseline(viewBaseline) {
  const viewport = document.getElementById("svg-viewport");
  viewerState.zoomScale = viewBaseline.zoomScale;
  document.getElementById("svg-root").style.transform = `scale(${viewerState.zoomScale})`;
  syncStageSize();
  viewport.scrollLeft = viewBaseline.scrollLeft;
  viewport.scrollTop = viewBaseline.scrollTop;
}


/**
 * Recompute the fit baseline and optionally apply it immediately.
 */
function refreshFitBaseline({ apply = false } = {}) {
  viewerState.fitBaseline = computeFitBaseline();
  if (apply) {
    applyViewBaseline(viewerState.fitBaseline);
  }
}


/**
 * Clamp one requested zoom level against the baseline-aware interactive range.
 */
function clampInteractiveZoom(nextZoom) {
  const minZoom = Math.min(MIN_ZOOM, viewerState.fitBaseline.zoomScale);
  const maxZoom = Math.max(MAX_ZOOM, viewerState.fitBaseline.zoomScale);
  return Math.min(maxZoom, Math.max(minZoom, nextZoom));
}


/**
 * Resize the stage so the scaled SVG always has a valid scrollable canvas.
 */
function syncStageSize() {
  const viewportSize = measureViewportContentSize();
  const stage = document.getElementById("svg-stage");
  const svg = document.getElementById("svg-root").querySelector("svg");
  const svgSize = measureSvgSize(svg);
  stage.style.width = `${Math.max(viewportSize.width, svgSize.width * viewerState.zoomScale)}px`;
  stage.style.height = `${Math.max(viewportSize.height, svgSize.height * viewerState.zoomScale)}px`;
}


/**
 * Toggle the shared CSS state used while the user is actively panning.
 */
function setPanInteractionState(isActive) {
  const viewport = document.getElementById("svg-viewport");
  viewport.classList.toggle(PAN_ACTIVE_CLASS, isActive);
  document.body.classList.toggle(PAN_ACTIVE_CLASS, isActive);
}


// Highlight rendering.


/**
 * Apply one CSS class to all SVG elements matching the given ids.
 */
function applyHighlightClass(ids, className) {
  for (const id of ids) {
    const element = document.getElementById(id);
    if (element !== null) {
      element.classList.add(className);
    }
  }
}


/**
 * Remove one highlight CSS class from every currently highlighted element.
 */
function clearHighlightClass(className) {
  for (const element of document.querySelectorAll(`.${className}`)) {
    element.classList.remove(className);
  }
}


/**
 * Clear all viewer highlight classes from the rendered SVG.
 */
function clearHighlights() {
  clearHighlightClass(ACTIVE_STATE_CLASS);
  clearHighlightClass(ACTIVE_TRANSITION_CLASS);
  clearHighlightClass(ACTIVE_TEXT_CLASS);
  clearHighlightClass(CURRENT_STEP_CLASS);
  clearHighlightClass(CURRENT_STEP_TEXT_CLASS);
}


/**
 * Apply the currently selected view mode to the rendered SVG.
 */
function applyViewMode() {
  clearFocusMode();
  if (viewerState.viewMode === "normal") {
    return;
  }

  const focusModel = getFocusModel();
  applyFocusMode(focusModel.relatedIds);
}


/**
 * Return the semantic focus ids for the currently selected view mode.
 */
function getFocusModel() {
  if (viewerState.viewMode === "trace") {
    return {
      relatedIds: viewerState.focusTraceRelatedIds,
      viewportFocusIds: viewerState.viewportTraceFocusIds,
    };
  }

  if (viewerState.hasPendingExecution) {
    return {
      relatedIds: viewerState.focusTraceRelatedIds,
      viewportFocusIds: viewerState.viewportTraceFocusIds,
    };
  }

  return {
    relatedIds: Array.from(new Set([
      ...viewerState.focusTraceRelatedIds,
      ...viewerState.focusStateRelatedIds,
    ])),
    viewportFocusIds: viewerState.viewportStateFocusIds,
  };
}


/**
 * Apply viewport auto-centering independently from the current view mode.
 */
function applyAutoCenter() {
  centerViewportOnFocusTarget(getAutoCenterFocusIds());
}


/**
 * Return the active semantic target used by viewport auto-centering.
 */
function getAutoCenterFocusIds() {
  if (viewerState.hasPendingExecution) {
    return viewerState.viewportTraceFocusIds;
  }

  if (viewerState.viewMode === "state") {
    return viewerState.viewportStateFocusIds;
  }

  return viewerState.viewportTraceFocusIds;
}


/**
 * Center the viewport on the current semantic focus target without changing zoom.
 */
function centerViewportOnFocusTarget(focusIds) {
  if (!viewerState.autoCenterEnabled) {
    return;
  }
  const focusKey = focusIds.join("|");
  if (focusIds.length === 0 || viewerState.lastAutoCenteredFocusKey === focusKey) {
    return;
  }

  const focusBounds = measureFocusBounds(focusIds);
  if (focusBounds === null) {
    return;
  }

  const viewport = document.getElementById("svg-viewport");
  const viewportRect = viewport.getBoundingClientRect();
  viewport.scrollLeft = Math.max(
    0,
    viewport.scrollLeft + (focusBounds.centerX - viewportRect.left) - (viewportRect.width / 2),
  );
  viewport.scrollTop = Math.max(
    0,
    viewport.scrollTop + (focusBounds.centerY - viewportRect.top) - (viewportRect.height / 2),
  );
  viewerState.lastAutoCenteredFocusKey = focusKey;
}


/**
 * Measure one combined rendered bounding box for the requested semantic ids.
 */
function measureFocusBounds(ids) {
  let left = null;
  let top = null;
  let right = null;
  let bottom = null;

  for (const id of ids) {
    const element = document.getElementById(id);
    const box = measureSvgElementBox(element);
    if (box === null) {
      continue;
    }
    left = left === null ? box.x : Math.min(left, box.x);
    top = top === null ? box.y : Math.min(top, box.y);
    right = right === null ? box.x + box.width : Math.max(right, box.x + box.width);
    bottom = bottom === null ? box.y + box.height : Math.max(bottom, box.y + box.height);
  }

  if (left === null || top === null || right === null || bottom === null) {
    return null;
  }

  return {
    centerX: (left + right) / 2,
    centerY: (top + bottom) / 2,
  };
}


/**
 * Measure one rendered element box in viewport pixel coordinates.
 */
function measureSvgElementBox(element) {
  if (element === null || typeof element.getBoundingClientRect !== "function") {
    return null;
  }

  try {
    const box = element.getBoundingClientRect();
    return {
      x: Number(box.left),
      y: Number(box.top),
      width: Number(box.width),
      height: Number(box.height),
    };
  } catch {
    return null;
  }
}


/**
 * Dim unrelated SVG elements and keep the related focus set fully visible.
 */
function applyFocusMode(relatedIds) {
  const svgRoot = document.getElementById("svg-root");
  const relatedElements = new Set();

  for (const id of relatedIds) {
    const element = document.getElementById(id);
    if (element === null) {
      continue;
    }

    let currentElement = element;
    while (currentElement !== null && currentElement !== svgRoot) {
      relatedElements.add(currentElement);
      currentElement = currentElement.parentElement;
    }
  }

  for (const element of svgRoot.querySelectorAll("[id]")) {
    if (relatedElements.has(element)) {
      element.classList.add(FOCUS_RELATED_CLASS);
      continue;
    }
    element.classList.add(FOCUS_DIMMED_CLASS);
  }
}


/**
 * Remove all temporary focus-mode classes from the rendered SVG.
 */
function clearFocusMode() {
  for (const element of document.querySelectorAll(`.${FOCUS_RELATED_CLASS}`)) {
    element.classList.remove(FOCUS_RELATED_CLASS);
  }
  for (const element of document.querySelectorAll(`.${FOCUS_DIMMED_CLASS}`)) {
    element.classList.remove(FOCUS_DIMMED_CLASS);
  }
}


// Network and formatting helpers.


/**
 * Fetch one JSON resource and reject non-success HTTP responses.
 */
async function fetchJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}


/**
 * Fetch one text resource and reject non-success HTTP responses.
 */
async function fetchText(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.text();
}


/**
 * Return compact HTML for one event parameter dictionary.
 */
function renderEventParametersSummary(parameters) {
  const parameterNames = Object.keys(parameters);
  if (parameterNames.length === 0) {
    return "";
  }
  return `<div class="debugger-queue-item">${escapeHtml(JSON.stringify(parameters))}</div>`;
}


/**
 * Format one compact label for one typed variable or event parameter.
 */
function formatDeclaredValueLabel(declaredValue) {
  if (declaredValue.type === "enum") {
    return `${declaredValue.name} (${declaredValue.type}: ${declaredValue.enum_id})`;
  }
  if (declaredValue.type === "bool") {
    return `${declaredValue.name} (${declaredValue.type})`;
  }
  return `${declaredValue.name} (${declaredValue.type}: ${declaredValue.min}..${declaredValue.max})`;
}


/**
 * Return the HTML input markup for one typed variable or event parameter.
 */
function renderDeclaredValueInput(declaredValue, value, enums, options = {}) {
  const inputId = options.inputId || `${declaredValue.name}-input`;
  const inputName = options.inputName || "value";

  if (declaredValue.type === "bool") {
    return `
      <input
        id="${escapeHtml(inputId)}"
        name="${escapeHtml(inputName)}"
        type="checkbox"
        class="checkbox-input"
        ${value === true ? "checked" : ""}
      />
    `;
  }

  if (declaredValue.type === "enum") {
    const enumDefinition = getEnumById(declaredValue.enum_id, enums);
    const enumValues = enumDefinition?.values || [];
    return `
      <select id="${escapeHtml(inputId)}" name="${escapeHtml(inputName)}" required>
        <option value=""></option>
        ${enumValues
          .map((enumValue) => `
            <option value="${escapeHtml(enumValue)}" ${value === enumValue ? "selected" : ""}>
              ${escapeHtml(enumValue)}
            </option>
          `)
          .join("")}
      </select>
    `;
  }

  return `
    <input
      id="${escapeHtml(inputId)}"
      name="${escapeHtml(inputName)}"
      type="number"
      ${declaredValue.type === "float" ? 'step="any"' : 'step="1"'}
      min="${escapeHtml(String(declaredValue.min))}"
      max="${escapeHtml(String(declaredValue.max))}"
      required
      value="${value === undefined ? "" : escapeHtml(String(value))}"
    />
  `;
}


/**
 * Collect one full declared-value dictionary from one parameter definition list.
 */
function collectDeclaredValues(declaredValues, container) {
  const resolvedValues = {};

  for (const declaredValue of declaredValues) {
    const value = collectDeclaredValue(declaredValue, container);
    if (value === null) {
      return null;
    }
    resolvedValues[declaredValue.name] = value;
  }

  return resolvedValues;
}


/**
 * Collect one typed variable or event parameter value from one form scope.
 */
function collectDeclaredValue(declaredValue, container) {
  const input = container.querySelector(`[name="${declaredValue.name}"], [name="value"]`);
  if (input === null) {
    return null;
  }

  if (declaredValue.type === "bool") {
    return Boolean(input.checked);
  }

  const rawValue = String(input.value || "").trim();
  if (rawValue.length === 0) {
    input.reportValidity?.();
    return null;
  }

  if (declaredValue.type === "enum") {
    return rawValue;
  }

  const numericValue = declaredValue.type === "float"
    ? Number.parseFloat(rawValue)
    : Number.parseInt(rawValue, 10);
  if (!Number.isFinite(numericValue)) {
    input.reportValidity?.();
    return null;
  }
  return numericValue;
}


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


/**
 * Return one enum declaration by id from the current session state.
 */
function getEnumById(enumId, enums = viewerState.sessionEnums) {
  return enums.find((enumDefinition) => enumDefinition.id === enumId) || null;
}


/**
 * Escape one value for safe HTML interpolation.
 */
function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}


void loadSession();
