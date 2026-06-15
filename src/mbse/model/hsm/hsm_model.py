"""Minimal HSM JSON model loading, validation, and query helpers."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


_HSM_MODEL_SCHEMA_PATH = Path(__file__).with_name("hsm_model.json")


class HsmModel:
  """Authored HSM model plus read-only structural queries."""

  def __init__(self, model: dict[str, Any]) -> None:
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

  def getVariables(self) -> list[dict[str, Any]]:
    """Return the authored variable declarations."""

    return self.document["variables"]

  def getVariableByName(self, name: str) -> dict[str, Any]:
    """Return one variable declaration by name."""

    for variable in self.document["variables"]:
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

    return None

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

  def getStateExternalTransitions(self, state_id: str) -> list[dict[str, Any]]:
    """Return the authored external transitions for one state."""

    return self.getStateById(state_id).get("external_transitions", [])

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

  def findExternalTransition(
    self,
    state_id: str,
    event_id: str,
  ) -> dict[str, Any] | None:
    """Return the first matching external transition for one state and event."""

    for transition in self.getStateExternalTransitions(state_id):
      if transition["event_id"] == event_id:
        return transition

    return None

  def _iterStates(self, states: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    for state in states:
      yield state
      yield from self._iterStates(state.get("states", []))
