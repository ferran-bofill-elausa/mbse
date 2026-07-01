from __future__ import annotations

"""HSM runtime API and internal implementation contract."""

from copy import deepcopy
from typing import Any
from typing import Literal
from typing import TypeAlias
from typing import TypedDict

from mbse.model.context.context_model import ContextModel
from mbse.model.hsm.hsm_model import HsmModel
from mbse.runtime.runtime_signals import RuntimeExecutionSuspended


HsmRuntimeExecutableRef: TypeAlias = dict[str, Any]


class HsmRuntimeEvent(TypedDict):
  """Queued runtime event waiting to be planned."""

  event_id: str | None
  parameters: dict[str, Any]


class HsmRuntimeInitialTransition(TypedDict):
  """Trace entry for one initial transition."""

  kind: Literal["initial_transition"]
  source_state_id: str | None
  source_state_label: str | None
  target_state_id: str
  target_state_label: str
  activity: HsmRuntimeExecutableRef | None


class HsmRuntimeExternalTransition(TypedDict):
  """Trace entry for one external transition."""

  kind: Literal["external_transition"]
  source_state_id: str
  source_state_label: str
  target_state_id: str
  target_state_label: str
  activity: HsmRuntimeExecutableRef | None


class HsmRuntimeGuardedTransition(TypedDict):
  """Trace entry for the transition segment that reaches one guard node."""

  kind: Literal["guarded_transition"]
  source_state_id: str
  source_state_label: str
  activity: HsmRuntimeExecutableRef | None


class HsmRuntimeGuardBranchTransition(TypedDict):
  """Trace entry for one guard-branch activity."""

  kind: Literal["guard_branch_transition"]
  source_state_id: str
  source_state_label: str
  target_state_id: str
  target_state_label: str
  result: bool
  activity: HsmRuntimeExecutableRef | None


class HsmRuntimeInternalTransition(TypedDict):
  """Trace entry for one internal transition."""

  kind: Literal["internal_transition"]
  source_state_id: str
  source_state_label: str
  activity: HsmRuntimeExecutableRef | None


class HsmRuntimeGuardCondition(TypedDict):
  """Trace entry for one resolved guard condition."""

  kind: Literal["guard_condition"]
  source_state_id: str
  source_state_label: str
  guard_activity: HsmRuntimeExecutableRef
  result: bool
  target_state_id: str
  target_state_label: str


class HsmRuntimeOnEntry(TypedDict):
  """Trace entry for one on_entry hook execution."""

  kind: Literal["on_entry"]
  source_state_id: str
  source_state_label: str
  activity: HsmRuntimeExecutableRef


class HsmRuntimeOnExit(TypedDict):
  """Trace entry for one on_exit hook execution."""

  kind: Literal["on_exit"]
  source_state_id: str
  source_state_label: str
  activity: HsmRuntimeExecutableRef


class HsmRuntimeChangeActiveState(TypedDict):
  """Trace entry for one explicit active-state update."""

  kind: Literal["change_active_state"]
  target_state_id: str
  target_state_label: str


class HsmRuntimeForcedState(TypedDict):
  """Trace entry for one forced-state override."""

  kind: Literal["forced_state"]
  target_state_id: str
  target_state_label: str


