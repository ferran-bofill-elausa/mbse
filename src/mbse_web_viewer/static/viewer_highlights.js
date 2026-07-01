import {
  ACTIVE_STATE_CLASS,
  ACTIVE_TEXT_CLASS,
  ACTIVE_TRANSITION_CLASS,
  CURRENT_STEP_CLASS,
  CURRENT_STEP_TEXT_CLASS,
  FOCUS_DIMMED_CLASS,
  FOCUS_RELATED_CLASS,
  viewerState,
} from "./viewer_state.js";
import { getDisplayedModelKind } from "./viewer_models.js";
import { centerViewportOnFocusTarget } from "./viewer_viewport.js";


export function applyDisplayedHighlight() {
  clearHighlights();
  const highlight = viewerState.highlightsByModel[viewerState.displayedModelId] || {
    state_ids: [],
    transition_ids: [],
    text_ids: [],
    current_transition_ids: [],
    current_text_ids: [],
  };
  applyHighlightClass(highlight.state_ids || [], ACTIVE_STATE_CLASS);
  applyHighlightClass(highlight.transition_ids || [], ACTIVE_TRANSITION_CLASS);
  applyHighlightClass(highlight.text_ids || [], ACTIVE_TEXT_CLASS);
  applyHighlightClass(highlight.current_transition_ids || [], CURRENT_STEP_CLASS);
  applyHighlightClass(highlight.current_text_ids || [], CURRENT_STEP_TEXT_CLASS);
}


export function applyViewMode() {
  clearFocusMode();
  if (viewerState.viewMode === "normal" || getDisplayedModelKind() !== "hsm") {
    return;
  }

  const focusModel = getFocusModel();
  applyFocusMode(focusModel.relatedIds);
}


export function applyAutoCenter() {
  centerViewportOnFocusTarget(getAutoCenterFocusIds());
}


export function clearFocusMode() {
  for (const element of document.querySelectorAll(`.${FOCUS_RELATED_CLASS}`)) {
    element.classList.remove(FOCUS_RELATED_CLASS);
  }
  for (const element of document.querySelectorAll(`.${FOCUS_DIMMED_CLASS}`)) {
    element.classList.remove(FOCUS_DIMMED_CLASS);
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
  clearHighlightClass(CURRENT_STEP_CLASS);
  clearHighlightClass(CURRENT_STEP_TEXT_CLASS);
}


function getFocusModel() {
  if (viewerState.viewMode === "trace") {
    return {
      relatedIds: viewerState.focusTraceRelatedIds,
      viewportFocusIds: viewerState.viewportTraceFocusIds,
    };
  }

  return {
    relatedIds: viewerState.focusStateRelatedIds,
    viewportFocusIds: viewerState.viewportStateFocusIds,
  };
}


function getAutoCenterFocusIds() {
  if (viewerState.hasPendingExecution) {
    return viewerState.viewportTraceFocusIds;
  }

  if (viewerState.viewMode === "state") {
    return viewerState.viewportStateFocusIds;
  }

  return viewerState.viewportTraceFocusIds;
}


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

  if (relatedElements.size === 0) {
    return;
  }

  for (const element of svgRoot.querySelectorAll("[id]")) {
    if (relatedElements.has(element)) {
      element.classList.add(FOCUS_RELATED_CLASS);
      continue;
    }
    element.classList.add(FOCUS_DIMMED_CLASS);
  }
}
