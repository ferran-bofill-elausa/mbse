import {
  BREAKPOINT_ACTIVE_CLASS,
  BREAKPOINT_CENTER_SUPPRESSION_MS,
  BREAKPOINT_DRAGGING_CLASS,
  BREAKPOINT_DROP_TARGET_CLASS,
  BREAKPOINT_LIST_DRAGGING_CLASS,
  BREAKPOINT_MARKER_CLASS,
  BREAKPOINT_SET_CLASS,
  BREAKPOINT_TARGET_CLASS,
  SVG_NAMESPACE,
  viewerState,
} from "./viewer_state.js";
import { cssEscape, escapeHtml } from "./viewer_utils.js";
import { centerViewportOnBounds, measureFocusBounds } from "./viewer_viewport.js";


let submitRuntimeActionHandler = null;
let switchDisplayedModelHandler = null;


export function configureBreakpoints({ submitRuntimeAction, switchDisplayedModel }) {
  submitRuntimeActionHandler = submitRuntimeAction;
  switchDisplayedModelHandler = switchDisplayedModel;
}


export function renderBreakpointList(breakpointTargets) {
  const container = document.getElementById("debugger-breakpoints");
  const setTargets = breakpointTargets.filter((target) => target.is_set);
  if (setTargets.length === 0) {
    container.innerHTML = `
      <div class="debugger-queue-item">Breakpoints <strong>(0)</strong>:</div>
    `;
    return;
  }

  container.innerHTML = `
    <div class="debugger-queue-item">Breakpoints <strong>(${setTargets.length})</strong>:</div>
    <div class="debugger-breakpoint-box">
      <ul class="debugger-breakpoint-list">
        ${setTargets.map((target) => `
          <li class="debugger-breakpoint-list-item" data-breakpoint-id="${escapeHtml(target.id)}">
            <div class="debugger-breakpoint-toggle">
              <input
                class="debugger-breakpoint-enabled"
                type="checkbox"
                data-breakpoint-id="${escapeHtml(target.id)}"
                ${target.enabled ? "checked" : ""}
              />
              <button
                class="debugger-breakpoint-center-button"
                type="button"
                data-breakpoint-id="${escapeHtml(target.id)}"
                draggable="true"
                title="Center breakpoint in diagram"
                aria-label="Center breakpoint in diagram"
              >
                ${escapeHtml(target.label)}
              </button>
            </div>
            <button
              class="debugger-breakpoint-remove-button"
              type="button"
              data-breakpoint-id="${escapeHtml(target.id)}"
              title="Remove breakpoint"
              aria-label="Remove breakpoint"
            >
              x
            </button>
          </li>
        `).join("")}
      </ul>
    </div>
  `;

  for (const input of container.querySelectorAll(".debugger-breakpoint-enabled")) {
    input.addEventListener("change", async () => {
      await submitBreakpointRuntimeAction("/api/debugger/breakpoints/enabled", {
        breakpoint_id: input.dataset.breakpointId,
        enabled: input.checked,
      });
    });
  }

  for (const button of container.querySelectorAll(".debugger-breakpoint-remove-button")) {
    button.addEventListener("click", async () => {
      await submitBreakpointRuntimeAction("/api/debugger/breakpoints/remove", {
        breakpoint_id: button.dataset.breakpointId,
      });
    });
  }

  for (const button of container.querySelectorAll(".debugger-breakpoint-center-button")) {
    button.addEventListener("click", async () => {
      if (
        viewerState.suppressBreakpointCenterId === (button.dataset.breakpointId || "")
        && Date.now() <= viewerState.suppressBreakpointCenterUntilMs
      ) {
        viewerState.suppressBreakpointCenterId = null;
        viewerState.suppressBreakpointCenterUntilMs = 0;
        return;
      }
      await centerViewportOnBreakpoint(button.dataset.breakpointId || "");
    });

    button.addEventListener("dragstart", (event) => {
      startBreakpointDrag(event, button.dataset.breakpointId || "");
    });

    button.addEventListener("dragend", () => {
      finishBreakpointDrag();
    });
  }

  for (const listItem of container.querySelectorAll(".debugger-breakpoint-list-item")) {
    listItem.addEventListener("dragover", (event) => {
      event.preventDefault();
      updateBreakpointDropTarget(listItem, event.clientY);
    });

    listItem.addEventListener("drop", async (event) => {
      event.preventDefault();
      const reorderedBreakpointIds = buildReorderedBreakpointIds(listItem, event.clientY);
      finishBreakpointDrag();
      if (reorderedBreakpointIds === null) {
        return;
      }
      await submitBreakpointRuntimeAction("/api/debugger/breakpoints/order", {
        breakpoint_ids: reorderedBreakpointIds,
      });
    });
  }
}


