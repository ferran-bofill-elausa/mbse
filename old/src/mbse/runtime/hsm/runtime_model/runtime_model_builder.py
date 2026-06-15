from __future__ import annotations

from typing import Mapping

from mbse.model.hsm import HsmCallableRef
from mbse.model.hsm import HsmDocument
from mbse.model.hsm import HsmGuardBranch
from mbse.model.hsm import HsmGuardNode
from mbse.model.hsm import HsmInternalTransition
from mbse.model.hsm import HsmState
from mbse.model.hsm import HsmExternalTransition

from .runtime_model_types import HsmGeneratedRuntimeCallablePlan
from .runtime_model_types import HsmGeneratedRuntimeEventCandidateRow
from .runtime_model_types import HsmGeneratedRuntimeGuardBranchRow
from .runtime_model_types import HsmGeneratedRuntimeView


DEFAULT_EVENT_HANDLER_SLOT_ORDER = (
  "external_transitions",
  "internal_transitions",
)


def derive_event_handler_slot_order(
  machine: Mapping[str, object] | HsmDocument,
) -> tuple[str, ...]:
  """Preserve authored event-handler collection order when available."""

  if isinstance(machine, HsmDocument):
    return DEFAULT_EVENT_HANDLER_SLOT_ORDER

  ordered = _find_authored_event_handler_slot_order(machine)
  missing = tuple(
    key for key in DEFAULT_EVENT_HANDLER_SLOT_ORDER if key not in ordered
  )
  return (*ordered, *missing)


def _find_authored_event_handler_slot_order(
  mapping: Mapping[str, object],
) -> tuple[str, ...]:
  states = mapping.get("states")
  if not isinstance(states, list):
    return ()
  for item in states:
    if not isinstance(item, Mapping):
      continue
    ordered = tuple(
      key for key in item.keys() if key in ("external_transitions", "internal_transitions")
    )
    if ordered:
      return ordered
    nested = _find_authored_event_handler_slot_order(item)
    if nested:
      return nested
  return ()


def prepare_hsm_generated_runtime_view(
  document: HsmDocument,
  *,
  event_handler_slot_order: tuple[str, ...] = DEFAULT_EVENT_HANDLER_SLOT_ORDER,
) -> HsmGeneratedRuntimeView:
  """Compile one validated HSM document into generated runtime metadata."""

  ordered_states = tuple(_flatten_states(document.states))
  state_ids = tuple(state.id for state in ordered_states)
  guard_nodes_by_id = {guard_node.id: guard_node for guard_node in document.guard_nodes}
  parent_ids = _collect_parent_ids(document.states, parent_id=None)
  ancestry_by_state_id = _collect_ancestry_by_state_id(document.states)
  initial_target_ids = _collect_initial_targets(document)
  initial_transition_ids = _collect_initial_transition_ids(document)
  leaf_state_ids = tuple(state.id for state in ordered_states if not state.states)
  callable_plans_by_id: dict[str, HsmGeneratedRuntimeCallablePlan] = {}
  on_initial_plan_ids_by_state_id = {
    state.id: _register_callable_plan_ids(
      state.on_initial,
      callable_plans_by_id,
      owner_scope="state",
      owner_id=state.id,
      slot_name="on_initial",
    )
    for state in ordered_states
  }
  on_entry_plan_ids_by_state_id = {
    state.id: _register_callable_plan_ids(
      state.on_entry,
      callable_plans_by_id,
      owner_scope="state",
      owner_id=state.id,
      slot_name="on_entry",
    )
    for state in ordered_states
  }
  on_exit_plan_ids_by_state_id = {
    state.id: _register_callable_plan_ids(
      state.on_exit,
      callable_plans_by_id,
      owner_scope="state",
      owner_id=state.id,
      slot_name="on_exit",
    )
    for state in ordered_states
  }
  event_candidate_rows_by_state_id = {
    state_id: _collect_event_candidate_rows(
      document,
      state_id,
      guard_nodes_by_id,
      callable_plans_by_id,
      event_handler_slot_order,
    )
    for state_id in state_ids
  }
  return HsmGeneratedRuntimeView(
    document_id=document.document_id,
    state_ids=state_ids,
    parent_ids=parent_ids,
    ancestry_by_state_id=ancestry_by_state_id,
    initial_target_ids=initial_target_ids,
    initial_transition_ids=initial_transition_ids,
    leaf_state_ids=leaf_state_ids,
    callable_plans_by_id=callable_plans_by_id,
    on_initial_plan_ids_by_state_id=on_initial_plan_ids_by_state_id,
    on_entry_plan_ids_by_state_id=on_entry_plan_ids_by_state_id,
    on_exit_plan_ids_by_state_id=on_exit_plan_ids_by_state_id,
    event_candidate_rows_by_state_id=event_candidate_rows_by_state_id,
  )


