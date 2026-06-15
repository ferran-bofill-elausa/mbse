from __future__ import annotations


def hsm_document(
  document_id: str,
  *,
  states: list[dict[str, object]],
  initial_transition: dict[str, str],
  variables: list[dict[str, object]] | None = None,
  events: list[dict[str, object]] | None = None,
) -> dict[str, object]:
  return {
    "schema_version": "hsm-v1",
    "document_id": document_id,
    "variables": variables or [],
    "events": events or [],
    "initial_transition": initial_transition,
    "states": states,
  }


def hsm_initial(transition_id: str, target_id: str) -> dict[str, str]:
  return {"id": transition_id, "target_id": target_id}


def hsm_guard_branch(
  target_id: str,
  *,
  activities: list[dict[str, str]] | None = None,
) -> dict[str, object]:
  branch: dict[str, object] = {"target_id": target_id}
  if activities is not None:
    branch["activities"] = activities
  return branch


def hsm_guard(
  *,
  guard: dict[str, str],
  true_branch: dict[str, object],
  false_branch: dict[str, object],
  guard_id: str | None = None,
) -> dict[str, object]:
  payload: dict[str, object] = {
    "guard": guard,
    "true_branch": true_branch,
    "false_branch": false_branch,
  }
  if guard_id is not None:
    payload["id"] = guard_id
  return payload


def hsm_external_transition(
  transition_id: str,
  *,
  target_id: str | None = None,
  event_id: str | None = None,
  activities: list[dict[str, str]] | None = None,
  guard: dict[str, object] | None = None,
) -> dict[str, object]:
  transition: dict[str, object] = {"id": transition_id}
  if target_id is not None:
    transition["target_id"] = target_id
  if event_id is not None:
    transition["event_id"] = event_id
  if activities is not None:
    transition["activities"] = activities
  if guard is not None:
    transition["guard"] = guard
  return transition


def hsm_internal_transition(
  transition_id: str,
  *,
  event_id: str,
  activities: list[dict[str, str]] | None = None,
) -> dict[str, object]:
  transition: dict[str, object] = {
    "id": transition_id,
    "event_id": event_id,
  }
  if activities is not None:
    transition["activities"] = activities
  return transition


def hsm_state(
  state_id: str,
  *,
  label: str | None = None,
  states: list[dict[str, object]] | None = None,
  on_initial: list[dict[str, str]] | None = None,
  on_entry: list[dict[str, str]] | None = None,
  on_exit: list[dict[str, str]] | None = None,
  initial_transition: dict[str, str] | None = None,
  external_transitions: list[dict[str, object]] | None = None,
  internal_transitions: list[dict[str, object]] | None = None,
) -> dict[str, object]:
  state: dict[str, object] = {
    "id": state_id,
    "states": states or [],
    "hooks": {
      "on_initial": on_initial or [],
      "on_entry": on_entry or [],
      "on_exit": on_exit or [],
    },
    "external_transitions": external_transitions or [],
    "internal_transitions": internal_transitions or [],
  }
  if label is not None:
    state["label"] = label
  if initial_transition is not None:
    state["initial_transition"] = initial_transition
  return state
