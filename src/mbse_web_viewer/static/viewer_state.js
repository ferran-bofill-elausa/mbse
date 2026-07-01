export const DEFAULT_ZOOM = 1;
export const MIN_ZOOM = 0.5;
export const MAX_ZOOM = 2;
export const ZOOM_INTENSITY = 0.0015;
export const DEFAULT_SIDEBAR_WIDTH_PX = 288;
export const ACTIVE_STATE_CLASS = "is-active-state";
export const ACTIVE_TRANSITION_CLASS = "is-active-transition";
export const ACTIVE_TEXT_CLASS = "is-active-text";
export const CURRENT_STEP_CLASS = "is-current-step";
export const CURRENT_STEP_TEXT_CLASS = "is-current-step-text";
export const FOCUS_RELATED_CLASS = "is-focus-related";
export const FOCUS_DIMMED_CLASS = "is-focus-dimmed";
export const PAN_ACTIVE_CLASS = "is-pan-active";
export const BREAKPOINT_ACTIVE_CLASS = "is-breakpoint-active";
export const BREAKPOINT_SET_CLASS = "is-breakpoint-set";
export const BREAKPOINT_TARGET_CLASS = "is-breakpoint-target";
export const BREAKPOINT_MARKER_CLASS = "breakpoint-marker";
export const BREAKPOINT_LIST_DRAGGING_CLASS = "is-breakpoint-list-dragging";
export const BREAKPOINT_DRAGGING_CLASS = "is-breakpoint-dragging";
export const BREAKPOINT_DROP_TARGET_CLASS = "is-breakpoint-drop-target";
export const SVG_NAMESPACE = "http://www.w3.org/2000/svg";
export const BREAKPOINT_CENTER_SUPPRESSION_MS = 250;

export const viewerState = {
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
  sessionModels: [],
  activeModelId: null,
  displayedModelId: null,
  modelViewStateById: {},
  sessionEnums: [],
  sessionVariables: [],
  changedVariableIds: [],
  breakpointTargets: [],
  highlightsByModel: {},
  isPaused: true,
  hasPendingExecution: false,
  breakpointDragState: null,
  suppressBreakpointCenterId: null,
  suppressBreakpointCenterUntilMs: 0,
  eventDraftEventId: null,
  eventDraftParameters: null,
  fitBaseline: {
    zoomScale: DEFAULT_ZOOM,
    scrollLeft: 0,
    scrollTop: 0,
  },
};
