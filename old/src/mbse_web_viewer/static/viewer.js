const DEFAULT_ZOOM = 1;
const MIN_ZOOM = 0.5;
const MAX_ZOOM = 2;
const ZOOM_STEP = 0.2;
const DEFAULT_SIDEBAR_WIDTH_PX = 288;
const ACTIVE_STATE_CLASS = "is-active-state";
const ACTIVE_TRANSITION_CLASS = "is-active-transition";
const ACTIVE_TEXT_CLASS = "is-active-text";
const PAN_ACTIVE_CLASS = "is-pan-active";

const viewerState = {
  zoomScale: DEFAULT_ZOOM,
  isDragging: false,
  dragStartX: 0,
  dragStartY: 0,
  dragStartScrollLeft: 0,
  dragStartScrollTop: 0,
  sidebarWidthPx: DEFAULT_SIDEBAR_WIDTH_PX,
  fitBaseline: {
    zoomScale: DEFAULT_ZOOM,
    scrollLeft: 0,
    scrollTop: 0,
  },
};

async function loadSession() {
  const session = await fetchJson("/api/session.json");
  const svgText = await fetchText(session.svg_url);
  document.getElementById("svg-root").innerHTML = svgText;
  applySidebarWidth(viewerState.sidebarWidthPx);
  refreshFitBaseline({ apply: true });
  wireResetForm();
  wireResetViewButton();
  wireEventForm();
  wireLayoutSplitter();
  wireViewportZoom();
  wireViewportPan();
  renderSession(session);
}

function wireResetForm() {
  const form = document.getElementById("reset-form");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    await submitRuntimeAction("/api/runtime/reset", {});
  });
}

function wireResetViewButton() {
  const button = document.getElementById("reset-view-button");
  button.addEventListener("click", () => {
    refreshFitBaseline({ apply: true });
  });
}

function wireEventForm() {
  const form = document.getElementById("event-form");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const eventId = document.getElementById("event-select").value;
    await submitRuntimeAction("/api/runtime/events", { event_id: eventId });
  });
}

async function submitRuntimeAction(url, payload) {
  try {
    const session = await fetchJson(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    renderSession(session);
  } catch (error) {
    await refreshSession();
  }
}

function renderSession(session) {
  renderSelectOptions("event-select", session.event_ids);
  renderVariableList(session.variable_ids, session.snapshot.variables);
  clearHighlights();
  applyHighlights(
    session,
  );
}

function renderVariableList(variableIds, variables) {
  const container = document.getElementById("variable-list");
  if (variableIds.length === 0) {
    container.innerHTML = '<p class="empty-state">No declared variables.</p>';
    return;
  }

  container.innerHTML = variableIds
    .map((variableId) => renderVariableRow(variableId, variables[variableId]))
    .join("");

  for (const form of container.querySelectorAll(".variable-row")) {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const variableId = form.dataset.variableId || "";
      const rawValue = form.querySelector("input").value.trim();

      try {
        const value = rawValue.length === 0 ? null : JSON.parse(rawValue);
        await submitRuntimeAction("/api/runtime/variables", {
          variable_id: variableId,
          value,
        });
      } catch (error) {
        await refreshSession();
      }
    });
  }
}

function renderVariableRow(variableId, value) {
  const formattedInput = formatVariableInput(value);
  const isUnset = value === undefined;
  return `
    <form
      class="variable-row"
      data-variable-id="${escapeHtml(variableId)}"
    >
      <div class="variable-row-main">
        <strong>${escapeHtml(variableId)}</strong>
        <div class="variable-row-input">
          <input
            name="value"
            type="text"
            value="${escapeHtml(formattedInput)}"
            placeholder='3 or "auto" or true'
          />
          <span class="variable-unset">${isUnset ? "Unset" : ""}</span>
        </div>
        <button type="submit">Set</button>
      </div>
    </form>
  `;
}

function renderSelectOptions(elementId, values) {
  const select = document.getElementById(elementId);
  const currentValue = select.value;
  select.innerHTML = "";
  for (const value of values) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.appendChild(option);
  }
  if (values.includes(currentValue)) {
    select.value = currentValue;
  }
  select.disabled = values.length === 0;
  const form = select.closest("form");
  form.querySelector("button").disabled = values.length === 0;
}

