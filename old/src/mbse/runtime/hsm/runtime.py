from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from mbse.model.hsm import HsmVariable

from .generator.generator import GeneratedRuntime
from .runtime_model.runtime_model_types import HsmGeneratedRuntimeEventCandidateRow
from .runtime_model.runtime_model_types import HsmGeneratedRuntimeGuardBranchRow
from .runtime_state_types import HsmExecutedActivity
from .runtime_state_types import HsmRuntimeLastEvent
from .runtime_state_types import HsmRuntimeMetadata
from .runtime_state_types import HsmRuntimeSnapshot


class HsmRuntimeContext:
  """Mutable variable store scoped to one runtime instance."""

  def __init__(self, variables: tuple[HsmVariable, ...]) -> None:
    """Register declared variables and copy their defaults."""

    object.__setattr__(self, "_declared_defaults", {
      variable.id: variable.default for variable in variables
    })
    object.__setattr__(self, "_values", {})
    self.reset()

  def reset(self) -> None:
    """Restore all variables to deep-copied declared defaults."""

    object.__setattr__(
      self,
      "_values",
      {
        variable_id: deepcopy(default)
        for variable_id, default in self._declared_defaults.items()
      },
    )

  def export_variables(self) -> dict[str, object]:
    """Return a shallow copy of current runtime variables."""

    return dict(self._values)

  def get_variable(self, variable_id: str) -> object:
    """Return one declared variable value by ID."""

    self._require_declared_variable(variable_id)
    return self._values[variable_id]

  def set_variable(self, variable_id: str, value: object) -> None:
    """Set one declared variable value by ID."""

    self._require_declared_variable(variable_id)
    self._values[variable_id] = value

  def _require_declared_variable(self, variable_id: str) -> None:
    """Reject access to variables that the model did not declare."""

    if variable_id not in self._declared_defaults:
      raise ValueError(
        f"Unknown HSM variable '{variable_id}'. Declare it in the HSM 'variables' list first."
      )

  def __getattr__(self, name: str) -> object:
    """Expose declared variables as attribute reads for callables."""

    if name in self._declared_defaults:
      return self._values[name]
    raise AttributeError(
      f"Unknown HSM variable '{name}'. Declare it in the HSM 'variables' list first."
    )

  def __setattr__(self, name: str, value: object) -> None:
    """Route public attribute writes through declared variable checks."""

    if name.startswith("_"):
      object.__setattr__(self, name, value)
      return
    self.set_variable(name, value)


@dataclass(frozen=True)
class HsmRuntimeTransitionPath:
  """Resolved exit and entry paths for one taken transition."""

  source_id: str
  target_id: str
  lca_id: str | None
  exit_path: tuple[str, ...]
  entry_path: tuple[str, ...]
  should_descend_initials: bool