export function renderBreakpointMarkers(breakpointTargets) {
  for (const marker of document.querySelectorAll(`.${BREAKPOINT_MARKER_CLASS}`)) {
    marker.classList.remove(BREAKPOINT_ACTIVE_CLASS);
    marker.removeAttribute("data-breakpoint-id");
  }

  for (const target of getDisplayedModelBreakpointTargets(breakpointTargets)) {
    for (const textId of target.text_ids || []) {
      const textElement = document.getElementById(textId);
      if (textElement === null) {
        continue;
      }
      const marker = ensureBreakpointMarker(textElement);
      marker.dataset.breakpointId = target.id;
      textElement.dataset.breakpointId = target.id;
      textElement.classList.add(BREAKPOINT_TARGET_CLASS);
    }
  }
}


export function applyBreakpointClasses(breakpointTargets) {
  clearBreakpointClass(BREAKPOINT_ACTIVE_CLASS);
  clearBreakpointClass(BREAKPOINT_SET_CLASS);
  clearBreakpointClass(BREAKPOINT_TARGET_CLASS);
  for (const target of getDisplayedModelBreakpointTargets(breakpointTargets)) {
    for (const textId of target.text_ids || []) {
      const textElement = document.getElementById(textId);
      if (textElement !== null) {
        textElement.classList.add(BREAKPOINT_TARGET_CLASS);
      }
    }
    if (!target.is_set) {
      continue;
    }
    for (const textId of target.text_ids || []) {
      const marker = document.querySelector(
        `[data-breakpoint-marker-for="${cssEscape(textId)}"]`,
      );
      marker?.classList.add(BREAKPOINT_SET_CLASS);
      if (target.enabled) {
        marker?.classList.add(BREAKPOINT_ACTIVE_CLASS);
      }
    }
  }
}


function submitBreakpointRuntimeAction(url, payload) {
  if (submitRuntimeActionHandler === null) {
    throw new Error("Breakpoint runtime action handler is not configured.");
  }
  return submitRuntimeActionHandler(url, payload, {
    autoCenter: false,
    syncDisplayedModel: false,
  });
}


async function switchBreakpointModel(modelId) {
  if (switchDisplayedModelHandler === null) {
    throw new Error("Breakpoint model switch handler is not configured.");
  }
  await switchDisplayedModelHandler(modelId, { autoCenter: false });
}


function ensureBreakpointMarker(textElement) {
  if (textElement.dataset.breakpointMarkerId !== undefined) {
    const marker = document.querySelector(
      `[data-breakpoint-marker-for="${cssEscape(textElement.id)}"]`,
    );
    if (marker !== null) {
      return marker;
    }
  }

  if (textElement.tagName.toLowerCase() === "text") {
    return ensureTextElementBreakpointMarker(textElement);
  }
  return ensureTspanBreakpointMarker(textElement);
}


function ensureTextElementBreakpointMarker(textElement) {
  const existingText = textElement.textContent || "";
  textElement.textContent = "";

  const marker = createBreakpointMarker(textElement.id);
  const content = document.createElementNS(SVG_NAMESPACE, "tspan");
  content.textContent = existingText;
  textElement.append(marker, content);
  textElement.dataset.breakpointMarkerId = textElement.id;
  return marker;
}


function ensureTspanBreakpointMarker(textElement) {
  const marker = createBreakpointMarker(textElement.id);
  textElement.parentElement?.insertBefore(marker, textElement);
  textElement.dataset.breakpointMarkerId = textElement.id;
  return marker;
}


function createBreakpointMarker(textId) {
  const marker = document.createElementNS(SVG_NAMESPACE, "tspan");
  marker.textContent = "\u25CF ";
  marker.classList.add(BREAKPOINT_MARKER_CLASS);
  marker.dataset.breakpointMarkerFor = textId;
  return marker;
}


function clearBreakpointClass(className) {
  for (const element of document.querySelectorAll(`.${className}`)) {
    element.classList.remove(className);
  }
}


async function centerViewportOnBreakpoint(breakpointId) {
  const breakpointTarget = getBreakpointTargetById(breakpointId);
  if (breakpointTarget === null || (breakpointTarget.text_ids || []).length === 0) {
    return;
  }
  if (breakpointTarget.model_id !== viewerState.displayedModelId) {
    await switchBreakpointModel(breakpointTarget.model_id);
  }
  const focusBounds = measureFocusBounds(breakpointTarget.text_ids);
  if (focusBounds === null) {
    return;
  }
  centerViewportOnBounds(focusBounds);
}


