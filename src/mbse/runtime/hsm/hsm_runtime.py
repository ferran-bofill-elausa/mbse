from __future__ import annotations

"""HSM runtime API and internal implementation contract."""

from copy import deepcopy
import importlib
from types import SimpleNamespace
from typing import Any
from typing import Literal
from typing import TypeAlias
from typing import TypedDict

from mbse.model.hsm.hsm_model import HsmModel


class HsmRuntimeEvent(TypedDict):
  """Queued runtime event waiting to be planned."""

  event_id: str | None
  parameters: dict[str, Any]


class HsmRuntimeCallableRef(TypedDict):
  """Reference to one Python callable declared by the model."""

  module: str
  name: str


class HsmRuntimeInitialTransition(TypedDict):
  """Trace entry for one initial transition."""

  kind: Literal["initial_transition"]
  source_state_id: str | None
  source_state_label: str | None
  target_state_id: str
  target_state_label: str


class HsmRuntimeExternalTransition(TypedDict):
  """Trace entry for one external transition."""

  kind: Literal["external_transition"]
  source_state_id: str
  source_state_label: str
  target_state_id: str
  target_state_label: str


class HsmRuntimeInternalTransition(TypedDict):
  """Trace entry for one internal transition."""

  kind: Literal["internal_transition"]
  source_state_id: str
  source_state_label: str


class HsmRuntimeGuardCondition(TypedDict):
  """Trace entry for one resolved guard condition."""

  kind: Literal["guard_condition"]
  source_state_id: str
  source_state_label: str
  guard_activity: HsmRuntimeCallableRef
  result: bool
  target_state_id: str
  target_state_label: str


class HsmRuntimeActivity(TypedDict):
  """Trace entry for one transition activity execution."""

  kind: Literal["activity"]
  source_state_id: str
  source_state_label: str
  activity_owner: Literal["internal_transition", "external_transition", "guard_branch"]
  activity: HsmRuntimeCallableRef


class HsmRuntimeOnEntry(TypedDict):
  """Trace entry for one on_entry hook execution."""

  kind: Literal["on_entry"]
  source_state_id: str
  source_state_label: str
  activity: HsmRuntimeCallableRef


class HsmRuntimeOnInitial(TypedDict):
  """Trace entry for one on_initial hook execution."""

  kind: Literal["on_initial"]
  source_state_id: str
  source_state_label: str
  activity: HsmRuntimeCallableRef


class HsmRuntimeOnExit(TypedDict):
  """Trace entry for one on_exit hook execution."""

  kind: Literal["on_exit"]
  source_state_id: str
  source_state_label: str
  activity: HsmRuntimeCallableRef


HsmRuntimeTraceTypeAlias: TypeAlias = (
  HsmRuntimeInitialTransition |
  HsmRuntimeExternalTransition |
  HsmRuntimeInternalTransition |
  HsmRuntimeGuardCondition |
  HsmRuntimeActivity |
  HsmRuntimeOnEntry |
  HsmRuntimeOnInitial |
  HsmRuntimeOnExit
)


class HsmRuntimePendingGuardCondition(TypedDict):
  """Pending guard decision with both branches precalculated.

  This node exists only in pending_execution. Once the guard is executed, the
  chosen branch replaces this node and the execution log receives one resolved
  HsmRuntimeGuardCondition entry.
  """

  kind: Literal["pending_guard_condition"]
  source_state_id: str
  source_state_label: str
  guard_activity: HsmRuntimeCallableRef
  true_target_state_id: str
  true_target_state_label: str
  true_branch: list[HsmRuntimePendingExecutionTypeAlias]
  false_target_state_id: str
  false_target_state_label: str
  false_branch: list[HsmRuntimePendingExecutionTypeAlias]


