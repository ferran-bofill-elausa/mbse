import {
  DEFAULT_ZOOM,
  MAX_ZOOM,
  MIN_ZOOM,
  PAN_ACTIVE_CLASS,
  viewerState,
} from "./viewer_state.js";


export function applyZoom(nextZoom, anchor = null) {
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
    viewport.scrollLeft = (
      (anchoredContentPoint.x * viewerState.zoomScale)
      - anchoredContentPoint.offsetX
    );
    viewport.scrollTop = (
      (anchoredContentPoint.y * viewerState.zoomScale)
      - anchoredContentPoint.offsetY
    );
  }
}


export function applySidebarWidth(nextWidthPx) {
  const layout = document.getElementById("layout");
  viewerState.sidebarWidthPx = Math.max(220, nextWidthPx);
  layout.style.setProperty("--sidebar-width", `${viewerState.sidebarWidthPx}px`);
}


export function refreshFitBaseline({ apply = false } = {}) {
  viewerState.fitBaseline = computeFitBaseline();
  if (apply) {
    applyViewBaseline(viewerState.fitBaseline);
  }
}


export function captureViewportState() {
  const viewport = document.getElementById("svg-viewport");
  return {
    zoomScale: viewerState.zoomScale,
    scrollLeft: viewport.scrollLeft,
    scrollTop: viewport.scrollTop,
    fitBaseline: { ...viewerState.fitBaseline },
    lastAutoCenteredFocusKey: viewerState.lastAutoCenteredFocusKey,
  };
}


export function restoreViewportState(viewState) {
  viewerState.fitBaseline = { ...viewState.fitBaseline };
  applyViewBaseline(viewState);
  viewerState.lastAutoCenteredFocusKey = viewState.lastAutoCenteredFocusKey;
}


export function syncStageSize() {
  const viewportSize = measureViewportContentSize();
  const stage = document.getElementById("svg-stage");
  const svg = document.getElementById("svg-root").querySelector("svg");
  const svgSize = measureSvgSize(svg);
  stage.style.width = `${Math.max(
    viewportSize.width,
    svgSize.width * viewerState.zoomScale,
  )}px`;
  stage.style.height = `${Math.max(
    viewportSize.height,
    svgSize.height * viewerState.zoomScale,
  )}px`;
}


export function setPanInteractionState(isActive) {
  const viewport = document.getElementById("svg-viewport");
  viewport.classList.toggle(PAN_ACTIVE_CLASS, isActive);
  document.body.classList.toggle(PAN_ACTIVE_CLASS, isActive);
}


export function centerViewportOnFocusTarget(focusIds) {
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

  centerViewportOnBounds(focusBounds);
  viewerState.lastAutoCenteredFocusKey = focusKey;
}


export function centerViewportOnBounds(focusBounds) {
  const viewport = document.getElementById("svg-viewport");
  const viewportRect = viewport.getBoundingClientRect();
  viewport.scrollLeft = Math.max(
    0,
    viewport.scrollLeft
      + (focusBounds.centerX - viewportRect.left)
      - (viewportRect.width / 2),
  );
  viewport.scrollTop = Math.max(
    0,
    viewport.scrollTop
      + (focusBounds.centerY - viewportRect.top)
      - (viewportRect.height / 2),
  );
}


export function measureFocusBounds(ids) {
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


function measureViewportContentSize() {
  const viewport = document.getElementById("svg-viewport");
  const styles = globalThis.getComputedStyle?.(viewport);
  const horizontalPadding = (
    parsePixelSize(styles?.paddingLeft) + parsePixelSize(styles?.paddingRight)
  );
  const verticalPadding = (
    parsePixelSize(styles?.paddingTop) + parsePixelSize(styles?.paddingBottom)
  );
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
  return {
    width: Number(rect.width) / zoomScale,
    height: Number(rect.height) / zoomScale,
  };
}


function applyViewBaseline(viewBaseline) {
  const viewport = document.getElementById("svg-viewport");
  viewerState.zoomScale = viewBaseline.zoomScale;
  document.getElementById("svg-root").style.transform = (
    `scale(${viewerState.zoomScale})`
  );
  syncStageSize();
  viewport.scrollLeft = viewBaseline.scrollLeft;
  viewport.scrollTop = viewBaseline.scrollTop;
}


function clampInteractiveZoom(nextZoom) {
  const minZoom = Math.min(MIN_ZOOM, viewerState.fitBaseline.zoomScale);
  const maxZoom = Math.max(MAX_ZOOM, viewerState.fitBaseline.zoomScale);
  return Math.min(maxZoom, Math.max(minZoom, nextZoom));
}


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