class HsmRuntime:
  """Handwritten public runtime API over generated runtime data."""

  def __init__(
    self,
    generated_runtime: GeneratedRuntime,
    *,
    variables: tuple[HsmVariable, ...],
    event_ids: tuple[str, ...],
  ) -> None:
    """Create one runtime bound to generated runtime data."""

    self._generated_runtime = generated_runtime
    self._context = HsmRuntimeContext(variables)
    self._metadata = HsmRuntimeMetadata(
      event_ids=event_ids,
      variable_ids=tuple(variable.id for variable in variables),
    )
    self._active_path: tuple[str, ...] = ()
    self._last_event = HsmRuntimeLastEvent()

  def init(self) -> None:
    """Initialize the runtime and resolve the full initial leaf path."""

    self._context.reset()
    self._active_path = ()
    self._last_event = HsmRuntimeLastEvent()
    target_id = self._generated_runtime.initial_target_ids[None]
    executed_activities: list[HsmExecutedActivity] = []
    transition_ids: list[str] = []
    initial_transition_id = self._generated_runtime.initial_transition_ids.get(None)
    if initial_transition_id is not None:
      transition_ids.append(initial_transition_id)
    self._run_entry_path(None, target_id, executed_activities)
    leaf_state_id, nested_transition_ids = self._descend_initial_chain(
      target_id,
      executed_activities,
    )
    transition_ids.extend(nested_transition_ids)
    self._active_path = self._resolve_ancestry(leaf_state_id)
    self._last_event = HsmRuntimeLastEvent(
      handled=bool(transition_ids or executed_activities),
      handler_kind="init" if transition_ids or executed_activities else None,
      transition_path_ids=tuple(transition_ids),
      executed_activities=tuple(executed_activities),
    )

  def set_variable(self, variable_id: str, value: object) -> None:
    """Set one runtime variable by ID."""

    self._context.set_variable(variable_id, value)

  def get_variable(self, variable_id: str) -> object:
    """Return one runtime variable by ID."""

    return self._context.get_variable(variable_id)

  def send_event(self, event_id: str) -> bool:
    """Dispatch one event against the active path and record the outcome."""

    for state_id in reversed(self._active_path):
      for candidate in self._generated_runtime.event_candidate_rows_by_state_id[state_id]:
        if candidate.event_id != event_id:
          continue
        if candidate.kind == "internal":
          executed_activities: list[HsmExecutedActivity] = []
          self._run_activity_plan_ids(
            candidate.activity_plan_ids,
            executed_activities,
          )
          self._last_event = HsmRuntimeLastEvent(
            event_id=event_id,
            handled=True,
            handler_kind="internal_transition",
            handler_id=candidate.candidate_id,
            executed_activities=tuple(executed_activities),
          )
          return True
        if candidate.guard_plan_id is not None:
          guard = self._generated_runtime.resolve_guard_handler(candidate.guard_plan_id)
          guard_result = guard(self._context)
          if candidate.guard_node_id is not None:
            branch = self._resolve_guard_branch(candidate, guard_result)
            if branch is None:
              continue
            executed_activities = []
            transition_path = self._compute_transition_path(
              candidate.source_id,
              branch.target_id,
              reenter_target_on_same_state=False,
            )
            self._active_path, transition_path_ids = self._execute_transition(
              transition_path,
              candidate,
              executed_activities,
              guard_branch=branch,
            )
            self._last_event = HsmRuntimeLastEvent(
              event_id=event_id,
              handled=True,
              handler_kind="guard_transition",
              handler_id=candidate.candidate_id,
              guard_node_id=candidate.guard_node_id,
              guard_branch_id=branch.branch_id,
              transition_path_ids=transition_path_ids,
              executed_activities=tuple(executed_activities),
            )
            return True
          if not guard_result:
            continue
        executed_activities = []
        transition_path = self._compute_transition_path(
          candidate.source_id,
          candidate.target_id or "",
        )
        self._active_path, transition_path_ids = self._execute_transition(
          transition_path,
          candidate,
          executed_activities,
        )
        self._last_event = HsmRuntimeLastEvent(
          event_id=event_id,
          handled=True,
            handler_kind="external_transition",
          handler_id=candidate.candidate_id,
          transition_path_ids=transition_path_ids,
          executed_activities=tuple(executed_activities),
        )
        return True
    self._last_event = HsmRuntimeLastEvent(event_id=event_id)
    return False

  def set_state(self, state_id: str) -> None:
    """Force the active leaf state for tests or inspection tools."""

    if state_id not in self._generated_runtime.leaf_state_ids:
      raise ValueError(f"set_state requires a known leaf state, got '{state_id}'.")
    self._active_path = self._resolve_ancestry(state_id)
    self._last_event = HsmRuntimeLastEvent()

  def get_state(self) -> str:
    """Return the current active leaf state ID."""

    if not self._active_path:
      raise ValueError("Runtime is not initialized.")
    return self._active_path[-1]

  def get_snapshot(self) -> HsmRuntimeSnapshot:
    """Return a deterministic inspection snapshot of runtime state."""

    return HsmRuntimeSnapshot(
      state_id=self.get_state(),
      active_path=self._active_path,
      variables=self._context.export_variables(),
      last_event=self._last_event,
    )

  def get_metadata(self) -> HsmRuntimeMetadata:
    """Return canonical runtime-declared event and variable IDs."""

    return self._metadata

  def _compute_transition_path(
    self,
    source_id: str,
    target_id: str,
    *,
    reenter_target_on_same_state: bool = True,
  ) -> HsmRuntimeTransitionPath:
    """Compute exit and entry paths for a transition target."""

    source_ancestry = self._generated_runtime.ancestry_by_state_id[source_id]
    target_ancestry = self._generated_runtime.ancestry_by_state_id[target_id]

    lca_id: str | None = None
    shared_depth = 0
    for source_ancestor_id, target_ancestor_id in zip(
      source_ancestry,
      target_ancestry,
    ):
      if source_ancestor_id != target_ancestor_id:
        break
      lca_id = source_ancestor_id
      shared_depth += 1

    is_self_transition = source_id == target_id and reenter_target_on_same_state
    exit_path_builder: list[str] = []
    for state_id in reversed(self._active_path):
      if not is_self_transition and state_id == lca_id:
        break
      exit_path_builder.append(state_id)
      if is_self_transition and state_id == source_id:
        break
    exit_path = tuple(exit_path_builder)
    entry_path = (
      (target_id,)
      if is_self_transition
      else tuple(target_ancestry[shared_depth:])
    )
    return HsmRuntimeTransitionPath(
      source_id=source_id,
      target_id=target_id,
      lca_id=lca_id,
      exit_path=exit_path,
      entry_path=entry_path,
      should_descend_initials=bool(entry_path),
    )

  def _execute_transition(
    self,
    transition_path: HsmRuntimeTransitionPath,
    transition_row: HsmGeneratedRuntimeEventCandidateRow,
    executed_activities: list[HsmExecutedActivity],
    *,
    guard_branch: HsmGeneratedRuntimeGuardBranchRow | None = None,
  ) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Run one taken transition and return new path plus transition IDs."""

    for state_id in transition_path.exit_path:
      self._run_on_exit(state_id, executed_activities)
    self._run_activity_plan_ids(
      transition_row.activity_plan_ids,
      executed_activities,
    )
    if guard_branch is not None:
      self._run_activity_plan_ids(
        guard_branch.activity_plan_ids,
        executed_activities,
      )
    for state_id in transition_path.entry_path:
      self._run_on_entry(state_id, executed_activities)

    leaf_state_id = guard_branch.target_id if guard_branch is not None else transition_path.target_id
    transition_ids = [transition_row.candidate_id]
    if guard_branch is not None:
      transition_ids.append(guard_branch.branch_id)
    if transition_path.should_descend_initials:
      leaf_state_id, initial_transition_ids = self._descend_initial_chain(
        leaf_state_id,
        executed_activities,
      )
      transition_ids.extend(initial_transition_ids)
    return self._resolve_ancestry(leaf_state_id), tuple(transition_ids)

  def _resolve_guard_branch(
    self,
    candidate: HsmGeneratedRuntimeEventCandidateRow,
    guard_result: bool,
  ) -> HsmGeneratedRuntimeGuardBranchRow | None:
    """Select the resolved guard branch for one guard result."""

    branch = candidate.guard_true_branch if guard_result else candidate.guard_false_branch
    if branch is None:
      raise ValueError(
        f"Guard transition '{candidate.candidate_id}' is missing the resolved branch definition."
      )
    return branch

  def _descend_initial_chain(
    self,
    state_id: str,
    executed_activities: list[HsmExecutedActivity] | None = None,
  ) -> tuple[str, tuple[str, ...]]:
    """Follow nested local initials until the active leaf is reached."""

    current_state_id = state_id
    transition_ids: list[str] = []
    while current_state_id in self._generated_runtime.initial_target_ids:
      self._run_on_initial(current_state_id, executed_activities)
      initial_transition_id = self._generated_runtime.initial_transition_ids.get(current_state_id)
      if initial_transition_id is not None:
        transition_ids.append(initial_transition_id)
      next_state_id = self._generated_runtime.initial_target_ids[current_state_id]
      self._run_entry_path(current_state_id, next_state_id, executed_activities)
      current_state_id = next_state_id
    return current_state_id, tuple(transition_ids)

  def _run_entry_path(
    self,
    owner_state_id: str | None,
    target_id: str,
    executed_activities: list[HsmExecutedActivity] | None = None,
  ) -> None:
    """Run on-entry hooks for the full path from one owner to its target."""

    for state_id in self._resolve_entry_path(owner_state_id, target_id):
      self._run_on_entry(state_id, executed_activities)

  def _resolve_entry_path(
    self,
    owner_state_id: str | None,
    target_id: str,
  ) -> tuple[str, ...]:
    """Return the states entered when one initial descends to its target."""

    target_ancestry = self._generated_runtime.ancestry_by_state_id[target_id]
    if owner_state_id is None:
      return target_ancestry
    owner_ancestry = self._generated_runtime.ancestry_by_state_id[owner_state_id]
    if target_ancestry[: len(owner_ancestry)] != owner_ancestry:
      raise ValueError(
        f"Initial target '{target_id}' is not contained by state '{owner_state_id}'."
      )
    return target_ancestry[len(owner_ancestry) :]

  def _run_on_initial(
    self,
    state_id: str,
    executed_activities: list[HsmExecutedActivity] | None = None,
  ) -> None:
    """Run generated on-initial activities for one active state."""

    self._run_activity_plan_ids(
      self._generated_runtime.on_initial_plan_ids_by_state_id.get(state_id, ()),
      executed_activities,
    )

  def _run_on_entry(
    self,
    state_id: str,
    executed_activities: list[HsmExecutedActivity] | None = None,
  ) -> None:
    """Run generated on-entry activities for one state."""

    self._run_activity_plan_ids(
      self._generated_runtime.on_entry_plan_ids_by_state_id.get(state_id, ()),
      executed_activities,
    )

  def _run_on_exit(
    self,
    state_id: str,
    executed_activities: list[HsmExecutedActivity] | None = None,
  ) -> None:
    """Run generated on-exit activities for one state."""

    self._run_activity_plan_ids(
      self._generated_runtime.on_exit_plan_ids_by_state_id.get(state_id, ()),
      executed_activities,
    )

  def _run_activity_plan_ids(
    self,
    plan_ids: tuple[str, ...],
    executed_activities: list[HsmExecutedActivity] | None = None,
  ) -> None:
    """Run ordered activity plans and optionally record executions."""

    for plan_id, handler in zip(
      plan_ids,
      self._generated_runtime.resolve_activity_handlers(plan_ids),
    ):
      handler(self._context)
      if executed_activities is not None:
        executed_activities.append(self._build_executed_activity(plan_id))

  def _build_executed_activity(self, plan_id: str) -> HsmExecutedActivity:
    """Convert one plan ID into snapshot-ready activity metadata."""

    plan = self._generated_runtime.callable_plans_by_id[plan_id]
    owner_scope, owner_id, slot_name, _index = plan_id.split(":", 3)
    return HsmExecutedActivity(
      activity_id=plan.name,
      owner_kind=_resolve_owner_kind(owner_scope, slot_name),
      owner_id=owner_id,
    )

  def _resolve_ancestry(self, state_id: str) -> tuple[str, ...]:
    """Return the root-to-leaf active path for one state ID."""

    active_path: list[str] = []
    current_state_id: str | None = state_id
    while current_state_id is not None:
      active_path.append(current_state_id)
      current_state_id = self._generated_runtime.parent_ids[current_state_id]
    active_path.reverse()
    return tuple(active_path)


def _resolve_owner_kind(owner_scope: str, slot_name: str) -> str:
  """Map internal plan ownership metadata to public snapshot labels."""

  if owner_scope == "state":
    return f"state_{slot_name}"
  if owner_scope in {"external_transition", "internal_transition"}:
    return owner_scope
  if owner_scope == "guard_branch":
    return "guard_branch"
  raise ValueError(f"Unsupported activity owner '{owner_scope}:{slot_name}'.")
