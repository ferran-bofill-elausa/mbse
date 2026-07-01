from __future__ import annotations

"""HSM model viewer controller and HSM-specific session derivation."""

from copy import deepcopy
from typing import Any

from mbse.model.activity.activity_model import ActivityModel
from mbse.model.context.context_model import ContextModel
from mbse.model.hsm.hsm_model import HsmExternalTransitionRelation
from mbse.model.hsm.hsm_model import HsmGuardedTransitionBranchRelation
from mbse.model.hsm.hsm_model import HsmModel
from mbse.model.hsm.hsm_model import HsmRelatedState
from mbse.model.project.project_registry import ProjectRegistry
from mbse.runtime.hsm.hsm_runtime import HsmRuntimeExternalTransition
from mbse.runtime.hsm.hsm_runtime import HsmRuntimeGuardBranchTransition
from mbse.runtime.hsm.hsm_runtime import HsmRuntimeGuardCondition
from mbse.runtime.hsm.hsm_runtime import HsmRuntimeInitialTransition
from mbse.runtime.hsm.hsm_runtime import HsmRuntimeInternalTransition
from mbse.runtime.hsm.hsm_runtime import HsmRuntimeOnEntry
from mbse.runtime.hsm.hsm_runtime import HsmRuntimeOnExit
from mbse.runtime.hsm.hsm_runtime import HsmRuntimePendingExecutionTypeAlias
from mbse.runtime.hsm.hsm_runtime import HsmRuntimeTrace
from mbse.runtime.runtime import Runtime
from mbse.runtime.runtime import RuntimeStep
from mbse_web_viewer.render.activity.activity_render import ActivityRender
from mbse_web_viewer.render.hsm.hsm_render import HsmRender
from mbse_web_viewer.server.debugging.activity_breakpoints import activityBreakpointIdForStep
from mbse_web_viewer.server.debugging.activity_breakpoints import buildActivityBreakpointTargets
from mbse_web_viewer.server.debugging.hsm_breakpoints import breakpointKey
from mbse_web_viewer.server.debugging.hsm_breakpoints import buildHsmBreakpointTargets
from mbse_web_viewer.server.debugging.hsm_breakpoints import executableKey
from mbse_web_viewer.server.debugging.hsm_breakpoints import executableLabel
from mbse_web_viewer.server.debugging.hsm_breakpoints import hsmBreakpointIdForStep
from mbse_web_viewer.server.highlighting.activity_highlighting import buildActivityHighlight
from mbse_web_viewer.server.highlighting.hsm_highlighting import HsmHighlightingMixin
from mbse_web_viewer.server.session import ViewerBreakpointTarget
from mbse_web_viewer.server.session import ViewerFocus
from mbse_web_viewer.server.session import ViewerHighlight
from mbse_web_viewer.server.session import ViewerSession
from mbse_web_viewer.server.session import ViewerTrace
from mbse_web_viewer.server.model_catalog import ProjectModelCatalog