function wireViewportZoom() {
  document.getElementById("svg-viewport").addEventListener("wheel", (event) => {
    event.preventDefault();
    const direction = event.deltaY < 0 ? 1 : -1;
    applyZoom(viewerState.zoomScale + (direction * ZOOM_STEP));
  });
}

function wireViewportPan() {
  const viewport = document.getElementById("svg-viewport");
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

function wireLayoutSplitter() {
  const splitter = document.getElementById("layout-splitter");
  function updateSidebarWidth(event) {
    applySidebarWidth(event.clientX);
  }
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

function applyZoom(nextZoom) {
  const svgRoot = document.getElementById("svg-root");
  viewerState.zoomScale = clampInteractiveZoom(nextZoom);
  svgRoot.style.transform = `scale(${viewerState.zoomScale})`;
  syncStageSize();
}

function applySidebarWidth(nextWidthPx) {
  const layout = document.getElementById("layout");
  viewerState.sidebarWidthPx = Math.max(220, nextWidthPx);
  layout.style.setProperty("--sidebar-width", `${viewerState.sidebarWidthPx}px`);
}

function computeFitBaseline() {
  const viewportSize = measureViewportContentSize();
  const svg = document.getElementById("svg-root").querySelector("svg");
  const svgSize = measureSvgSize(svg);
  if (svgSize.width <= 0 || svgSize.height <= 0) {
    return {
      zoomScale: DEFAULT_ZOOM,
      scrollLeft: 0,
      scrollTop: 0,
    };
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

function parsePixelSize(value) {
  const numeric = Number.parseFloat(value || "0");
  return Number.isFinite(numeric) ? numeric : 0;
}

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
  if (typeof svg.getBBox === "function") {
    const bbox = svg.getBBox();
    if (bbox.width > 0 && bbox.height > 0) {
      return { width: bbox.width, height: bbox.height };
    }
  }
  return {
    width: Number(svg.clientWidth) || 0,
    height: Number(svg.clientHeight) || 0,
  };
}

function measureRenderedSvgSize(svg) {
  if (typeof svg.getBoundingClientRect !== "function") {
    return { width: 0, height: 0 };
  }
  const rect = svg.getBoundingClientRect();
  const zoomScale = viewerState.zoomScale > 0 ? viewerState.zoomScale : 1;
  const width = Number(rect.width) / zoomScale;
  const height = Number(rect.height) / zoomScale;
  return {
    width: Number.isFinite(width) ? width : 0,
    height: Number.isFinite(height) ? height : 0,
  };
}

function applyViewBaseline(viewBaseline) {
  const viewport = document.getElementById("svg-viewport");
  viewerState.zoomScale = viewBaseline.zoomScale;
  document.getElementById("svg-root").style.transform =
    `scale(${viewerState.zoomScale})`;
  syncStageSize();
  viewport.scrollLeft = viewBaseline.scrollLeft;
  viewport.scrollTop = viewBaseline.scrollTop;
}

function refreshFitBaseline({ apply = false } = {}) {
  viewerState.fitBaseline = computeFitBaseline();
  if (apply) {
    applyViewBaseline(viewerState.fitBaseline);
  }
}

function clampInteractiveZoom(nextZoom) {
  const minZoom = Math.min(MIN_ZOOM, viewerState.fitBaseline.zoomScale);
  const maxZoom = Math.max(MAX_ZOOM, viewerState.fitBaseline.zoomScale);
  return Math.min(maxZoom, Math.max(minZoom, nextZoom));
}

function syncStageSize() {
  const viewportSize = measureViewportContentSize();
  const stage = document.getElementById("svg-stage");
  const svg = document.getElementById("svg-root").querySelector("svg");
  const svgSize = measureSvgSize(svg);
  const scaledWidth = svgSize.width * viewerState.zoomScale;
  const scaledHeight = svgSize.height * viewerState.zoomScale;
  stage.style.width = `${Math.max(viewportSize.width, scaledWidth)}px`;
  stage.style.height = `${Math.max(viewportSize.height, scaledHeight)}px`;
  stage.dataset.scaledWidth = String(scaledWidth);
  stage.dataset.scaledHeight = String(scaledHeight);
}

function setPanInteractionState(isActive) {
  const viewport = document.getElementById("svg-viewport");
  const body = document.body;
  viewport.classList.toggle(PAN_ACTIVE_CLASS, isActive);
  viewport.dataset.panActive = isActive ? "true" : "false";
  if (!body) {
    return;
  }
  body.classList.toggle(PAN_ACTIVE_CLASS, isActive);
  body.dataset.panActive = isActive ? "true" : "false";
}

function applyHighlights(session) {
  applyHighlightClass(session.snapshot.active_ids, ACTIVE_STATE_CLASS);
  if (session.snapshot.last_event.guard_node_id) {
    applyHighlightClass([session.snapshot.last_event.guard_node_id], ACTIVE_STATE_CLASS);
  }
  if (session.snapshot.last_event.transition_path_ids.length > 0) {
    applyHighlightClass(
      session.snapshot.last_event.transition_path_ids,
      ACTIVE_TRANSITION_CLASS,
    );
  }
  if (session.snapshot.last_event.guard_branch_id) {
    applyHighlightClass([session.snapshot.last_event.guard_branch_id], ACTIVE_TRANSITION_CLASS);
  }
  applyHighlightClass(resolveTextHighlightIds(session), ACTIVE_TEXT_CLASS);
}

function resolveTextHighlightIds(session) {
  const textTargets = session.text_targets || {};
  const lastEvent = session.snapshot.last_event || {};
  const resolvedIds = new Set();

  for (const transitionId of lastEvent.transition_path_ids || []) {
    addResolvedIds(
      resolvedIds,
      textTargets.external_transition_label_ids?.[transitionId],
    );
  }

  if (lastEvent.handler_kind === "internal_transition") {
    addResolvedIds(
      resolvedIds,
      textTargets.internal_transition_section_ids?.[lastEvent.handler_id],
    );
    addResolvedIds(
      resolvedIds,
      textTargets.internal_transition_event_ids?.[lastEvent.handler_id],
    );
  }

  for (const activity of lastEvent.executed_activities || []) {
    if (activity.owner_kind === "external_transition") {
      addResolvedIds(
        resolvedIds,
        textTargets.external_transition_activity_ids?.[activity.owner_id]?.[activity.activity_id],
      );
      continue;
    }
    if (activity.owner_kind === "internal_transition") {
      addResolvedIds(
        resolvedIds,
        textTargets.internal_transition_activity_ids?.[activity.owner_id]?.[activity.activity_id],
      );
      continue;
    }
    if (activity.owner_kind === "guard_branch") {
      addResolvedIds(
        resolvedIds,
        textTargets.external_transition_activity_ids?.[activity.owner_id]?.[activity.activity_id],
      );
      continue;
    }
    if (activity.owner_kind.startsWith("state_")) {
      const slotName = activity.owner_kind.slice("state_".length);
      addResolvedIds(
        resolvedIds,
        textTargets.lifecycle_section_ids?.[activity.owner_id]?.[slotName],
      );
      addResolvedIds(
        resolvedIds,
        textTargets.lifecycle_activity_ids?.[activity.owner_id]?.[slotName]?.[activity.activity_id],
      );
    }
  }

  return Array.from(resolvedIds);
}

function addResolvedIds(target, ids) {
  for (const id of ids || []) {
    target.add(id);
  }
}

function applyHighlightClass(ids, className) {
  for (const id of ids) {
    const element = document.getElementById(id);
    if (element !== null) {
      element.classList.add(className);
    }
  }
}

function clearHighlightClass(className) {
  for (const element of document.querySelectorAll(`.${className}`)) {
    element.classList.remove(className);
  }
}

function clearHighlights() {
  clearHighlightClass(ACTIVE_STATE_CLASS);
  clearHighlightClass(ACTIVE_TRANSITION_CLASS);
  clearHighlightClass(ACTIVE_TEXT_CLASS);
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

async function fetchText(url) {
  const response = await fetch(url);
  return response.text();
}

async function refreshSession() {
  const session = await fetchJson("/api/session.json");
  renderSession(session);
}

function formatVariableInput(value) {
  if (value === undefined) {
    return "";
  }
  return JSON.stringify(value);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

void loadSession();
