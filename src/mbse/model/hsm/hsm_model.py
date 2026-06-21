"""Minimal HSM JSON model loading, validation, and query helpers."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


_HSM_MODEL_SCHEMA_PATH = Path(__file__).with_name("hsm_model.json")


@dataclass(frozen=True)
class HsmInitialTransitionRelation:
  """One root or local initial transition relation in the authored model."""

  source_state_id: str | None
  target_state_id: str


@dataclass(frozen=True)
class HsmExternalTransitionRelation:
  """One authored unguarded external transition between two states."""

  source_state_id: str
  event_id: str
  target_state_id: str
  activities: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class HsmGuardedTransitionBranchRelation:
  """One authored guarded branch relation for one boolean guard result."""

  source_state_id: str
  event_id: str
  guard_result: bool
  target_state_id: str
  guard_activity: dict[str, str]
  transition_activities: tuple[dict[str, str], ...]
  branch_activities: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class HsmRelatedState:
  """One related state together with the state-owned elements relevant for focus."""

  state_id: str
  on_entry_activities: tuple[dict[str, str], ...]
  on_initial_activities: tuple[dict[str, str], ...]
  on_exit_activities: tuple[dict[str, str], ...]
  internal_transitions: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class HsmStateRelatedElements:
  """All HSM elements semantically related to one state during execution.

  Related means:
  - the state itself
  - all ancestor states that may receive bubbled-up events from that state
  - every initial-transition chain that can eventually enter the state from root or one
    of those ancestor states
  - outgoing external transitions from the state or one of its ancestors, including
    guarded branches and their target states
  - incoming external transitions that target the state directly or target one of its
    ancestors when that ancestor can reach the state through an initial-transition chain
  - incoming guarded branches that target the state directly or target one of its
    ancestors when that ancestor can reach the state through an initial-transition chain
  - all source and target states directly involved in the transition and branch
    relations described above
  """

  states: tuple[HsmRelatedState, ...]
  initial_entry_chains: tuple[tuple[HsmInitialTransitionRelation, ...], ...]
  outgoing_external_transitions: tuple[HsmExternalTransitionRelation, ...]
  incoming_external_transitions: tuple[HsmExternalTransitionRelation, ...]
  guarded_transition_branches: tuple[HsmGuardedTransitionBranchRelation, ...]


class HsmModel:
  """Authored HSM model plus read-only structural queries."""

  def __init__(self, model: dict[str, Any]) -> None:
    """HsmModel initialization."""

    self.document = model

  @classmethod
  def load(cls, modelPath: str | Path) -> HsmModel:
    """Load an HSM model JSON file."""

    with Path(modelPath).open("r", encoding="utf-8") as modelFile:
      return cls(json.load(modelFile))

  @staticmethod
  def validate(model: dict[str, Any]) -> None:
    """Validate an HSM model dictionary against the JSON Schema."""

    with _HSM_MODEL_SCHEMA_PATH.open("r", encoding="utf-8") as schemaFile:
      schema = json.load(schemaFile)

    Draft202012Validator(schema).validate(model)

  @classmethod
  def loadAndValidate(cls, modelPath: str | Path) -> HsmModel:
    """Load and validate an HSM model JSON file."""

    model = cls.load(modelPath)
    cls.validate(model.document)
    return model

  def getDocumentId(self) -> str:
    """Return the authored document id."""

    return self.document["document_id"]

  def getSchemaVersion(self) -> str:
    """Return the authored schema version."""

    return self.document["schema_version"]

  def getEnums(self) -> list[dict[str, Any]]:
    """Return the authored global enum declarations."""

    return self.document.get("enums", [])

  def getEnumById(self, enum_id: str) -> dict[str, Any]:
    """Return one global enum declaration by id."""

    for enum in self.getEnums():
      if enum["id"] == enum_id:
        return enum

    raise KeyError(f"Unknown enum_id '{enum_id}'.")

  def getEnumValues(self, enum_id: str) -> list[str]:
    """Return the declared values for one global enum."""

    return self.getEnumById(enum_id)["values"]

  def getVariables(self) -> list[dict[str, Any]]:
    """Return the authored variable declarations."""

    return self.document.get("variables", [])

  def getVariableByName(self, name: str) -> dict[str, Any]:
    """Return one variable declaration by name."""

    for variable in self.getVariables():
      if variable["name"] == name:
        return variable

    raise KeyError(f"Unknown variable name '{name}'.")

  def getVariableDefaultValue(self, name: str) -> Any:
    """Return the authored default value for one variable."""

    return self.getVariableByName(name)["default_value"]

  def getEvents(self) -> list[dict[str, Any]]:
    """Return the authored event declarations."""

    return self.document["events"]

  def getEventById(self, event_id: str) -> dict[str, Any]:
    """Return one event declaration by id."""

    for event in self.document["events"]:
      if event["id"] == event_id:
        return event

    raise KeyError(f"Unknown event_id '{event_id}'.")

  def getEventParameters(self, event_id: str) -> list[dict[str, Any]]:
    """Return the authored parameters for one event."""

    return self.getEventById(event_id).get("parameters", [])

  def getEventParameterByName(
    self,
    event_id: str,
    parameter_name: str,
  ) -> dict[str, Any]:
    """Return one authored event parameter declaration by name."""

    for parameter in self.getEventParameters(event_id):
      if parameter["name"] == parameter_name:
        return parameter

    raise KeyError(
      f"Unknown parameter name '{parameter_name}' for event_id '{event_id}'."
    )

  def getStates(self) -> list[dict[str, Any]]:
    """Return the authored top-level states."""

    return self.document["states"]

  def iterStates(self) -> Iterator[dict[str, Any]]:
    """Iterate states depth-first across the whole model."""

    yield from self._iterStates(self.getStates())

  def getStateById(self, state_id: str) -> dict[str, Any]:
    """Return one state by id."""

    for state in self.iterStates():
      if state["id"] == state_id:
        return state

    raise KeyError(f"Unknown state_id '{state_id}'.")

  def getStateLabel(self, state_id: str) -> str:
    """Return the authored label for one state."""

    return self.getStateById(state_id)["label"]

  def getParentStateId(self, state_id: str) -> str | None:
    """Return the direct parent state id for one state."""

    pending_states: list[tuple[dict[str, Any], str | None]] = [
      (state, None)
      for state in self.getStates()
    ]

    while pending_states:
      state, parent_state_id = pending_states.pop(0)
      if state["id"] == state_id:
        return parent_state_id

      child_states = state.get("states", [])
      pending_states[0:0] = [
        (child_state, state["id"])
        for child_state in child_states
      ]

    raise KeyError(f"Unknown state_id '{state_id}'.")

  def getParentStateIds(self, state_id: str) -> tuple[str, ...]:
    """Return all ancestor state ids from direct parent up to the root."""

    parent_state_ids: list[str] = []
    parent_state_id = self.getParentStateId(state_id)
    while parent_state_id is not None:
      parent_state_ids.append(parent_state_id)
      parent_state_id = self.getParentStateId(parent_state_id)
    return tuple(parent_state_ids)

  def getChildStates(self, state_id: str) -> list[dict[str, Any]]:
    """Return the direct child states of one state."""

    return self.getStateById(state_id).get("states", [])

  def getStateHooks(self, state_id: str) -> dict[str, list[dict[str, str]]]:
    """Return the authored hooks dictionary for one state."""

    return self.getStateById(state_id).get("hooks", {})

  def getStateOnEntry(self, state_id: str) -> list[dict[str, str]]:
    """Return the authored on_entry hooks for one state."""

    return self.getStateHooks(state_id).get("on_entry", [])

  def getStateOnInitial(self, state_id: str) -> list[dict[str, str]]:
    """Return the authored on_initial hooks for one state."""

    return self.getStateHooks(state_id).get("on_initial", [])

  def getStateOnExit(self, state_id: str) -> list[dict[str, str]]:
    """Return the authored on_exit hooks for one state."""

    return self.getStateHooks(state_id).get("on_exit", [])

  def hasStateInitialTransition(self, state_id: str) -> bool:
    """Return whether one state declares a local initial transition."""

    return "initial_transition" in self.getStateById(state_id)

  def getStateInitialTransition(self, state_id: str) -> dict[str, Any]:
    """Return the authored local initial transition for one state."""

    return self.getStateById(state_id)["initial_transition"]

  def getStateInitialTargetId(self, state_id: str) -> str:
    """Return the local initial transition target id for one state."""

    return self.getStateInitialTransition(state_id)["target_id"]

  def getRootInitialTransition(self) -> dict[str, Any]:
    """Return the authored root initial transition."""

    return self.document["initial_transition"]

  def getRootInitialTargetId(self) -> str:
    """Return the authored root initial target id."""

    return self.getRootInitialTransition()["target_id"]

  def getStateInternalTransitions(self, state_id: str) -> list[dict[str, Any]]:
    """Return the authored internal transitions for one state."""

    return self.getStateById(state_id).get("internal_transitions", [])

  def findInternalTransition(
    self,
    state_id: str,
    event_id: str,
  ) -> dict[str, Any] | None:
    """Return the first matching internal transition for one state and event."""

    for transition in self.getStateInternalTransitions(state_id):
      if transition["event_id"] == event_id:
        return transition

    return None

  def getOutgoingExternalTransitions(self, state_id: str) -> list[dict[str, Any]]:
    """Return all authored outgoing external transitions for one state."""

    return self.getStateById(state_id).get("external_transitions", [])

  def findExternalTransition(
    self,
    state_id: str,
    event_id: str,
  ) -> dict[str, Any] | None:
    """Return the first matching external transition for one state and event."""

    for transition in self.getOutgoingExternalTransitions(state_id):
      if transition["event_id"] == event_id:
        return transition

    return None

  def getIncomingExternalTransitions(
    self,
    target_state_id: str,
  ) -> tuple[HsmExternalTransitionRelation, ...]:
    """Return unguarded external transitions that target one state directly."""

    incoming_transitions: list[HsmExternalTransitionRelation] = []
    for state in self.iterStates():
      source_state_id = state["id"]
      for transition in self.getOutgoingExternalTransitions(source_state_id):
        if transition.get("guard_condition") is not None:
          continue
        if transition["target_id"] != target_state_id:
          continue
        incoming_transitions.append(
          HsmExternalTransitionRelation(
            source_state_id=source_state_id,
            event_id=transition["event_id"],
            target_state_id=target_state_id,
            activities=tuple(transition.get("activities", [])),
          )
        )
    return tuple(incoming_transitions)

  def getGuardedTransitionBranches(
    self,
    source_state_id: str,
    event_id: str,
  ) -> tuple[HsmGuardedTransitionBranchRelation, ...]:
    """Return both true/false branch relations for guarded transitions of one state/event."""

    branches: list[HsmGuardedTransitionBranchRelation] = []
    for transition in self.getOutgoingExternalTransitions(source_state_id):
      if transition["event_id"] != event_id:
        continue
      guard_condition = transition.get("guard_condition")
      if guard_condition is None:
        continue
      for outcome, branch_key in ((True, "true_branch"), (False, "false_branch")):
        branch = guard_condition[branch_key]
        branches.append(
          HsmGuardedTransitionBranchRelation(
            source_state_id=source_state_id,
            event_id=event_id,
            target_state_id=branch["target_id"],
            guard_result=outcome,
            guard_activity=guard_condition["guard_activity"],
            transition_activities=tuple(transition.get("activities", [])),
            branch_activities=tuple(branch.get("activities", [])),
          )
        )
    return tuple(branches)

  def getInitialEntryChainsToState(
    self,
    state_id: str,
  ) -> tuple[tuple[HsmInitialTransitionRelation, ...], ...]:
    """Return every initial-transition chain that can eventually enter one state."""

    chains: list[tuple[HsmInitialTransitionRelation, ...]] = []
    for source_state_id in (None, *self.getParentStateIds(state_id)):
      chain = self._buildInitialEntryChain(source_state_id, state_id)
      if chain is not None:
        chains.append(chain)
    return tuple(chains)

  def getStateRelatedElements(self, state_id: str) -> HsmStateRelatedElements:
    """Return all model elements semantically related to one state during execution.

    Related means:
    - the state itself
    - all ancestor states that may receive bubbled-up events from that state
    - every initial-transition chain that can eventually enter the state from root or
      one of those ancestor states
    - outgoing external transitions from the state or one of its ancestors, including
      guarded branches and their target states
    - incoming external transitions that target the state directly or target one of its
      ancestors when that ancestor can reach the state through an initial-transition chain
    - incoming guarded branches with the same ancestor-entry semantics
    """

    relevant_source_state_ids = (state_id, *self.getParentStateIds(state_id))
    initial_entry_chains = self.getInitialEntryChainsToState(state_id)
    ancestor_entry_state_ids = tuple(
      chain[0].source_state_id
      for chain in initial_entry_chains
      if chain[0].source_state_id is not None
    )
    relevant_entry_state_ids = tuple(dict.fromkeys((state_id, *ancestor_entry_state_ids)))

    related_state_ids: list[str] = [state_id, *self.getParentStateIds(state_id)]
    outgoing_external_transitions: list[HsmExternalTransitionRelation] = []
    incoming_external_transitions: list[HsmExternalTransitionRelation] = []
    guarded_transition_branches: list[HsmGuardedTransitionBranchRelation] = []

    for source_state_id in relevant_source_state_ids:
      for transition in self.getOutgoingExternalTransitions(source_state_id):
        if transition.get("guard_condition") is None:
          relation = HsmExternalTransitionRelation(
            source_state_id=source_state_id,
            event_id=transition["event_id"],
            target_state_id=transition["target_id"],
            activities=tuple(transition.get("activities", [])),
          )
          outgoing_external_transitions.append(relation)
          related_state_ids.append(relation.target_state_id)
          continue

        for branch in self.getGuardedTransitionBranches(source_state_id, transition["event_id"]):
          guarded_transition_branches.append(branch)
          related_state_ids.append(branch.target_state_id)

    for entry_state_id in relevant_entry_state_ids:
      for relation in self.getIncomingExternalTransitions(entry_state_id):
        incoming_external_transitions.append(relation)
        related_state_ids.append(relation.source_state_id)

      for candidate_state in self.iterStates():
        candidate_state_id = candidate_state["id"]
        for transition in self.getOutgoingExternalTransitions(candidate_state_id):
          if transition.get("guard_condition") is None:
            continue
          for branch in self.getGuardedTransitionBranches(
            candidate_state_id,
            transition["event_id"],
          ):
            if branch.target_state_id != entry_state_id:
              continue
            guarded_transition_branches.append(branch)
            related_state_ids.append(branch.source_state_id)

    unique_related_state_ids = tuple(dict.fromkeys(related_state_ids))
    return HsmStateRelatedElements(
      states=tuple(
        HsmRelatedState(
          state_id=related_state_id,
          on_entry_activities=tuple(self.getStateOnEntry(related_state_id)),
          on_initial_activities=tuple(self.getStateOnInitial(related_state_id)),
          on_exit_activities=tuple(self.getStateOnExit(related_state_id)),
          internal_transitions=tuple(self.getStateInternalTransitions(related_state_id)),
        )
        for related_state_id in unique_related_state_ids
      ),
      initial_entry_chains=initial_entry_chains,
      outgoing_external_transitions=self._uniqueExternalTransitionRelations(
        outgoing_external_transitions
      ),
      incoming_external_transitions=self._uniqueExternalTransitionRelations(
        incoming_external_transitions
      ),
      guarded_transition_branches=self._uniqueGuardedTransitionBranchRelations(
        guarded_transition_branches
      ),
    )

  def _iterStates(self, states: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    """Yield one state list recursively in depth-first order."""

    for state in states:
      yield state
      yield from self._iterStates(state.get("states", []))

  def _buildInitialEntryChain(
    self,
    source_state_id: str | None,
    target_state_id: str,
  ) -> tuple[HsmInitialTransitionRelation, ...] | None:
    """Return one initial-transition chain from one entry point to one target state."""

    if source_state_id is None:
      current_target_state_id = self.getRootInitialTargetId()
    else:
      if not self.hasStateInitialTransition(source_state_id):
        return None
      current_target_state_id = self.getStateInitialTargetId(source_state_id)

    chain: list[HsmInitialTransitionRelation] = [
      HsmInitialTransitionRelation(
        source_state_id=source_state_id,
        target_state_id=current_target_state_id,
      )
    ]
    while current_target_state_id != target_state_id:
      if not self.hasStateInitialTransition(current_target_state_id):
        return None
      source_state_id = current_target_state_id
      current_target_state_id = self.getStateInitialTargetId(source_state_id)
      chain.append(
        HsmInitialTransitionRelation(
          source_state_id=source_state_id,
          target_state_id=current_target_state_id,
        )
      )
    return tuple(chain)

  def _uniqueExternalTransitionRelations(
    self,
    relations: list[HsmExternalTransitionRelation],
  ) -> tuple[HsmExternalTransitionRelation, ...]:
    """Return external transition relations deduplicated by structural key."""

    unique_relations: list[HsmExternalTransitionRelation] = []
    seen_keys: set[tuple[str, str, str]] = set()
    for relation in relations:
      key = (
        relation.source_state_id,
        relation.event_id,
        relation.target_state_id,
      )
      if key in seen_keys:
        continue
      seen_keys.add(key)
      unique_relations.append(relation)
    return tuple(unique_relations)

  def _uniqueGuardedTransitionBranchRelations(
    self,
    relations: list[HsmGuardedTransitionBranchRelation],
  ) -> tuple[HsmGuardedTransitionBranchRelation, ...]:
    """Return guarded branch relations deduplicated by structural key."""

    unique_relations: list[HsmGuardedTransitionBranchRelation] = []
    seen_keys: set[tuple[str, str, bool, str]] = set()
    for relation in relations:
      key = (
        relation.source_state_id,
        relation.event_id,
        relation.guard_result,
        relation.target_state_id,
      )
      if key in seen_keys:
        continue
      seen_keys.add(key)
      unique_relations.append(relation)
    return tuple(unique_relations)