class HsmModelViewerController(HsmHighlightingMixin):
  """Own the rendered SVG, runtime instance, and derived viewer session."""

  def __init__(self, model: HsmModel, context: ContextModel | None = None) -> None:
    """Initialize the controller from one validated HSM model."""

    self._model = model
    self._context = context
    self._rendered_svg = HsmRender()
    self._rendered_svg.render(model)
    self._breakpoint_enabled_by_id: dict[str, bool] = {}
    self._breakpoint_targets = self._buildBreakpointTargets()
    self._breakpoint_target_ids = tuple(self._breakpoint_targets)
    self._breakpoint_order: list[str] = []
    self._runtime = self._buildRuntime()
    self._changed_variable_ids: tuple[str, ...] = ()
    self._advanceToNextExecutableStepForViewer()
    self._last_highlight = self._buildCurrentTraceHighlight()

  def getModelSvgText(self, model_id: str) -> str:
    """Return the rendered SVG document for one model id."""

    if model_id != self._model.getDocumentId():
      raise KeyError(f"Unknown model_id '{model_id}'.")
    return self._rendered_svg.getSvgText()

  def _getViewerModels(self) -> tuple[dict[str, object], ...]:
    """Return models available to the current viewer session."""

    return (
      {
        "model_id": self._model.getDocumentId(),
        "kind": "hsm",
        "svg_url": f"/artifacts/models/{self._model.getDocumentId()}/diagram.svg",
        "is_entrypoint": True,
      },
    )

  def _getActiveModelId(self) -> str:
    """Return the model id currently emphasized by this controller."""

    return self._runtime.getActiveFrame()["model_id"]

  def getSession(self) -> ViewerSession:
    """Return the current serialized browser session."""

    return ViewerSession(
      active_model_id=self._getActiveModelId(),
      models=self._getViewerModels(),
      enums=tuple(dict(enum) for enum in self._getContextEnums()),
      events=tuple(dict(event) for event in self._model.getEvents()),
      variables=tuple(dict(variable) for variable in self._getContextVariables()),
      state=self._runtime.getState(),
      variable_values={
        variable["name"]: self._runtime.getVariable(variable["name"])
        for variable in self._getContextVariables()
      },
      changed_variable_ids=self._changed_variable_ids,
      execution_log=self._serializeExecutionLog(),
      debugger=self._serializeDebuggerState(),
      highlight=self._last_highlight,
      highlights_by_model=self._buildModelHighlights(),
      focus=self._buildCurrentStateFocus(),
      last_trace=self._serializeLastTrace(),
      breakpoints=self._serializeBreakpoints(),
    )

  def reset(self) -> ViewerSession:
    """Reset the runtime and return the refreshed browser session."""

    self._runtime = self._buildRuntime()
    self._changed_variable_ids = ()
    self._advanceToNextExecutableStepForViewer()
    self._last_highlight = self._buildCurrentTraceHighlight()
    return self.getSession()

  def sendEvent(
    self,
    event_id: str,
    parameters: dict[str, Any] | None = None,
  ) -> ViewerSession:
    """Send one runtime event and return the refreshed browser session."""

    self._requireDeclaredEventId(event_id)
    initial_variable_values = self._snapshotVariableValues()
    should_run_to_breakpoint = (
      self._hasEnabledBreakpoints() and not self._runtime.isPaused()
    )
    if should_run_to_breakpoint:
      self._runtime.pause()
    self._runtime.sendEvent(event_id, parameters)
    if should_run_to_breakpoint:
      self._playUntilBreakpoint(skip_current_breakpoint=False)
    else:
      self._advanceToNextExecutableStepForViewer()
    self._changed_variable_ids = self._diffVariableIds(initial_variable_values)
    self._last_highlight = self._buildCurrentTraceHighlight()
    return self.getSession()

  def play(self) -> ViewerSession:
    """Run the runtime until the current pending work and queue are drained."""

    initial_variable_values = self._snapshotVariableValues()
    if self._hasEnabledBreakpoints():
      self._playUntilBreakpoint()
    else:
      self._runtime.play()
    self._changed_variable_ids = self._diffVariableIds(initial_variable_values)
    self._last_highlight = self._buildCurrentTraceHighlight()
    return self.getSession()

  def pause(self) -> ViewerSession:
    """Pause future automatic execution and return the refreshed session."""

    self._runtime.pause()
    self._last_highlight = self._buildCurrentTraceHighlight()
    return self.getSession()

  def stepInto(self) -> ViewerSession:
    """Advance the runtime to the next debugger step-in boundary."""

    initial_variable_values = self._snapshotVariableValues()
    self._runtime.stepInto()
    self._advanceToNextExecutableStepForViewer()
    self._changed_variable_ids = self._diffVariableIds(initial_variable_values)
    self._last_highlight = self._buildCurrentTraceHighlight()
    return self.getSession()

  def stepOver(self) -> ViewerSession:
    """Advance the runtime to the next debugger step-over boundary."""

    initial_variable_values = self._snapshotVariableValues()
    self._runtime.stepOver()
    self._advanceToNextExecutableStepForViewer()
    self._changed_variable_ids = self._diffVariableIds(initial_variable_values)
    self._last_highlight = self._buildCurrentTraceHighlight()
    return self.getSession()

  def stepOut(self) -> ViewerSession:
    """Advance the runtime until the current child frame returns."""

    initial_variable_values = self._snapshotVariableValues()
    self._runtime.stepOut()
    self._advanceToNextExecutableStepForViewer()
    self._changed_variable_ids = self._diffVariableIds(initial_variable_values)
    self._last_highlight = self._buildCurrentTraceHighlight()
    return self.getSession()

  def setVariable(self, variable_id: str, value: Any) -> ViewerSession:
    """Set one runtime variable and return the refreshed browser session."""

    self._requireDeclaredVariableId(variable_id)
    initial_variable_values = self._snapshotVariableValues()
    self._runtime.setVariable(variable_id, value)
    self._changed_variable_ids = self._diffVariableIds(initial_variable_values)
    self._last_highlight = self._buildCurrentTraceHighlight()
    return self.getSession()

  def toggleBreakpoint(self, breakpoint_id: str) -> ViewerSession:
    """Toggle one declared debugger breakpoint target."""

    if breakpoint_id not in self._breakpoint_targets:
      raise KeyError(f"Unknown breakpoint_id '{breakpoint_id}'.")
    if breakpoint_id in self._breakpoint_enabled_by_id:
      del self._breakpoint_enabled_by_id[breakpoint_id]
      self._breakpoint_order = [
        ordered_breakpoint_id
        for ordered_breakpoint_id in self._breakpoint_order
        if ordered_breakpoint_id != breakpoint_id
      ]
    else:
      self._breakpoint_enabled_by_id[breakpoint_id] = True
      self._breakpoint_order.append(breakpoint_id)
    self._last_highlight = self._buildCurrentTraceHighlight()
    return self.getSession()

  def removeBreakpoint(self, breakpoint_id: str) -> ViewerSession:
    """Remove one set debugger breakpoint."""

    if breakpoint_id not in self._breakpoint_targets:
      raise KeyError(f"Unknown breakpoint_id '{breakpoint_id}'.")
    self._breakpoint_enabled_by_id.pop(breakpoint_id, None)
    self._breakpoint_order = [
      ordered_breakpoint_id
      for ordered_breakpoint_id in self._breakpoint_order
      if ordered_breakpoint_id != breakpoint_id
    ]
    self._last_highlight = self._buildCurrentTraceHighlight()
    return self.getSession()

  def setBreakpointEnabled(
    self,
    breakpoint_id: str,
    enabled: bool,
  ) -> ViewerSession:
    """Enable or disable one existing debugger breakpoint."""

    if breakpoint_id not in self._breakpoint_targets:
      raise KeyError(f"Unknown breakpoint_id '{breakpoint_id}'.")
    if breakpoint_id not in self._breakpoint_enabled_by_id:
      raise KeyError(f"Breakpoint '{breakpoint_id}' is not set.")
    self._breakpoint_enabled_by_id[breakpoint_id] = enabled
    self._last_highlight = self._buildCurrentTraceHighlight()
    return self.getSession()

  def reorderBreakpoints(self, breakpoint_ids: list[str]) -> ViewerSession:
    """Persist one explicit order for the currently set debugger breakpoints."""

    ordered_breakpoint_ids: list[str] = []
    seen_breakpoint_ids: set[str] = set()
    for breakpoint_id in breakpoint_ids:
      if breakpoint_id not in self._breakpoint_targets:
        raise KeyError(f"Unknown breakpoint_id '{breakpoint_id}'.")
      if breakpoint_id not in self._breakpoint_enabled_by_id:
        raise ValueError(f"Breakpoint '{breakpoint_id}' is not set.")
      if breakpoint_id in seen_breakpoint_ids:
        raise ValueError(f"Breakpoint '{breakpoint_id}' was provided more than once.")
      seen_breakpoint_ids.add(breakpoint_id)
      ordered_breakpoint_ids.append(breakpoint_id)

    current_set_breakpoint_ids = set(self._breakpoint_enabled_by_id)
    if seen_breakpoint_ids != current_set_breakpoint_ids:
      raise ValueError(
        "Breakpoint reorder payload must include every set breakpoint exactly once."
      )

    self._breakpoint_order = ordered_breakpoint_ids
    self._last_highlight = self._buildCurrentTraceHighlight()
    return self.getSession()

  def _buildRuntime(self) -> Runtime:
    """Create and initialize one fresh runtime from the current model."""

    runtime = Runtime()
    runtime.initModel(self._model, self._context)
    return runtime

  def _getWrappedNextStep(self) -> RuntimeStep | None:
    """Return the pending top-level runtime step with active-frame metadata."""

    return self._runtime.getNextStep()

  def _getNextStep(self) -> HsmRuntimePendingExecutionTypeAlias | None:
    """Return the native pending HSM step when the active frame is an HSM."""

    wrapped_step = self._getWrappedNextStep()
    if wrapped_step is None:
      return None
    if wrapped_step["runtime"] != "hsm":
      return None
    return wrapped_step["step"]

  def _getCallStackStep(self) -> HsmRuntimePendingExecutionTypeAlias | None:
    """Return this HSM's current step from the runtime call stack."""

    call_stack = self._runtime.getCallStack()
    while call_stack is not None:
      if (
        call_stack["runtime"] == "hsm"
        and call_stack["model_id"] == self._model.getDocumentId()
      ):
        return call_stack["step"]
      call_stack = call_stack["nested"]
    return None

  def _getExecutionLog(self) -> list[HsmRuntimeTrace]:
    """Return native HSM traces from the top-level runtime."""

    return [
      wrapped_trace["trace"]
      for wrapped_trace in self._runtime.getExecutionLog()
      if (
        wrapped_trace["runtime"] == "hsm"
        and wrapped_trace["model_id"] == self._model.getDocumentId()
      )
    ]

  def _getContextEnums(self) -> list[dict[str, Any]]:
    """Return context enum declarations available to the viewer."""

    return [] if self._context is None else self._context.getEnums()

  def _getContextVariables(self) -> list[dict[str, Any]]:
    """Return context variable declarations available to the runtime."""

    return [] if self._context is None else self._context.getVariables()

  def _snapshotVariableValues(self) -> dict[str, Any]:
    """Return a detached snapshot of current runtime variable values."""

    return {
      variable["name"]: deepcopy(self._runtime.getVariable(variable["name"]))
      for variable in self._getContextVariables()
    }

  def _diffVariableIds(self, initial_variable_values: dict[str, Any]) -> tuple[str, ...]:
    """Return variable ids whose current value differs from one snapshot."""

    return tuple(
      variable["name"]
      for variable in self._getContextVariables()
      if (
        self._runtime.getVariable(variable["name"])
        != initial_variable_values[variable["name"]]
      )
    )

  def _playUntilBreakpoint(self, *, skip_current_breakpoint: bool = True) -> None:
    """Run pending work until idle or before the next active breakpoint step."""

    skipped_breakpoint_id = (
      self._getPendingBreakpointId() if skip_current_breakpoint else None
    )

    while True:
      self._advanceToNextExecutableStepForViewer(
        stop_on_breakpoint=True,
        skipped_breakpoint_id=skipped_breakpoint_id,
      )
      wrapped_step = self._getWrappedNextStep()
      if wrapped_step is None:
        if not self._runtime.getEventQueue():
          self._runtime.play()
          return
        self._runtime.stepInto()
        skipped_breakpoint_id = None
        continue

      breakpoint_id = self._breakpointIdForWrappedStep(wrapped_step)
      if (
        breakpoint_id is not None
        and self._isBreakpointEnabled(breakpoint_id)
        and breakpoint_id != skipped_breakpoint_id
      ):
        self._runtime.pause()
        return

      self._runtime.stepInto()
      skipped_breakpoint_id = None

  def _advanceToNextExecutableStepForViewer(
    self,
    *,
    stop_on_breakpoint: bool = True,
    skipped_breakpoint_id: str | None = None,
  ) -> None:
    """Consume pending entries that should be shown only as completed path."""

    while True:
      next_step = self._getNextStep()
      if next_step is None:
        return
      breakpoint_id = self._breakpointIdForStep(next_step)
      if (
        stop_on_breakpoint
        and breakpoint_id is not None
        and self._isBreakpointEnabled(breakpoint_id)
        and breakpoint_id != skipped_breakpoint_id
      ):
        self._runtime.pause()
        return
      if next_step["kind"] == "change_active_state":
        self._runtime.stepInto()
        continue
      if self._isNonExecutableTransitionStep(next_step):
        self._runtime.stepInto()
        continue
      return

  def _isNonExecutableTransitionStep(
    self,
    step: HsmRuntimePendingExecutionTypeAlias,
  ) -> bool:
    """Return whether one pending transition has no executable to execute."""

    return (
      step["kind"] in {
        "external_transition",
        "guarded_transition",
        "guard_branch_transition",
        "initial_transition",
        "internal_transition",
      }
      and step["activity"] is None
    )

  def _serializeLastTrace(self) -> ViewerTrace:
    """Serialize the latest runtime trace for lightweight browser inspection."""

    execution_log = self._getExecutionLog()
    if not execution_log:
      return ViewerTrace(event_id=None, entries=[])

    trace = execution_log[-1]
    return ViewerTrace(
      event_id=trace["event"]["event_id"],
      entries=[dict(entry) for entry in trace["entries"]],
    )

  def _serializeExecutionLog(self) -> list[dict[str, object]]:
    """Serialize the full runtime execution log without viewer formatting."""

    return [
      {
        "event": dict(trace["event"]),
        "entries": [dict(entry) for entry in trace["entries"]],
      }
      for trace in self._getExecutionLog()
    ]

  def _serializeDebuggerState(self) -> dict[str, object]:
    """Serialize the minimal debugger state needed by the browser UI."""

    queued_events = [dict(event) for event in self._runtime.getEventQueue()]
    has_pending_execution = self._runtime.hasPendingExecution()
    current_event = None
    execution_log = self._getExecutionLog()
    if has_pending_execution and execution_log:
      current_event = dict(execution_log[-1]["event"])
    elif queued_events:
      current_event = dict(queued_events[0])
    completed_traces = execution_log
    if has_pending_execution and completed_traces:
      completed_traces = completed_traces[:-1]
    return {
      "is_paused": self._runtime.isPaused(),
      "current_event": current_event,
      "queued_events": queued_events,
      "event_history": [
        dict(trace["event"])
        for trace in completed_traces
        if trace["event"]["event_id"] is not None
      ],
      "has_pending_execution": has_pending_execution,
      "can_step": has_pending_execution or bool(queued_events),
    }

  def _serializeBreakpoints(self) -> tuple[ViewerBreakpointTarget, ...]:
    """Serialize all available breakpoint targets with current active state."""

    return tuple(
      ViewerBreakpointTarget(
        id=target.id,
        model_id=target.model_id,
        label=target.label,
        svg_ids=target.svg_ids,
        text_ids=target.text_ids,
        is_set=target.id in self._breakpoint_enabled_by_id,
        enabled=self._isBreakpointEnabled(target.id),
      )
      for target in (
        self._breakpoint_targets[breakpoint_id]
        for breakpoint_id in self._iterSerializedBreakpointIds()
      )
    )

  def _iterSerializedBreakpointIds(self) -> tuple[str, ...]:
    """Return breakpoint ids ordered for viewer serialization."""

    ordered_set_breakpoint_ids = [
      breakpoint_id
      for breakpoint_id in self._breakpoint_order
      if breakpoint_id in self._breakpoint_enabled_by_id
    ]
    remaining_set_breakpoint_ids = [
      breakpoint_id
      for breakpoint_id in self._breakpoint_target_ids
      if (
        breakpoint_id in self._breakpoint_enabled_by_id
        and breakpoint_id not in ordered_set_breakpoint_ids
      )
    ]
    unset_breakpoint_ids = [
      breakpoint_id
      for breakpoint_id in self._breakpoint_target_ids
      if breakpoint_id not in self._breakpoint_enabled_by_id
    ]
    return tuple(
      ordered_set_breakpoint_ids + remaining_set_breakpoint_ids + unset_breakpoint_ids
    )

  def _hasEnabledBreakpoints(self) -> bool:
    """Return whether any set breakpoint is currently enabled."""

    return any(self._breakpoint_enabled_by_id.values())

  def _isBreakpointEnabled(self, breakpoint_id: str) -> bool:
    """Return whether one breakpoint is set and enabled."""

    return self._breakpoint_enabled_by_id.get(breakpoint_id, False)

  def _getPendingBreakpointId(self) -> str | None:
    """Return the breakpoint id for the current pending step, if any."""

    wrapped_step = self._getWrappedNextStep()
    if wrapped_step is None:
      return None
    return self._breakpointIdForWrappedStep(wrapped_step)

  def _breakpointIdForWrappedStep(self, wrapped_step: RuntimeStep) -> str | None:
    """Return breakpoint id for one active top-level runtime step."""

    if wrapped_step["runtime"] == "hsm":
      return self._breakpointIdForStep(wrapped_step["step"])
    if wrapped_step["runtime"] == "activity":
      return activityBreakpointIdForStep(
        wrapped_step["model_id"],
        wrapped_step["step"],
      )
    return None

  def _breakpointIdForStep(
    self,
    step: HsmRuntimePendingExecutionTypeAlias,
  ) -> str | None:
    """Return the semantic breakpoint id matching one pending runtime step."""

    return hsmBreakpointIdForStep(step, event_id=self._getPendingEventId())

  def _breakpointKey(self, *parts: object) -> str:
    """Return one stable serialized breakpoint key."""

    return breakpointKey(*parts)

  def _executableKey(self, activity: dict[str, str]) -> str:
    """Return one stable executable key matching render-layer text targeting."""

    return executableKey(activity)

  def _executableLabel(self, activity: dict[str, str]) -> str:
    """Return one readable executable label."""

    return executableLabel(activity)

  def _buildBreakpointTargets(self) -> dict[str, ViewerBreakpointTarget]:
    """Build semantic debugger breakpoint targets backed by rendered SVG text ids."""

    return buildHsmBreakpointTargets(
      self._model,
      self._rendered_svg,
      is_set_by_id=self._breakpoint_enabled_by_id,
    )

  def _requireDeclaredEventId(self, event_id: str) -> None:
    """Reject one event id that is not declared by the current model."""

    self._model.getEventById(event_id)

  def _requireDeclaredVariableId(self, variable_id: str) -> None:
    """Reject one variable id that is not declared by the current context."""

    if self._context is None:
      raise KeyError(f"Unknown variable_id '{variable_id}'.")
    self._context.getVariableByName(variable_id)