def _flatten_states(states: tuple[HsmState, ...]) -> list[HsmState]:
  """Return states in depth-first authored order."""

  ordered_states: list[HsmState] = []
  for state in states:
    ordered_states.append(state)
    ordered_states.extend(_flatten_states(state.states))
  return ordered_states


def _collect_parent_ids(
  states: tuple[HsmState, ...],
  *,
  parent_id: str | None,
) -> dict[str, str | None]:
  """Map each state ID to its direct parent ID."""

  parent_ids: dict[str, str | None] = {}
  for state in states:
    parent_ids[state.id] = parent_id
    parent_ids.update(_collect_parent_ids(state.states, parent_id=state.id))
  return parent_ids


def _collect_ancestry_by_state_id(
  states: tuple[HsmState, ...],
  ancestors: tuple[str, ...] = (),
) -> dict[str, tuple[str, ...]]:
  """Map each state ID to its root-to-self ancestry path."""

  ancestry_by_state_id: dict[str, tuple[str, ...]] = {}
  for state in states:
    ancestry = (*ancestors, state.id)
    ancestry_by_state_id[state.id] = ancestry
    ancestry_by_state_id.update(
      _collect_ancestry_by_state_id(state.states, ancestry)
    )
  return ancestry_by_state_id


def _collect_initial_targets(document: HsmDocument) -> dict[str | None, str]:
  """Collect root and local initial target IDs by owner state."""

  initial_target_ids: dict[str | None, str] = {}
  if document.initial is not None:
    initial_target_ids[None] = document.initial.target_id
  for state in _flatten_states(document.states):
    if state.initial is not None:
      initial_target_ids[state.id] = state.initial.target_id
  return initial_target_ids


def _collect_initial_transition_ids(document: HsmDocument) -> dict[str | None, str]:
  """Collect authored initial transition IDs by owner state."""

  initial_transition_ids: dict[str | None, str] = {}
  if document.initial is not None:
    initial_transition_ids[None] = document.initial.id
  for state in _flatten_states(document.states):
    if state.initial is not None:
      initial_transition_ids[state.id] = state.initial.id
  return initial_transition_ids


def _collect_event_candidate_rows(
  document: HsmDocument,
  state_id: str,
  guard_nodes_by_id: dict[str, HsmGuardNode],
  callable_plans_by_id: dict[str, HsmGeneratedRuntimeCallablePlan],
  event_handler_slot_order: tuple[str, ...],
) -> tuple[HsmGeneratedRuntimeEventCandidateRow, ...]:
  """Build ordered event candidates for one source state."""

  rows: list[HsmGeneratedRuntimeEventCandidateRow] = []
  for collection_name in event_handler_slot_order:
    if collection_name == "internal_transitions":
      rows.extend(
        _build_internal_candidate_row(
          transition,
          callable_plans_by_id,
        )
        for transition in document.internal_transitions
        if transition.source_id == state_id
      )
      continue
    rows.extend(
      _build_external_transition_candidate_row(
        transition,
        guard_nodes_by_id,
        callable_plans_by_id,
      )
      for transition in document.external_transitions
      if transition.source_id == state_id and transition.event_id is not None
    )
  return tuple(rows)


def _build_internal_candidate_row(
  transition: HsmInternalTransition,
  callable_plans_by_id: dict[str, HsmGeneratedRuntimeCallablePlan],
) -> HsmGeneratedRuntimeEventCandidateRow:
  """Convert one internal transition into a generated runtime candidate row."""

  return HsmGeneratedRuntimeEventCandidateRow(
    candidate_id=transition.id,
    event_id=transition.event_id,
    source_id=transition.source_id,
    kind="internal",
    activity_plan_ids=_register_callable_plan_ids(
      transition.activities,
      callable_plans_by_id,
      owner_scope="internal_transition",
      owner_id=transition.id,
      slot_name="activities",
    ),
  )