HsmRuntimePendingExecutionTypeAlias: TypeAlias = (
  HsmRuntimeInitialTransition |
  HsmRuntimeExternalTransition |
  HsmRuntimeInternalTransition |
  HsmRuntimeActivity |
  HsmRuntimeOnEntry |
  HsmRuntimeOnInitial |
  HsmRuntimeOnExit |
  HsmRuntimePendingGuardCondition
)


class HsmRuntimeTrace(TypedDict):
  """One runtime trace caused by exactly one triggering event.

  The trace is created during planning and filled incrementally as execution proceeds.
  """

  event: HsmRuntimeEvent
  entries: list[HsmRuntimeTraceTypeAlias]


class HsmRuntimePendingTrace(TypedDict):
  """One full pending trace caused by exactly one triggering event."""

  event: HsmRuntimeEvent
  entries: list[HsmRuntimePendingExecutionTypeAlias]


class HsmRuntime:
  """Mutable HSM runtime instance."""

  def __init__(self) -> None:
    """HsmRuntime initialization."""

    self.model: HsmModel | None = None
    self.mode = "rtc"
    self.current_state_id: str | None = None
    self.variables: dict[str, Any] = {}
    self.execution_log: list[HsmRuntimeTrace] = []
    self.pending_execution: HsmRuntimePendingTrace | None = None
    self.event_queue: list[HsmRuntimeEvent] = []

  def init(self, model: HsmModel, mode: str = "rtc") -> None:
    """Initialize the runtime from a loaded HSM model."""

    if mode not in {"rtc", "step"}:
      raise ValueError("Runtime mode must be 'rtc' or 'step'.")

    self.model = model
    self.mode = mode
    self.current_state_id = None
    # Copy authored defaults so runtime mutation never aliases the model payload.
    self.variables = {
      variable["name"]: deepcopy(variable["default_value"])
      for variable in model.getVariables()
    }
    self.execution_log = []
    self.pending_execution = None
    self.event_queue = []

    self._planInit()
    if self.mode == "rtc":
      while self.step():
        pass

  def setMode(self, mode: str) -> None:
    """Change the runtime execution mode."""

    if mode not in {"rtc", "step"}:
      raise ValueError("Runtime mode must be 'rtc' or 'step'.")

    self.mode = mode

  def sendEvent(
    self,
    event_id: str,
    parameters: dict[str, Any] | None = None,
  ) -> bool:
    """Send one event to the runtime."""

    self._pushEvent(event_id, parameters)

    if self.pending_execution is None:
      next_event = self._popEvent()
      self._planEvent(next_event)

    if self.mode == "rtc":
      while self.step():
        pass

    return True

  def step(self) -> bool:
    """Execute one pending activity in step mode."""

    pending_execution = self.pending_execution
    if pending_execution is None:
      if not self.event_queue:
        return False

      # Only plan the next event when no trace is currently in progress.
      next_event = self._popEvent()
      if not self._planEvent(next_event):
        return self.step()

      pending_execution = self.pending_execution
      if pending_execution is None:
        return False

    while pending_execution["entries"]:
      entry = pending_execution["entries"].pop(0)
      kind = entry["kind"]

      if kind == "pending_guard_condition":
        # Resolve the decision now and splice the chosen branch back into pending.
        guard_result = self._callGuard(
          entry["guard_activity"],
          pending_execution["event"],
        )
        branch_entries = entry["true_branch"] if guard_result else entry["false_branch"]
        target_state_id = (
          entry["true_target_state_id"]
          if guard_result
          else entry["false_target_state_id"]
        )
        target_state_label = (
          entry["true_target_state_label"]
          if guard_result
          else entry["false_target_state_label"]
        )

        self.execution_log[-1]["entries"].append(
          {
            "kind": "guard_condition",
            "source_state_id": entry["source_state_id"],
            "source_state_label": entry["source_state_label"],
            "guard_activity": entry["guard_activity"],
            "result": guard_result,
            "target_state_id": target_state_id,
            "target_state_label": target_state_label,
          }
        )
        pending_execution["entries"][0:0] = branch_entries
        return True

      if kind in {"activity", "on_entry", "on_initial", "on_exit"}:
        # Hook and activity entries are the only steps with user code side effects.
        self._callActivity(entry["activity"], pending_execution["event"])
        self.execution_log[-1]["entries"].append(entry)
        return True

      # Structural entries still belong to the log even though they do not execute code.
      self.execution_log[-1]["entries"].append(entry)

    final_state_id = self._getTraceFinalStateId(self.execution_log[-1])
    if final_state_id is not None:
      self.current_state_id = final_state_id

    self.pending_execution = None
    return self.step()

  def setState(self, state_id: str) -> None:
    """Force the current active state."""

    raise NotImplementedError

  def getState(self) -> dict[str, str | None]:
    """Get the current active state id and label."""

    state_id = self.current_state_id
    if state_id is None:
      return {"id": None, "label": None}

    for state in self._requireModel().iterStates():
      if state["id"] == state_id:
        return {"id": state_id, "label": state["label"]}

    return {"id": state_id, "label": None}

  def setVariable(self, name: str, value: Any) -> None:
    """Set one runtime variable value."""

    self.variables[name] = value

  def getVariable(self, name: str) -> Any:
    """Get one runtime variable value."""

    return self.variables[name]

  def getExecutionLog(self) -> list[HsmRuntimeTrace]:
    """Get the accumulated runtime execution log.

    The log is filled incrementally while execution proceeds.
    """

    return self.execution_log

  def _pushEvent(
    self,
    event_id: str,
    parameters: dict[str, Any] | None,
  ) -> None:
    """Push one user event to the runtime FIFO queue."""

    self.event_queue.append(
      {
        "event_id": event_id,
        "parameters": parameters or {},
      }
    )

  def _popEvent(self) -> HsmRuntimeEvent:
    """Pop and return the next user event from the runtime FIFO queue."""

    return self.event_queue.pop(0)

  def _buildTransitionBranch(
    self,
    current_state_id: str,
    source_state_id: str,
    target_state_id: str,
    external_transition: dict[str, Any],
    branch_activities: list[HsmRuntimeCallableRef],
  ) -> list[HsmRuntimePendingExecutionTypeAlias]:
    """Build the deterministic pending entries for one chosen transition branch."""

    entries: list[HsmRuntimePendingExecutionTypeAlias] = []
    model = self._requireModel()

    entries.append(
      {
        "kind": "external_transition",
        "source_state_id": source_state_id,
        "source_state_label": model.getStateLabel(source_state_id),
        "target_state_id": target_state_id,
        "target_state_label": model.getStateLabel(target_state_id),
      }
    )

    for activity in external_transition.get("activities", []):
      entries.append(
        {
          "kind": "activity",
          "source_state_id": source_state_id,
          "source_state_label": model.getStateLabel(source_state_id),
          "activity_owner": "external_transition",
          "activity": activity,
        }
      )

    for activity in branch_activities:
      entries.append(
        {
          "kind": "activity",
          "source_state_id": source_state_id,
          "source_state_label": model.getStateLabel(source_state_id),
          "activity_owner": "guard_branch",
          "activity": activity,
        }
      )

    # Exit from the active leaf up to the state that actually owns the transition.
    aux_state_id = current_state_id
    while aux_state_id != source_state_id:
      for activity in model.getStateHooks(aux_state_id).get("on_exit", []):
        entries.append(
          {
            "kind": "on_exit",
            "source_state_id": aux_state_id,
            "source_state_label": model.getStateLabel(aux_state_id),
            "activity": activity,
          }
        )
      aux_state_id = model.getParentStateId(aux_state_id)

    exit_path, entry_path = self._getTransitionPath(source_state_id, target_state_id)

    # Exit and entry hooks follow the same transition path computed below.
    for exit_state_id in exit_path:
      for activity in model.getStateHooks(exit_state_id).get("on_exit", []):
        entries.append(
          {
            "kind": "on_exit",
            "source_state_id": exit_state_id,
            "source_state_label": model.getStateLabel(exit_state_id),
            "activity": activity,
          }
        )

    for entry_state_id in reversed(entry_path):
      for activity in model.getStateHooks(entry_state_id).get("on_entry", []):
        entries.append(
          {
            "kind": "on_entry",
            "source_state_id": entry_state_id,
            "source_state_label": model.getStateLabel(entry_state_id),
            "activity": activity,
          }
        )

    current_target_state_id = target_state_id

    # Once the target is entered, keep descending through local initials.
    while model.hasStateInitialTransition(current_target_state_id):
      for activity in model.getStateHooks(current_target_state_id).get("on_initial", []):
        entries.append(
          {
            "kind": "on_initial",
            "source_state_id": current_target_state_id,
            "source_state_label": model.getStateLabel(current_target_state_id),
            "activity": activity,
          }
        )

      next_target_state_id = model.getStateInitialTargetId(current_target_state_id)
      entries.append(
        {
          "kind": "initial_transition",
          "source_state_id": current_target_state_id,
          "source_state_label": model.getStateLabel(current_target_state_id),
          "target_state_id": next_target_state_id,
          "target_state_label": model.getStateLabel(next_target_state_id),
        }
      )

      nested_entry_path = [next_target_state_id]
      parent_state_id = model.getParentStateId(next_target_state_id)
      while parent_state_id is not None and parent_state_id != current_target_state_id:
        nested_entry_path.append(parent_state_id)
        parent_state_id = model.getParentStateId(parent_state_id)

      for entry_state_id in reversed(nested_entry_path):
        for activity in model.getStateHooks(entry_state_id).get("on_entry", []):
          entries.append(
            {
              "kind": "on_entry",
              "source_state_id": entry_state_id,
              "source_state_label": model.getStateLabel(entry_state_id),
              "activity": activity,
            }
          )

      current_target_state_id = next_target_state_id

    return entries

  def _planInit(self) -> None:
    """Plan root initialization plus full nested initial descent."""

    model = self._requireModel()
    event: HsmRuntimeEvent = {"event_id": None, "parameters": {}}
    entries: list[HsmRuntimePendingExecutionTypeAlias] = []

    target_state_id = model.getRootInitialTargetId()
    entries.append(
      {
        "kind": "initial_transition",
        "source_state_id": None,
        "source_state_label": None,
        "target_state_id": target_state_id,
        "target_state_label": model.getStateLabel(target_state_id),
      }
    )

    entry_path = [target_state_id]
    # Build the entry path upward, then replay it downward during initialization.
    parent_state_id = model.getParentStateId(target_state_id)
    while parent_state_id is not None:
      entry_path.append(parent_state_id)
      parent_state_id = model.getParentStateId(parent_state_id)

    for state_id in reversed(entry_path):
      for activity in model.getStateHooks(state_id).get("on_entry", []):
        entries.append(
          {
            "kind": "on_entry",
            "source_state_id": state_id,
            "source_state_label": model.getStateLabel(state_id),
            "activity": activity,
          }
        )

    current_state_id = target_state_id
    # Repeat local initial descent until reaching the final active leaf.
    while model.hasStateInitialTransition(current_state_id):
      for activity in model.getStateHooks(current_state_id).get("on_initial", []):
        entries.append(
          {
            "kind": "on_initial",
            "source_state_id": current_state_id,
            "source_state_label": model.getStateLabel(current_state_id),
            "activity": activity,
          }
        )

      target_state_id = model.getStateInitialTargetId(current_state_id)
      entries.append(
        {
          "kind": "initial_transition",
          "source_state_id": current_state_id,
          "source_state_label": model.getStateLabel(current_state_id),
          "target_state_id": target_state_id,
          "target_state_label": model.getStateLabel(target_state_id),
        }
      )

      entry_path = [target_state_id]
      parent_state_id = model.getParentStateId(target_state_id)
      while parent_state_id is not None and parent_state_id != current_state_id:
        entry_path.append(parent_state_id)
        parent_state_id = model.getParentStateId(parent_state_id)

      for state_id in reversed(entry_path):
        for activity in model.getStateHooks(state_id).get("on_entry", []):
          entries.append(
            {
              "kind": "on_entry",
              "source_state_id": state_id,
              "source_state_label": model.getStateLabel(state_id),
              "activity": activity,
            }
          )

      current_state_id = target_state_id

    self.pending_execution = {"event": event, "entries": entries}
    # Prepare the log trace now so step() can append executed entries in order.
    self.execution_log.append({"event": event, "entries": []})

  def _planEvent(self, event: HsmRuntimeEvent) -> bool:
    """Plan one event from the active leaf using the runtime transition rules."""

    current_state_id = self.current_state_id
    if current_state_id is None:
      return False

    model = self._requireModel()
    entries: list[HsmRuntimePendingExecutionTypeAlias] = []
    state_id: str | None = current_state_id

    # Bubble from the active leaf to the root until one state resolves the event.
    while state_id is not None:
      internal_transition = model.findInternalTransition(state_id, event["event_id"])
      if internal_transition is not None:
        entries.append(
          {
            "kind": "internal_transition",
            "source_state_id": state_id,
            "source_state_label": model.getStateLabel(state_id),
          }
        )
        for activity in internal_transition.get("activities", []):
          entries.append(
            {
              "kind": "activity",
              "source_state_id": state_id,
              "source_state_label": model.getStateLabel(state_id),
              "activity_owner": "internal_transition",
              "activity": activity,
            }
          )

        self.pending_execution = {"event": event, "entries": entries}
        # Prepare the log trace now so step() can append executed entries in order.
        self.execution_log.append({"event": event, "entries": []})
        return True

      external_transition = model.findExternalTransition(state_id, event["event_id"])
      if external_transition is None:
        state_id = model.getParentStateId(state_id)
        continue

      source_state_id = state_id
      target_state_id = external_transition.get("target_id")
      guard_condition = external_transition.get("guard_condition")

      if guard_condition is not None:
        true_branch = guard_condition["true_branch"]
        false_branch = guard_condition["false_branch"]
        # The guard node keeps both authored outcomes so step() can choose later.
        entries.append(
          {
            "kind": "pending_guard_condition",
            "source_state_id": source_state_id,
            "source_state_label": model.getStateLabel(source_state_id),
            "guard_activity": guard_condition["guard_activity"],
            "true_target_state_id": true_branch["target_id"],
            "true_target_state_label": model.getStateLabel(true_branch["target_id"]),
            "true_branch": self._buildTransitionBranch(
              current_state_id,
              source_state_id,
              true_branch["target_id"],
              external_transition,
              true_branch.get("activities", []),
            ),
            "false_target_state_id": false_branch["target_id"],
            "false_target_state_label": model.getStateLabel(false_branch["target_id"]),
            "false_branch": self._buildTransitionBranch(
              current_state_id,
              source_state_id,
              false_branch["target_id"],
              external_transition,
              false_branch.get("activities", []),
            ),
          }
        )

        self.pending_execution = {"event": event, "entries": entries}
        # Prepare the log trace now so step() can append executed entries in order.
        self.execution_log.append({"event": event, "entries": []})
        return True

      if target_state_id is None:
        state_id = model.getParentStateId(state_id)
        continue

      entries.extend(
        self._buildTransitionBranch(
          current_state_id,
          source_state_id,
          target_state_id,
          external_transition,
          [],
        )
      )

      self.pending_execution = {"event": event, "entries": entries}
      # Prepare the log trace now so step() can append executed entries in order.
      self.execution_log.append({"event": event, "entries": []})
      return True

    # Unhandled events still open an empty trace so the log preserves event reception order.
    self.execution_log.append({"event": event, "entries": []})
    return False

  def _getTransitionPath(
    self,
    source_state_id: str,
    target_state_id: str,
  ) -> tuple[list[str], list[str]]:
    """Compute the exit path and entry path for one external transition."""

    model = self._requireModel()
    t_found = False
    entry_path: list[str] = []
    exit_path: list[str] = []

    # Case 1: self transition.
    if source_state_id == target_state_id:
      exit_path = [target_state_id]
      entry_path = [target_state_id]
      t_found = True

    # Case 2: ancestor -> descendant.
    if not t_found:
      entry_path = [target_state_id]
      parent_state_id = model.getParentStateId(entry_path[0])
      while parent_state_id is not None:
        entry_path.append(parent_state_id)

        if parent_state_id == source_state_id:
          exit_path = []
          entry_path.pop()
          t_found = True
          break

        parent_state_id = model.getParentStateId(parent_state_id)

    # Case 3: descendant -> ancestor.
    if not t_found:
      exit_path = [source_state_id]
      parent_state_id = model.getParentStateId(exit_path[0])
      while parent_state_id is not None:
        if parent_state_id == target_state_id:
          entry_path = []
          t_found = True
          break

        exit_path.append(parent_state_id)
        parent_state_id = model.getParentStateId(parent_state_id)

    # Case 4: branch -> branch via lowest common ancestor.
    if not t_found:
      for exit_index, exit_state_id in enumerate(exit_path):
        if exit_state_id in entry_path:
          entry_index = entry_path.index(exit_state_id)
          exit_path = exit_path[:exit_index]
          entry_path = entry_path[:entry_index]
          t_found = True
          break

      # Top-level branch-to-branch transitions share only the implicit root.
      if not t_found:
        t_found = True

    if not t_found:
      raise ValueError(
        f"Unable to compute transition path from '{source_state_id}' to '{target_state_id}'."
      )

    return exit_path, entry_path

  def _getTraceFinalStateId(self, trace: HsmRuntimeTrace) -> str | None:
    """Return the final active state id implied by one completed trace."""

    final_state_id: str | None = None
    # The last transition target in the trace is the final active state.
    for entry in trace["entries"]:
      if entry["kind"] in {"initial_transition", "external_transition"}:
        final_state_id = entry["target_state_id"]

    return final_state_id

  def _callActivity(
    self,
    callable_ref: dict[str, str],
    event: HsmRuntimeEvent | None,
  ) -> Any:
    """Resolve and execute one activity callable."""

    return self._callRuntimeCallable(callable_ref, event)

  def _callGuard(
    self,
    callable_ref: dict[str, str],
    event: HsmRuntimeEvent,
  ) -> bool:
    """Resolve and execute one guard callable and require a bool result."""

    result = self._callRuntimeCallable(callable_ref, event)

    if not isinstance(result, bool):
      raise TypeError("Guard callable must return a bool.")

    return result

  def _callRuntimeCallable(
    self,
    callable_ref: dict[str, str],
    event: HsmRuntimeEvent | None,
  ) -> Any:
    """Resolve one runtime callable, execute it, and persist ctx mutations."""

    module = importlib.import_module(callable_ref["module"])
    handler = getattr(module, callable_ref["name"])
    ctx = SimpleNamespace(**self.variables)
    ctx.variables = self.variables
    ctx.event_id = event["event_id"] if event is not None else None
    ctx.event_parameters = event["parameters"] if event is not None else {}
    ctx.send_event = lambda nested_event_id, nested_parameters=None: self.sendEvent(
      nested_event_id,
      nested_parameters,
    )

    result = handler(ctx)

    for name in self.variables:
      if hasattr(ctx, name):
        self.variables[name] = getattr(ctx, name)

    return result

  def _requireModel(self) -> HsmModel:
    """Return the initialized model or fail if the runtime is uninitialized."""

    if self.model is None:
      raise RuntimeError("Runtime has not been initialized with a model.")
    return self.model