class ProjectViewerController(HsmModelViewerController):
  """Viewer controller backed by a multi-model project registry."""

  def __init__(self, registry: ProjectRegistry) -> None:
    """Initialize the controller from one loaded project registry."""

    entrypoint_model = registry.getEntrypointModel()
    if not isinstance(entrypoint_model, HsmModel):
      raise TypeError("Project viewer requires an HSM entrypoint model.")

    self._registry = registry
    self._model_catalog = ProjectModelCatalog(registry)
    super().__init__(entrypoint_model, registry.getContext())

  def getModelSvgText(self, model_id: str) -> str:
    """Return the rendered SVG document for one project model id."""

    return self._model_catalog.getModelSvgText(model_id)

  def _getViewerModels(self) -> tuple[dict[str, object], ...]:
    """Return executable project models available to the viewer session."""

    return self._model_catalog.getViewerModels()

  def _getActiveModelId(self) -> str:
    """Return the model id currently emphasized by this controller."""

    return self._runtime.getActiveFrame()["model_id"]

  def _buildBreakpointTargets(self) -> dict[str, ViewerBreakpointTarget]:
    """Build debugger breakpoint targets for every executable project model."""

    targets = super()._buildBreakpointTargets()
    for model in self._registry.iterExecutableModels():
      model_id = model.getDocumentId()
      rendered = self._model_catalog.getRenderedModels().get(model_id)
      if not isinstance(model, ActivityModel) or not isinstance(rendered, ActivityRender):
        continue
      targets.update(
        buildActivityBreakpointTargets(
          model,
          rendered,
          is_set_by_id=self._breakpoint_enabled_by_id,
        )
      )
    return targets

  def _buildRuntime(self) -> Runtime:
    """Create and initialize one fresh runtime from the project registry."""

    runtime = Runtime()
    runtime.init(self._registry)
    return runtime

  def _buildModelHighlights(self) -> dict[str, ViewerHighlight]:
    """Return current highlights for every rendered project model."""

    highlights = {self._model.getDocumentId(): self._last_highlight}
    for model_id, rendered in self._model_catalog.getRenderedModels().items():
      if model_id == self._model.getDocumentId():
        continue
      if isinstance(rendered, ActivityRender):
        highlights[model_id] = buildActivityHighlight(self._runtime, model_id, rendered)
    return highlights
