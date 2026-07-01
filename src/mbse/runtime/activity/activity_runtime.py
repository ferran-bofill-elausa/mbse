from __future__ import annotations

"""Activity runtime API and internal implementation contract."""

from copy import deepcopy
from typing import Any
from typing import Literal
from typing import TypeAlias
from typing import TypedDict

from mbse.model.activity.activity_model import ActivityModel
from mbse.model.context.context_model import ContextModel
from mbse.runtime.runtime_signals import RuntimeExecutionSuspended


ActivityRuntimeExecutableRef: TypeAlias = dict[str, Any]


class ActivityRuntimeInitial(TypedDict):
  """Trace entry for the initial activity edge."""

  kind: Literal["initial"]
  target_id: str
  target_label: str
  target_type: Literal["action", "decision", "final"]


class ActivityRuntimeAction(TypedDict):
  """Trace entry for one executed action."""

  kind: Literal["action"]
  action_id: str
  action_label: str
  executable: ActivityRuntimeExecutableRef
  target_id: str
  target_label: str
  target_type: Literal["action", "decision", "final"]


class ActivityRuntimePendingDecision(TypedDict):
  """Pending decision with both branches precalculated.

  This node exists only in pending_execution. Once the decision is executed, the
  chosen branch replaces this node and the execution log receives one resolved
  ActivityRuntimeDecision entry.
  """

  kind: Literal["pending_decision"]
  decision_id: str
  decision_label: str
  condition: ActivityRuntimeExecutableRef
  true_target_id: str
  true_target_label: str
  true_target_type: Literal["action", "decision", "final"]
  false_target_id: str
  false_target_label: str
  false_target_type: Literal["action", "decision", "final"]
  true_branch: list[ActivityRuntimePendingExecutionTypeAlias]
  false_branch: list[ActivityRuntimePendingExecutionTypeAlias]


class ActivityRuntimeDecision(TypedDict):
  """Trace entry for one resolved decision."""

  kind: Literal["decision"]
  decision_id: str
  decision_label: str
  condition: ActivityRuntimeExecutableRef
  result: bool
  target_id: str
  target_label: str
  target_type: Literal["action", "decision", "final"]


class ActivityRuntimeFinal(TypedDict):
  """Trace entry for one reached final node."""

  kind: Literal["final"]
  final_id: str
  final_label: str


ActivityRuntimeTraceTypeAlias: TypeAlias = (
  ActivityRuntimeInitial |
  ActivityRuntimeAction |
  ActivityRuntimeDecision |
  ActivityRuntimeFinal
)


ActivityRuntimePendingExecutionTypeAlias: TypeAlias = (
  ActivityRuntimeInitial |
  ActivityRuntimeAction |
  ActivityRuntimePendingDecision |
  ActivityRuntimeFinal
)


class ActivityRuntimeTrace(TypedDict):
  """One activity runtime trace."""

  entries: list[ActivityRuntimeTraceTypeAlias]


class ActivityRuntimePendingTrace(TypedDict):
  """One full pending activity trace."""

  entries: list[ActivityRuntimePendingExecutionTypeAlias]


