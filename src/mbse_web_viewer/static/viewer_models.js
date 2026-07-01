import { fetchText } from "./viewer_api.js";
import { viewerState } from "./viewer_state.js";
import { escapeHtml } from "./viewer_utils.js";
import {
  captureViewportState,
  refreshFitBaseline,
  restoreViewportState,
} from "./viewer_viewport.js";


export async function loadSessionSvg(session, modelId) {
  const model = getModelById(session.models || [], modelId);
  if (model === null) {
    throw new Error(`Unknown session model: ${modelId}`);
  }
  await loadModelSvg(model, { preserveViewState: true });
}


export async function loadModelSvg(model, { preserveViewState = true } = {}) {
  const svgText = await fetchText(model.svg_url);
  loadSvgText(model.model_id, svgText, { preserveViewState });
}


export function loadSvgText(modelId, svgText, { preserveViewState = true } = {}) {
  saveDisplayedModelViewState();
  document.getElementById("svg-root").innerHTML = svgText;
  viewerState.displayedModelId = modelId;
  const savedViewState = viewerState.modelViewStateById[modelId];
  if (preserveViewState && savedViewState !== undefined) {
    restoreViewportState(savedViewState);
    return;
  }
  viewerState.lastAutoCenteredFocusKey = null;
  refreshFitBaseline({ apply: true });
  saveDisplayedModelViewState();
}


export function saveDisplayedModelViewState() {
  if (viewerState.displayedModelId === null) {
    return;
  }
  viewerState.modelViewStateById[viewerState.displayedModelId] = captureViewportState();
}


export function renderModelOptions(models, activeModelId) {
  const select = document.getElementById("model-select");
  select.innerHTML = models.map((model) => `
    <option value="${escapeHtml(model.model_id)}">
      ${escapeHtml(model.model_id)}${model.is_entrypoint ? " *" : ""} (${escapeHtml(model.kind)})
    </option>
  `).join("");
  select.value = activeModelId;
  select.disabled = models.length <= 1;
}


export function getSessionActiveModelId(session) {
  return session.active_model_id;
}


export function getSessionModelById(modelId) {
  return getModelById(viewerState.sessionModels, modelId);
}


export function getModelById(models, modelId) {
  for (const model of models) {
    if (model.model_id === modelId) {
      return model;
    }
  }
  return null;
}


export function getDisplayedModelKind() {
  const model = getSessionModelById(viewerState.displayedModelId);
  return model?.kind || null;
}