function startBreakpointDrag(event, breakpointId) {
  const listItem = getBreakpointListItem(breakpointId);
  if (listItem === null) {
    return;
  }
  viewerState.breakpointDragState = { breakpointId };
  listItem.classList.add(BREAKPOINT_DRAGGING_CLASS);
  document.getElementById("debugger-breakpoints")
    .classList.add(BREAKPOINT_LIST_DRAGGING_CLASS);
  if (event.dataTransfer !== null) {
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", breakpointId);
  }
}


function finishBreakpointDrag() {
  const draggedBreakpointId = viewerState.breakpointDragState?.breakpointId || null;
  if (draggedBreakpointId !== null) {
    getBreakpointListItem(draggedBreakpointId)?.classList.remove(BREAKPOINT_DRAGGING_CLASS);
    viewerState.suppressBreakpointCenterId = draggedBreakpointId;
    viewerState.suppressBreakpointCenterUntilMs = (
      Date.now() + BREAKPOINT_CENTER_SUPPRESSION_MS
    );
  }
  viewerState.breakpointDragState = null;
  document.getElementById("debugger-breakpoints")
    .classList.remove(BREAKPOINT_LIST_DRAGGING_CLASS);
  for (const element of document.querySelectorAll(`.${BREAKPOINT_DROP_TARGET_CLASS}`)) {
    element.classList.remove(BREAKPOINT_DROP_TARGET_CLASS);
    delete element.dataset.breakpointDropEdge;
  }
}


function updateBreakpointDropTarget(listItem, clientY) {
  const dragState = viewerState.breakpointDragState;
  if (dragState === null || listItem.dataset.breakpointId === dragState.breakpointId) {
    return;
  }
  for (const element of document.querySelectorAll(`.${BREAKPOINT_DROP_TARGET_CLASS}`)) {
    element.classList.remove(BREAKPOINT_DROP_TARGET_CLASS);
  }
  const targetEdge = getBreakpointDropEdge(listItem, clientY);
  listItem.classList.add(BREAKPOINT_DROP_TARGET_CLASS);
  listItem.dataset.breakpointDropEdge = targetEdge;
}


function buildReorderedBreakpointIds(listItem, clientY) {
  const dragState = viewerState.breakpointDragState;
  if (dragState === null) {
    return null;
  }
  const draggedBreakpointId = dragState.breakpointId;
  const targetBreakpointId = listItem.dataset.breakpointId || "";
  if (draggedBreakpointId === "" || targetBreakpointId === "" || draggedBreakpointId === targetBreakpointId) {
    return null;
  }

  const orderedBreakpointIds = getRenderedSetBreakpointIds();
  const draggedBreakpointIndex = orderedBreakpointIds.indexOf(draggedBreakpointId);
  const targetBreakpointIndex = orderedBreakpointIds.indexOf(targetBreakpointId);
  if (draggedBreakpointIndex < 0 || targetBreakpointIndex < 0) {
    return null;
  }

  orderedBreakpointIds.splice(draggedBreakpointIndex, 1);
  let insertionIndex = orderedBreakpointIds.indexOf(targetBreakpointId);
  if (insertionIndex < 0) {
    orderedBreakpointIds.push(draggedBreakpointId);
    return orderedBreakpointIds;
  }
  if (getBreakpointDropEdge(listItem, clientY) === "after") {
    insertionIndex += 1;
  }
  orderedBreakpointIds.splice(insertionIndex, 0, draggedBreakpointId);
  return orderedBreakpointIds;
}


function getBreakpointDropEdge(listItem, clientY) {
  const rect = listItem.getBoundingClientRect();
  return clientY >= rect.top + (rect.height / 2) ? "after" : "before";
}


function getBreakpointTargetById(breakpointId) {
  for (const breakpointTarget of viewerState.breakpointTargets) {
    if (breakpointTarget.id === breakpointId) {
      return breakpointTarget;
    }
  }
  return null;
}


function getDisplayedModelBreakpointTargets(breakpointTargets) {
  return breakpointTargets.filter(
    (target) => target.model_id === viewerState.displayedModelId,
  );
}


function getBreakpointListItem(breakpointId) {
  return document.querySelector(
    `.debugger-breakpoint-list-item[data-breakpoint-id="${cssEscape(breakpointId)}"]`,
  );
}


function getRenderedSetBreakpointIds() {
  return Array.from(
    document.querySelectorAll(".debugger-breakpoint-list-item[data-breakpoint-id]"),
    (element) => element.dataset.breakpointId || "",
  ).filter((breakpointId) => breakpointId !== "");
}