class ActivityRuntime:
  """Mutable Activity runtime instance."""

  def __init__(self) -> None:
    """ActivityRuntime initialization."""

    self.model: ActivityModel | None = None
    self.is_paused = True
    self.variables: dict[str, Any] = {}
    self.execution_log: list[ActivityRuntimeTrace] = []
    self.pending_execution: ActivityRuntimePendingTrace | None = None
    self.executable_handler: Any | None = None

  def init(self, model: ActivityModel, context: ContextModel | None = None) -> None:
    """Initialize or fully reinitialize the runtime from one loaded Activity model."""

    self.model = model
    self.is_paused = True
    variable_declarations = [] if context is None else context.getVariables()
    self.variables = {
      variable["name"]: deepcopy(variable["default_value"])
      for variable in variable_declarations
    }
    self.execution_log = []
    self.pending_execution = None

    self._planInit()

  def play(self) -> bool:
    """Resume execution and drain all pending work until the runtime is idle."""

    self.is_paused = False
    return self._runToCompletion()

  def pause(self) -> None:
    """Pause future automatic execution."""

    self.is_paused = True

  def isPaused(self) -> bool:
    """Return whether automatic execution is currently paused."""

    return self.is_paused

  def step(self) -> bool:
    """Pause automatic execution and advance exactly one planned runtime step."""

    self.is_paused = True
    return self._step()

  def setVariable(self, name: str, value: Any) -> None:
    """Set one runtime variable value."""

    self.variables[name] = value

  def getVariable(self, name: str) -> Any:
    """Get one runtime variable value."""

    return self.variables[name]

  def getExecutionLog(self) -> list[ActivityRuntimeTrace]:
    """Get the accumulated runtime execution log."""

    return self.execution_log

  def hasPendingExecution(self) -> bool:
    """Return whether one planned trace is still waiting to complete."""

    return self.pending_execution is not None

  def getNextStep(self) -> ActivityRuntimePendingExecutionTypeAlias | None:
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

  def _runToCompletion(self) -> bool:
    """Execute all pending work until the runtime is idle."""

    did_work = False
    while self._step():
      did_work = True
    return did_work

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
      if kind == "initial":
        self.execution_log[-1]["entries"].append(entry)
      elif kind == "action":
        self._callActivity(entry["executable"])
        self.execution_log[-1]["entries"].append(entry)
      elif kind == "pending_decision":
        result = self._callCondition(entry["condition"])
        branch_entries = entry["true_branch"] if result else entry["false_branch"]
        target_id = entry["true_target_id"] if result else entry["false_target_id"]
        target_label = entry["true_target_label"] if result else entry["false_target_label"]
        target_type = entry["true_target_type"] if result else entry["false_target_type"]
        self.execution_log[-1]["entries"].append(
          {
            "kind": "decision",
            "decision_id": entry["decision_id"],
            "decision_label": entry["decision_label"],
            "condition": entry["condition"],
            "result": result,
            "target_id": target_id,
            "target_label": target_label,
            "target_type": target_type,
          }
        )
        pending_execution["entries"][0:0] = branch_entries
      elif kind == "final":
        self.execution_log[-1]["entries"].append(entry)
      else:
        raise ValueError(f"Unknown activity runtime step kind '{kind}'.")
    except RuntimeExecutionSuspended:
      pending_execution["entries"].insert(0, entry)
      raise

    if not pending_execution["entries"]:
      self.pending_execution = None

    return True

  def _planInit(self) -> None:
    """Plan the initial activity step."""

    model = self._requireModel()
    target_id = model.getInitialTargetId()
    target_type, target_label = self._getElementTypeAndLabel(target_id)
    entries: list[ActivityRuntimePendingExecutionTypeAlias] = [
      {
        "kind": "initial",
        "target_id": target_id,
        "target_label": target_label,
        "target_type": target_type,
      }
    ]
    entries.extend(self._buildElementBranch(target_id))
    self.pending_execution = {
      "entries": entries
    }
    self.execution_log.append({"entries": []})

  def _buildElementBranch(
    self,
    element_id: str,
  ) -> list[ActivityRuntimePendingExecutionTypeAlias]:
    """Build pending entries for one activity element and its reachable branches."""

    model = self._requireModel()
    element_type, element_label = self._getElementTypeAndLabel(element_id)

    if element_type == "action":
      action = model.getActionById(element_id)
      target_id = action["transition"]["target_id"]
      target_type, target_label = self._getElementTypeAndLabel(target_id)
      return [
        {
          "kind": "action",
          "action_id": element_id,
          "action_label": element_label,
          "executable": action["executable"],
          "target_id": target_id,
          "target_label": target_label,
          "target_type": target_type,
        }
      ] + self._buildElementBranch(target_id)

    if element_type == "decision":
      decision = model.getDecisionById(element_id)
      true_target_id = decision["true_transition"]["target_id"]
      false_target_id = decision["false_transition"]["target_id"]
      true_target_type, true_target_label = self._getElementTypeAndLabel(true_target_id)
      false_target_type, false_target_label = self._getElementTypeAndLabel(false_target_id)
      return [
        {
          "kind": "pending_decision",
          "decision_id": element_id,
          "decision_label": element_label,
          "condition": decision["condition"],
          "true_target_id": true_target_id,
          "true_target_label": true_target_label,
          "true_target_type": true_target_type,
          "false_target_id": false_target_id,
          "false_target_label": false_target_label,
          "false_target_type": false_target_type,
          "true_branch": self._buildElementBranch(true_target_id),
          "false_branch": self._buildElementBranch(false_target_id),
        }
      ]

    if element_type == "final":
      return [
        {
          "kind": "final",
          "final_id": element_id,
          "final_label": element_label,
        }
      ]

    raise ValueError(f"Unknown activity element type '{element_type}'.")

  def _getElementTypeAndLabel(
    self,
    element_id: str,
  ) -> tuple[Literal["action", "decision", "final"], str]:
    """Resolve one activity element id to its type and label."""

    model = self._requireModel()

    for action in model.getActions():
      if action["id"] == element_id:
        return "action", action["label"]

    for decision in model.getDecisions():
      if decision["id"] == element_id:
        return "decision", decision["label"]

    for final in model.getFinals():
      if final["id"] == element_id:
        return "final", final["label"]

    raise ValueError(f"Unknown activity target_id '{element_id}'.")

  def _callActivity(self, executable_ref: ActivityRuntimeExecutableRef) -> Any:
    """Execute one action executable through the upper handler."""

    return self._callRuntimeExecutable(executable_ref)

  def _callCondition(self, executable_ref: ActivityRuntimeExecutableRef) -> bool:
    """Execute one decision condition and require a bool result."""

    result = self._callRuntimeExecutable(executable_ref)

    if not isinstance(result, bool):
      raise TypeError("Decision condition executable must return a bool.")

    return result

  def _callRuntimeExecutable(self, executable_ref: ActivityRuntimeExecutableRef) -> Any:
    """Execute one runtime executable through the upper handler."""

    if self.executable_handler is None:
      raise RuntimeError("Executables require an upper Runtime handler.")
    return self.executable_handler(executable_ref, self, None)

  def _requireModel(self) -> ActivityModel:
    """Return the initialized model or fail if the runtime is uninitialized."""

    if self.model is None:
      raise RuntimeError("Runtime has not been initialized with a model.")
    return self.model