def _build_external_transition_candidate_row(
  transition: HsmExternalTransition,
  guard_nodes_by_id: dict[str, HsmGuardNode],
  callable_plans_by_id: dict[str, HsmGeneratedRuntimeCallablePlan],
) -> HsmGeneratedRuntimeEventCandidateRow:
  """Convert one authored external transition into a runtime candidate row."""

  if transition.target_id in guard_nodes_by_id:
    return _build_guard_node_external_transition_candidate_row(
      transition,
      guard_nodes_by_id[transition.target_id],
      callable_plans_by_id,
    )
  return HsmGeneratedRuntimeEventCandidateRow(
    candidate_id=transition.id,
    event_id=transition.event_id or "",
    source_id=transition.source_id,
    kind="external_transition",
    target_id=transition.target_id,
    activity_plan_ids=_register_callable_plan_ids(
      transition.activities,
      callable_plans_by_id,
      owner_scope="external_transition",
      owner_id=transition.id,
      slot_name="activities",
    ),
  )


def _build_guard_node_external_transition_candidate_row(
  transition: HsmExternalTransition,
  guard_node: HsmGuardNode,
  callable_plans_by_id: dict[str, HsmGeneratedRuntimeCallablePlan],
) -> HsmGeneratedRuntimeEventCandidateRow:
  """Convert a guard-targeting transition into a guard-aware runtime row."""

  guard_plan_id = _register_callable_plan(
    guard_node.guard,
    callable_plans_by_id,
    owner_scope="guard_node",
    owner_id=guard_node.id,
    slot_name="guard",
    index=0,
  )
  return HsmGeneratedRuntimeEventCandidateRow(
    candidate_id=transition.id,
    event_id=transition.event_id or "",
    source_id=transition.source_id,
    kind="external_transition",
    target_id=guard_node.id,
    guard_plan_id=guard_plan_id,
    guard_node_id=guard_node.id,
    guard_true_branch=_build_guard_branch_row(
      guard_node.id,
      "true",
      guard_node.true_branch,
      callable_plans_by_id,
    ),
    guard_false_branch=_build_guard_branch_row(
      guard_node.id,
      "false",
      guard_node.false_branch,
      callable_plans_by_id,
    ),
  )


def _build_guard_branch_row(
  guard_node_id: str,
  outcome: str,
  branch: HsmGuardBranch,
  callable_plans_by_id: dict[str, HsmGeneratedRuntimeCallablePlan],
) -> HsmGeneratedRuntimeGuardBranchRow:
  """Convert one guard branch into generated runtime target metadata."""

  return HsmGeneratedRuntimeGuardBranchRow(
    branch_id=_guard_branch_id(guard_node_id, outcome),
    target_id=branch.target_id,
    activity_plan_ids=_register_callable_plan_ids(
      branch.activities,
      callable_plans_by_id,
      owner_scope="guard_branch",
      owner_id=f"{guard_node_id}_{outcome}",
      slot_name="activities",
    ),
  )


def _guard_branch_id(guard_node_id: str, outcome: str) -> str:
  """Build the stable synthetic ID for one guard branch."""

  return f"{guard_node_id}_{outcome}"


def _register_callable_plan_ids(
  refs: tuple[HsmCallableRef, ...],
  callable_plans_by_id: dict[str, HsmGeneratedRuntimeCallablePlan],
  *,
  owner_scope: str,
  owner_id: str,
  slot_name: str,
) -> tuple[str, ...]:
  """Register one ordered callable-plan ID tuple for a slot."""

  return tuple(
    _register_callable_plan(
      ref,
      callable_plans_by_id,
      owner_scope=owner_scope,
      owner_id=owner_id,
      slot_name=slot_name,
      index=index,
    )
    for index, ref in enumerate(refs)
  )


def _register_callable_plan(
  ref: HsmCallableRef,
  callable_plans_by_id: dict[str, HsmGeneratedRuntimeCallablePlan],
  *,
  owner_scope: str,
  owner_id: str,
  slot_name: str,
  index: int,
) -> str:
  """Register one callable plan and return its stable plan ID."""

  plan_id = f"{owner_scope}:{owner_id}:{slot_name}:{index}"
  callable_plans_by_id.setdefault(
    plan_id,
    HsmGeneratedRuntimeCallablePlan(
      plan_id=plan_id,
      module=ref.module,
      name=ref.name,
    ),
  )
  return plan_id