HsmRuntimeTraceTypeAlias: TypeAlias = (
  HsmRuntimeGuardCondition |
  HsmRuntimeInitialTransition |
  HsmRuntimeExternalTransition |
  HsmRuntimeGuardedTransition |
  HsmRuntimeGuardBranchTransition |
  HsmRuntimeInternalTransition |
  HsmRuntimeOnEntry |
  HsmRuntimeOnExit |
  HsmRuntimeChangeActiveState |
  HsmRuntimeForcedState
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
  guard_activity: HsmRuntimeExecutableRef
  true_target_state_id: str
  true_target_state_label: str
  true_branch: list[HsmRuntimePendingExecutionTypeAlias]
  false_target_state_id: str
  false_target_state_label: str
  false_branch: list[HsmRuntimePendingExecutionTypeAlias]


HsmRuntimePendingExecutionTypeAlias: TypeAlias = (
  HsmRuntimeInitialTransition |
  HsmRuntimeExternalTransition |
  HsmRuntimeGuardedTransition |
  HsmRuntimeGuardBranchTransition |
  HsmRuntimeInternalTransition |
  HsmRuntimeOnEntry |
  HsmRuntimeOnExit |
  HsmRuntimeChangeActiveState |
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
    self.is_paused = True
    self.current_state_id: str | None = None
    self.variables: dict[str, Any] = {}
    self.execution_log: list[HsmRuntimeTrace] = []
    self.pending_execution: HsmRuntimePendingTrace | None = None
    self.event_queue: list[HsmRuntimeEvent] = []
    self.executable_handler: Any | None = None

  def init(self, model: HsmModel, context: ContextModel | None = None) -> None:
    """Initialize or fully reinitialize the runtime from one loaded HSM model.

    The runtime is reset to its authored variable defaults, bootstrap
    initialization is planned immediately, and execution starts paused.
    """

    self.model = model
    self.is_paused = True
    self.current_state_id = None
    # Copy authored defaults so runtime mutation never aliases the model payload.
    variable_declarations = [] if context is None else context.getVariables()
    self.variables = {
      variable["name"]: deepcopy(variable["default_value"])
      for variable in variable_declarations
    }
    self.execution_log = []
    self.pending_execution = None
    self.event_queue = []

    self._planInit()

  def play(self) -> bool:
    """Resume execution and drain all pending work until the runtime is idle.

    After this call returns, the runtime remains unpaused so future events auto-run.
    """

    self.is_paused = False
    return self._runToCompletion()

  def pause(self) -> None:
    """Pause future automatic execution between events, never mid-event."""

    self.is_paused = True

  def isPaused(self) -> bool:
    """Return whether automatic execution is currently paused."""

    return self.is_paused

  def step(self) -> bool:
    """Pause automatic execution and advance exactly one planned runtime step.

    If no trace is currently pending, the next queued event is planned without
    executing its first step.
    """

    self.is_paused = True
    if self.pending_execution is None:
      self._planNextQueuedEvent()
      return False

    return self._step()

  def sendEvent(
    self,
    event_id: str,
    parameters: dict[str, Any] | None = None,
  ) -> bool:
    """Enqueue one event and plan or run it immediately when idle."""

    self._pushEvent(event_id, parameters)
    if self.pending_execution is None:
      if self.is_paused:
        self._planNextQueuedEvent()
      else:
        self._runToCompletion()

    return True

  def setState(self, state_id: str) -> None:
    """Force one active state without executing HSM transition semantics.

    Clears any pending trace and queued events, leaves runtime variables untouched, and
    appends one explicit `forced_state` trace entry instead of simulating a real
    HSM transition.
    """

    model = self._requireModel()
    state = model.getStateById(state_id)
    self.current_state_id = state_id
    self.pending_execution = None
    self.event_queue = []
    self.execution_log.append(
      {
        "event": {"event_id": None, "parameters": {}},
        "entries": [
          {
            "kind": "forced_state",
            "target_state_id": state_id,
            "target_state_label": state["label"],
          }
        ],
      }
    )

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

  def hasPendingExecution(self) -> bool:
    """Return whether one planned trace is still waiting to complete."""

    return self.pending_execution is not None

  def getEventQueue(self) -> list[HsmRuntimeEvent]:
    """Return a shallow copy of the queued runtime events."""

    return [dict(event) for event in self.event_queue]

  def getNextStep(self) -> HsmRuntimePendingExecutionTypeAlias | None:
    """Return the next planned runtime step without executing it."""

    pending_execution = self.pending_execution
    if pending_execution is None:
      return None
    if not pending_execution["entries"]:
      return None
    return deepcopy(pending_execution["entries"][0])

  def setExecutableHandler(
    self,
    executable_handler: Any | None,
  ) -> None:
    """Set the upper-layer executable handler."""

    self.executable_handler = executable_handler

  def _planNextQueuedEvent(self) -> bool:
    """Plan the next queued event when no trace is currently in progress."""

    if self.pending_execution is not None:
      return False

    if not self.event_queue:
      return False

    next_event = self._popEvent()
    self._planEvent(next_event)
    return True

  def _runToCompletion(self) -> bool:
    """Execute all pending work and queued events until the runtime is idle."""

    did_work = False
    while True:
      if self.pending_execution is None:
        if not self._planNextQueuedEvent():
          return did_work
      if self._step():
        did_work = True

  def _step(self) -> bool:
    """Execute and advance the current planned trace by one runtime step."""

    pending_execution = self.pending_execution
    if pending_execution is None:
      return False

    if not pending_execution["entries"]:
      return False

    entry = pending_execution["entries"].pop(0)
    kind = entry["kind"]

    try:
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
      elif kind == "change_active_state":
        self.current_state_id = entry["target_state_id"]
        self.execution_log[-1]["entries"].append(entry)
      else:
        # Executable steps are the only ones with user-code side effects.
        if entry["activity"] is not None:
          self._callActivity(entry["activity"], pending_execution["event"])
        self.execution_log[-1]["entries"].append(entry)
    except RuntimeExecutionSuspended:
      pending_execution["entries"].insert(0, entry)
      raise

    if not pending_execution["entries"]:
      self.pending_execution = None

    return True

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

  def _appendInitialTransition(
    self,
    entries: list[HsmRuntimePendingExecutionTypeAlias],
    source_state_id: str | None,
    target_state_id: str,
    activity: HsmRuntimeExecutableRef | None,
  ) -> None:
    """Append one initial-transition runtime step."""

    model = self._requireModel()
    entries.append(
      {
        "kind": "initial_transition",
        "source_state_id": source_state_id,
        "source_state_label": (
          None if source_state_id is None else model.getStateLabel(source_state_id)
        ),
        "target_state_id": target_state_id,
        "target_state_label": model.getStateLabel(target_state_id),
        "activity": activity,
      }
    )

  def _appendExternalTransition(
    self,
    entries: list[HsmRuntimePendingExecutionTypeAlias],
    source_state_id: str,
    target_state_id: str,
    activity: HsmRuntimeExecutableRef | None,
  ) -> None:
    """Append one external-transition runtime step."""

    model = self._requireModel()
    entries.append(
      {
        "kind": "external_transition",
        "source_state_id": source_state_id,
        "source_state_label": model.getStateLabel(source_state_id),
        "target_state_id": target_state_id,
        "target_state_label": model.getStateLabel(target_state_id),
        "activity": activity,
      }
    )

  def _appendGuardedTransition(
    self,
    entries: list[HsmRuntimePendingExecutionTypeAlias],
    source_state_id: str,
    activity: HsmRuntimeExecutableRef | None,
  ) -> None:
    """Append one guarded-transition runtime step."""

    model = self._requireModel()
    entries.append(
      {
        "kind": "guarded_transition",
        "source_state_id": source_state_id,
        "source_state_label": model.getStateLabel(source_state_id),
        "activity": activity,
      }
    )

  def _appendGuardBranchTransition(
    self,
    entries: list[HsmRuntimePendingExecutionTypeAlias],
    source_state_id: str,
    target_state_id: str,
    result: bool,
    activity: HsmRuntimeExecutableRef | None,
  ) -> None:
    """Append one guard-branch runtime step."""

    model = self._requireModel()
    entries.append(
      {
        "kind": "guard_branch_transition",
        "source_state_id": source_state_id,
        "source_state_label": model.getStateLabel(source_state_id),
        "target_state_id": target_state_id,
        "target_state_label": model.getStateLabel(target_state_id),
        "result": result,
        "activity": activity,
      }
    )

  def _appendInternalTransition(
    self,
    entries: list[HsmRuntimePendingExecutionTypeAlias],
    source_state_id: str,
    activity: HsmRuntimeExecutableRef | None,
  ) -> None:
    """Append one internal-transition runtime step."""

    model = self._requireModel()
    entries.append(
      {
        "kind": "internal_transition",
        "source_state_id": source_state_id,
        "source_state_label": model.getStateLabel(source_state_id),
        "activity": activity,
      }
    )

  def _appendOnEntry(
    self,
    entries: list[HsmRuntimePendingExecutionTypeAlias],
    state_id: str,
    activity: HsmRuntimeExecutableRef,
  ) -> None:
    """Append one on_entry runtime step."""

    entries.append(
      {
        "kind": "on_entry",
        "source_state_id": state_id,
        "source_state_label": self._requireModel().getStateLabel(state_id),
        "activity": activity,
      }
    )

  def _appendOnExit(
    self,
    entries: list[HsmRuntimePendingExecutionTypeAlias],
    state_id: str,
    activity: HsmRuntimeExecutableRef,
  ) -> None:
    """Append one on_exit runtime step."""

    entries.append(
      {
        "kind": "on_exit",
        "source_state_id": state_id,
        "source_state_label": self._requireModel().getStateLabel(state_id),
        "activity": activity,
      }
    )

  def _appendChangeActiveState(
    self,
    entries: list[HsmRuntimePendingExecutionTypeAlias],
    state_id: str,
  ) -> None:
    """Append one explicit active-state update runtime step."""

    entries.append(
      {
        "kind": "change_active_state",
        "target_state_id": state_id,
        "target_state_label": self._requireModel().getStateLabel(state_id),
      }
    )

  def _buildTransitionBranch(
    self,
    current_state_id: str,
    source_state_id: str,
    target_state_id: str,
    external_transition: dict[str, Any],
    branch_activities: list[HsmRuntimeExecutableRef],
    branch_result: bool | None = None,
  ) -> list[HsmRuntimePendingExecutionTypeAlias]:
    """Build the deterministic pending entries for one chosen transition branch."""

    entries: list[HsmRuntimePendingExecutionTypeAlias] = []
    model = self._requireModel()
    if branch_result is None:
      transition_activities = external_transition.get("activities", [])
      if not transition_activities:
        self._appendExternalTransition(entries, source_state_id, target_state_id, None)

      for activity in transition_activities:
        self._appendExternalTransition(entries, source_state_id, target_state_id, activity)

    for activity in branch_activities:
      if branch_result is None:
        continue
      self._appendGuardBranchTransition(
        entries,
        source_state_id,
        target_state_id,
        branch_result,
        activity,
      )

    if branch_result is not None and not branch_activities:
      self._appendGuardBranchTransition(
        entries,
        source_state_id,
        target_state_id,
        branch_result,
        None,
      )

    # Exit from the active leaf up to the state that actually owns the transition.
    aux_state_id = current_state_id
    while aux_state_id != source_state_id:
      for activity in model.getStateOnExit(aux_state_id):
        self._appendOnExit(entries, aux_state_id, activity)
      aux_state_id = model.getParentStateId(aux_state_id)

    exit_path, entry_path = self._getTransitionPath(source_state_id, target_state_id)

    # Exit and entry hooks follow the same transition path computed below.
    for exit_state_id in exit_path:
      for activity in model.getStateOnExit(exit_state_id):
        self._appendOnExit(entries, exit_state_id, activity)

    for entry_state_id in reversed(entry_path):
      for activity in model.getStateOnEntry(entry_state_id):
        self._appendOnEntry(entries, entry_state_id, activity)

    current_target_state_id = target_state_id

    # Once the target is entered, keep descending through local initials.
    while model.hasStateInitialTransition(current_target_state_id):
      next_target_state_id = model.getStateInitialTargetId(current_target_state_id)
      initial_activities = model.getStateInitialTransitionActivities(current_target_state_id)
      for activity in initial_activities:
        self._appendInitialTransition(
          entries,
          current_target_state_id,
          next_target_state_id,
          activity,
        )

      if not initial_activities:
        self._appendInitialTransition(
          entries,
          current_target_state_id,
          next_target_state_id,
          None,
        )

      nested_entry_path = [next_target_state_id]
      parent_state_id = model.getParentStateId(next_target_state_id)
      while parent_state_id is not None and parent_state_id != current_target_state_id:
        nested_entry_path.append(parent_state_id)
        parent_state_id = model.getParentStateId(parent_state_id)

      for entry_state_id in reversed(nested_entry_path):
        for activity in model.getStateOnEntry(entry_state_id):
          self._appendOnEntry(entries, entry_state_id, activity)

      current_target_state_id = next_target_state_id

    if current_target_state_id != current_state_id:
      self._appendChangeActiveState(entries, current_target_state_id)

    return entries

  def _planInit(self) -> None:
    """Plan root initialization plus full nested initial descent."""

    model = self._requireModel()
    event: HsmRuntimeEvent = {"event_id": None, "parameters": {}}
    entries: list[HsmRuntimePendingExecutionTypeAlias] = []

    target_state_id = model.getRootInitialTargetId()
    self._appendInitialTransition(entries, None, target_state_id, None)

    entry_path = [target_state_id]
    # Build the entry path upward, then replay it downward during initialization.
    parent_state_id = model.getParentStateId(target_state_id)
    while parent_state_id is not None:
      entry_path.append(parent_state_id)
      parent_state_id = model.getParentStateId(parent_state_id)

    for state_id in reversed(entry_path):
      for activity in model.getStateOnEntry(state_id):
        self._appendOnEntry(entries, state_id, activity)

    current_state_id = target_state_id
    # Repeat local initial descent until reaching the final active leaf.
    while model.hasStateInitialTransition(current_state_id):
      target_state_id = model.getStateInitialTargetId(current_state_id)
      initial_activities = model.getStateInitialTransitionActivities(current_state_id)
      for activity in initial_activities:
        self._appendInitialTransition(
          entries,
          current_state_id,
          target_state_id,
          activity,
        )

      if not initial_activities:
        self._appendInitialTransition(
          entries,
          current_state_id,
          target_state_id,
          None,
        )

      entry_path = [target_state_id]
      parent_state_id = model.getParentStateId(target_state_id)
      while parent_state_id is not None and parent_state_id != current_state_id:
        entry_path.append(parent_state_id)
        parent_state_id = model.getParentStateId(parent_state_id)

      for state_id in reversed(entry_path):
        for activity in model.getStateOnEntry(state_id):
          self._appendOnEntry(entries, state_id, activity)

      current_state_id = target_state_id

    self._appendChangeActiveState(entries, current_state_id)

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
        transition_activities = internal_transition.get("activities", [])
        if not transition_activities:
          self._appendInternalTransition(entries, state_id, None)
        for activity in transition_activities:
          self._appendInternalTransition(entries, state_id, activity)

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
        transition_activities = external_transition.get("activities", [])
        if not transition_activities:
          self._appendGuardedTransition(entries, source_state_id, None)
        for activity in transition_activities:
          self._appendGuardedTransition(
            entries,
            source_state_id,
            activity,
          )
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
              branch_result=True,
            ),
            "false_target_state_id": false_branch["target_id"],
            "false_target_state_label": model.getStateLabel(false_branch["target_id"]),
            "false_branch": self._buildTransitionBranch(
              current_state_id,
              source_state_id,
              false_branch["target_id"],
              external_transition,
              false_branch.get("activities", []),
              branch_result=False,
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

  def _callActivity(
    self,
    executable_ref: HsmRuntimeExecutableRef,
    event: HsmRuntimeEvent | None,
  ) -> Any:
    """Execute one activity executable through the upper handler."""

    return self._callRuntimeExecutable(executable_ref, event)

  def _callGuard(
    self,
    executable_ref: HsmRuntimeExecutableRef,
    event: HsmRuntimeEvent,
  ) -> bool:
    """Execute one guard executable and require a bool result."""

    result = self._callRuntimeExecutable(executable_ref, event)

    if not isinstance(result, bool):
      raise TypeError("Guard executable must return a bool.")

    return result

  def _callRuntimeExecutable(
    self,
    executable_ref: HsmRuntimeExecutableRef,
    event: HsmRuntimeEvent | None,
  ) -> Any:
    """Execute one runtime executable through the upper handler."""

    if self.executable_handler is None:
      raise RuntimeError("Executables require an upper Runtime handler.")
    return self.executable_handler(executable_ref, self, event)

  def _requireModel(self) -> HsmModel:
    """Return the initialized model or fail if the runtime is uninitialized."""

    if self.model is None:
      raise RuntimeError("Runtime has not been initialized with a model.")
    return self.model
