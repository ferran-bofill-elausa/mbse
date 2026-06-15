"""Semantic validation for parsed HSM documents."""

from __future__ import annotations

from mbse.model.hsm.model_types import HsmDocument
from mbse.model.hsm.model_types import HsmGuardBranch
from mbse.model.hsm.model_types import HsmState
from mbse.model.hsm.validation.exceptions import HsmValidationError


def validate_hsm_document_semantics(document: HsmDocument) -> None:
  """Validate cross-reference and structural HSM rules beyond JSON Schema."""

  if document.schema_version != "hsm-v1":
    raise HsmValidationError(
      code="hsm_document.invalid_schema_version",
      message="HSM schema_version must equal 'hsm-v1'.",
    )

  id_registry: set[str] = set()
  state_ids = _collect_state_ids(document.states)
  guard_node_ids = {guard_node.id for guard_node in document.guard_nodes}
  event_ids = {event.id for event in document.events}

  _validate_id(document.document_id, id_registry)

  for variable in document.variables:
    _validate_id(variable.id, id_registry)

  for event in document.events:
    _validate_id(event.id, id_registry)
    parameter_names: set[str] = set()
    for parameter in event.parameters:
      if not parameter.name:
        raise HsmValidationError(
          code="hsm_document.invalid_parameter_name",
          message=f"Event '{event.id}' has an empty parameter name.",
        )
      if parameter.name in parameter_names:
        raise HsmValidationError(
          code="hsm_document.duplicate_parameter_name",
          message=(
            f"Event '{event.id}' has duplicate parameter name '{parameter.name}'."
          ),
        )
      parameter_names.add(parameter.name)

  _validate_states(document.states, id_registry=id_registry, state_ids=state_ids)

  if document.initial is None:
    raise HsmValidationError(
      code="hsm_document.missing_root_initial_transition",
      message="HSM document must declare exactly one root initial_transition.",
    )

  _validate_id(document.initial.id, id_registry)
  _validate_state_reference(
    reference_id=document.initial.target_id,
    state_ids=state_ids,
    code="hsm_document.unknown_state_reference",
    message=(
      f"Initial transition '{document.initial.id}' references unknown "
      f"target state '{document.initial.target_id}'."
    ),
  )

  for transition in document.external_transitions:
    _validate_id(transition.id, id_registry)
    _validate_state_reference(
      reference_id=transition.source_id,
      state_ids=state_ids,
      code="hsm_document.unknown_state_reference",
      message=(
          f"External transition '{transition.id}' references unknown source state "
          f"'{transition.source_id}'."
      ),
    )
    _validate_state_reference(
      reference_id=transition.target_id,
      state_ids=state_ids | guard_node_ids,
      code="hsm_document.unknown_state_reference",
      message=(
          f"External transition '{transition.id}' references unknown target state "
          f"'{transition.target_id}'."
      ),
    )
    if transition.event_id is not None and transition.event_id not in event_ids:
      raise HsmValidationError(
        code="hsm_document.unknown_event_reference",
        message=(
            f"External transition '{transition.id}' references unknown event "
            f"'{transition.event_id}'."
        ),
      )
    if transition.target_id in guard_node_ids:
      if transition.event_id is None:
        raise HsmValidationError(
          code="hsm_document.guard_node_requires_event",
          message=(
            f"External transition '{transition.id}' targeting guard node '{transition.target_id}' "
            "must declare event_id."
          ),
        )
      if transition.activities:
        raise HsmValidationError(
          code="hsm_document.guard_transition_activity_conflict",
          message=(
            f"External transition '{transition.id}' cannot declare activities when using "
            "guard branches; move them to true_branch/false_branch."
          ),
        )

  for guard_node in document.guard_nodes:
    _validate_id(guard_node.id, id_registry)
    _validate_guard_branch(
      guard_node.true_branch,
      guard_node_id=guard_node.id,
      branch_name="true_branch",
      state_ids=state_ids,
    )
    _validate_guard_branch(
      guard_node.false_branch,
      guard_node_id=guard_node.id,
      branch_name="false_branch",
      state_ids=state_ids,
    )

  for transition in document.internal_transitions:
    _validate_id(transition.id, id_registry)
    _validate_state_reference(
      reference_id=transition.source_id,
      state_ids=state_ids,
      code="hsm_document.unknown_state_reference",
      message=(
        f"Internal transition '{transition.id}' references unknown source "
        f"state '{transition.source_id}'."
      ),
    )
    if transition.event_id not in event_ids:
      raise HsmValidationError(
        code="hsm_document.unknown_event_reference",
        message=(
          f"Internal transition '{transition.id}' references unknown event "
          f"'{transition.event_id}'."
        ),
      )


def _validate_states(
  states: tuple[HsmState, ...],
  *,
  id_registry: set[str],
  state_ids: set[str],
) -> None:
  """Validate states recursively, including local initials."""

  for state in states:
    _validate_id(state.id, id_registry)
    if state.initial is not None:
      _validate_id(state.initial.id, id_registry)
      _validate_state_reference(
        reference_id=state.initial.target_id,
        state_ids=state_ids,
        code="hsm_document.unknown_state_reference",
        message=(
          f"State '{state.id}' initial transition references unknown target state "
          f"'{state.initial.target_id}'."
        ),
      )
      descendant_ids = _collect_descendant_ids(state.states)
      if state.initial.target_id not in descendant_ids:
        raise HsmValidationError(
          code="hsm_document.invalid_local_initial_target",
          message=(
            f"State '{state.id}' initial transition target '{state.initial.target_id}' "
            "must reference a descendant state in its subtree."
          ),
        )
    _validate_states(state.states, id_registry=id_registry, state_ids=state_ids)


def _collect_state_ids(states: tuple[HsmState, ...]) -> set[str]:
  """Collect every state id from a state subtree."""

  collected: set[str] = set()
  for state in states:
    collected.add(state.id)
    collected.update(_collect_state_ids(state.states))
  return collected


def _collect_descendant_ids(states: tuple[HsmState, ...]) -> set[str]:
  """Collect every descendant state id from the given child subtree."""

  return _collect_state_ids(states)


def _validate_id(value: str, registry: set[str]) -> None:
  """Require a non-empty id that has not been seen."""

  if not value:
    raise HsmValidationError(
      code="hsm_document.invalid_id",
      message="HSM ids must be non-empty.",
    )
  if value in registry:
    raise HsmValidationError(
      code="hsm_document.duplicate_id",
      message=f"Duplicate HSM id '{value}'.",
    )
  registry.add(value)


def _validate_state_reference(
  *,
  reference_id: str,
  state_ids: set[str],
  code: str,
  message: str,
) -> None:
  """Require a reference id to exist in the allowed state set."""

  if reference_id not in state_ids:
    raise HsmValidationError(code=code, message=message)


def _validate_guard_branch(
  branch: HsmGuardBranch,
  *,
  guard_node_id: str,
  branch_name: str,
  state_ids: set[str],
) -> None:
  """Validate one guard branch target."""

  _validate_state_reference(
    reference_id=branch.target_id,
    state_ids=state_ids,
    code="hsm_document.unknown_state_reference",
    message=(
      f"Guard node '{guard_node_id}' {branch_name} references unknown target state "
      f"'{branch.target_id}'."
    ),
  )


__all__ = ["validate_hsm_document_semantics"]
