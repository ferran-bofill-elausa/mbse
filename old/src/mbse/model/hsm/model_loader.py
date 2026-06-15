"""HSM document loading and validation entry points."""

from __future__ import annotations

import re

from jsonschema import Draft202012Validator

from mbse.model.hsm.json_schema.schema_loader import load_hsm_schema
from mbse.model.hsm.model_types import HsmCallableRef
from mbse.model.hsm.model_types import HsmDocument
from mbse.model.hsm.model_types import HsmEvent
from mbse.model.hsm.model_types import HsmEventParameter
from mbse.model.hsm.model_types import HsmGuardBranch
from mbse.model.hsm.model_types import HsmGuardNode
from mbse.model.hsm.model_types import HsmInitialTransition
from mbse.model.hsm.model_types import HsmInternalTransition
from mbse.model.hsm.model_types import HsmState
from mbse.model.hsm.model_types import HsmExternalTransition
from mbse.model.hsm.model_types import HsmVariable
from mbse.model.hsm.validation.callable_reference_validation import validate_hsm_document_callables
from mbse.model.hsm.validation.exceptions import HsmValidationError
from mbse.model.hsm.validation.callable_reference_validation import validate_parsed_callable_ref
from mbse.model.hsm.validation.semantic_validation import validate_hsm_document_semantics


UNEXPECTED_PROPERTY_PATTERN = re.compile(r"\('([^']+)' was unexpected\)")
REQUIRED_PROPERTY_PATTERN = re.compile(r"'([^']+)' is a required property")


def load_hsm_document(payload: dict[str, object]) -> HsmDocument:
  """Load one HSM JSON payload into the validated model dataclasses."""

  _require_mapping(payload, path="")
  _validate_hsm_payload_schema(payload)

  external_transitions: list[HsmExternalTransition] = []
  guard_nodes: list[HsmGuardNode] = []
  internal_transitions: list[HsmInternalTransition] = []

  document = HsmDocument(
    schema_version=_require_string(payload, "schema_version", path="schema_version"),
    document_id=_require_string(payload, "document_id", path="document_id"),
    variables=tuple(
      _parse_variable(item, index)
      for index, item in enumerate(_require_list(payload, "variables", path="variables"))
    ),
    events=tuple(
      _parse_event(item, index)
      for index, item in enumerate(_require_list(payload, "events", path="events"))
    ),
    states=tuple(
      _parse_state(
        item,
        path=f"states[{index}]",
        external_transitions=external_transitions,
        guard_nodes=guard_nodes,
        internal_transitions=internal_transitions,
      )
      for index, item in enumerate(_require_list(payload, "states", path="states"))
    ),
    initial=_parse_initial(payload["initial_transition"], path="initial_transition"),
    external_transitions=tuple(external_transitions),
    guard_nodes=tuple(guard_nodes),
    internal_transitions=tuple(internal_transitions),
  )
  validate_hsm_document(document)
  return document


def validate_hsm_document(document: HsmDocument) -> None:
  """Run semantic and callable validation on a parsed HSM document."""

  validate_hsm_document_semantics(document)
  validate_hsm_document_callables(document)


def _parse_variable(payload: object, index: int) -> HsmVariable:
  """Build one declared variable from the raw payload entry."""

  path = f"variables[{index}]"
  mapping = _require_mapping(payload, path=path)
  return HsmVariable(
    id=_require_string(mapping, "id", path=f"{path}.id"),
    default=mapping["default"],
  )


def _parse_event(payload: object, index: int) -> HsmEvent:
  """Build one event definition from the raw payload entry."""

  path = f"events[{index}]"
  mapping = _require_mapping(payload, path=path)
  parameters_payload = mapping.get("parameters", [])
  parameters = tuple(
    _parse_event_parameter(item, event_path=path, index=parameter_index)
    for parameter_index, item in enumerate(
      _require_list_value(parameters_payload, path=f"{path}.parameters")
    )
  )
  return HsmEvent(
    id=_require_string(mapping, "id", path=f"{path}.id"),
    parameters=parameters,
  )


def _parse_event_parameter(
  payload: object,
  event_path: str,
  index: int,
) -> HsmEventParameter:
  """Build one event parameter from the raw payload entry."""

  path = f"{event_path}.parameters[{index}]"
  mapping = _require_mapping(payload, path=path)
  return HsmEventParameter(name=_require_string(mapping, "name", path=f"{path}.name"))


def _parse_state(
  payload: object,
  path: str,
  *,
  external_transitions: list[HsmExternalTransition],
  guard_nodes: list[HsmGuardNode],
  internal_transitions: list[HsmInternalTransition],
) -> HsmState:
  """Build one state subtree from the raw payload entry."""

  mapping = _require_mapping(payload, path=path)
  state_id = _require_string(mapping, "id", path=f"{path}.id")
  states_payload = _require_list(mapping, "states", path=f"{path}.states")
  hooks = _require_mapping(mapping["hooks"], path=f"{path}.hooks")
  on_initial = _parse_callable_ref_list(
    hooks["on_initial"],
    path=f"{path}.hooks.on_initial",
  )
  on_entry = _parse_callable_ref_list(
    hooks["on_entry"],
    path=f"{path}.hooks.on_entry",
  )
  on_exit = _parse_callable_ref_list(
    hooks["on_exit"],
    path=f"{path}.hooks.on_exit",
  )
  child_states = tuple(
    _parse_state(
      item,
      path=f"{path}.states[{index}]",
      external_transitions=external_transitions,
      guard_nodes=guard_nodes,
      internal_transitions=internal_transitions,
    )
    for index, item in enumerate(states_payload)
  )
  authored_external_transitions = _require_list(
    mapping,
    "external_transitions",
    path=f"{path}.external_transitions",
  )
  external_transitions.extend(
    _parse_external_transition(
      item,
      source_id=state_id,
      path=f"{path}.external_transitions[{index}]",
      guard_nodes=guard_nodes,
    )
    for index, item in enumerate(authored_external_transitions)
  )
  authored_internal_transitions = _require_list(
    mapping,
    "internal_transitions",
    path=f"{path}.internal_transitions",
  )
  internal_transitions.extend(
    _parse_internal_transition(
      item,
      source_id=state_id,
      path=f"{path}.internal_transitions[{index}]",
    )
    for index, item in enumerate(authored_internal_transitions)
  )
  return HsmState(
    id=state_id,
    label=_optional_string(mapping.get("label"), path=f"{path}.label"),
    states=child_states,
    on_initial=on_initial,
    on_entry=on_entry,
    on_exit=on_exit,
    initial=(
      _parse_initial(mapping["initial_transition"], path=f"{path}.initial_transition")
      if mapping.get("initial_transition") is not None
      else None
    ),
  )


def _parse_initial(payload: object, path: str) -> HsmInitialTransition:
  """Build one structural initial transition from the raw payload entry."""

  mapping = _require_mapping(payload, path=path)
  return HsmInitialTransition(
    id=_require_string(mapping, "id", path=f"{path}.id"),
    target_id=_require_string(mapping, "target_id", path=f"{path}.target_id"),
  )


def _parse_external_transition(
  payload: object,
  *,
  source_id: str,
  path: str,
  guard_nodes: list[HsmGuardNode],
) -> HsmExternalTransition:
  """Build one external transition from the authored state-local payload."""

  mapping = _require_mapping(payload, path=path)
  event_id = mapping.get("event_id")
  activities = _parse_callable_ref_list(
    mapping.get("activities", []),
    path=f"{path}.activities",
  )
  guard_payload = mapping.get("guard")
  target_id: str
  if guard_payload is not None:
    if activities:
      transition_id = _require_string(mapping, "id", path=f"{path}.id")
      raise HsmValidationError(
        code="hsm_document.guard_transition_activity_conflict",
        message=(
          f"External transition '{transition_id}' cannot declare activities when using "
          "guard branches; move them to true_branch/false_branch."
        ),
      )
    guard_node = _parse_embedded_guard(
      guard_payload,
      transition_id=_require_string(mapping, "id", path=f"{path}.id"),
      path=f"{path}.guard",
    )
    guard_nodes.append(guard_node)
    target_id = guard_node.id
  else:
    target_id = _require_string(mapping, "target_id", path=f"{path}.target_id")
  return HsmExternalTransition(
    id=_require_string(mapping, "id", path=f"{path}.id"),
    source_id=source_id,
    target_id=target_id,
    event_id=_optional_string(event_id, path=f"{path}.event_id"),
    activities=activities,
  )


def _parse_internal_transition(
  payload: object,
  *,
  source_id: str,
  path: str,
) -> HsmInternalTransition:
  """Build one internal transition from the raw payload entry."""

  mapping = _require_mapping(payload, path=path)
  activities = _parse_callable_ref_list(
    mapping.get("activities", []),
    path=f"{path}.activities",
  )
  return HsmInternalTransition(
    id=_require_string(mapping, "id", path=f"{path}.id"),
    source_id=source_id,
    event_id=_require_string(mapping, "event_id", path=f"{path}.event_id"),
    activities=activities,
  )


def _parse_embedded_guard(
  payload: object,
  *,
  transition_id: str,
  path: str,
) -> HsmGuardNode:
  """Normalize one embedded external-transition guard into the stable guard-node model."""

  mapping = _require_mapping(payload, path=path)
  return HsmGuardNode(
    id=_optional_string(mapping.get("id"), path=f"{path}.id")
    or _derived_guard_node_id(transition_id),
    guard=_parse_callable_ref(mapping["guard"], path=f"{path}.guard"),
    true_branch=_parse_guard_branch(mapping["true_branch"], path=f"{path}.true_branch"),
    false_branch=_parse_guard_branch(
      mapping["false_branch"],
      path=f"{path}.false_branch",
    ),
  )


def _parse_guard_branch(payload: object, *, path: str) -> HsmGuardBranch:
  """Build one guard branch from the raw payload entry."""

  mapping = _require_mapping(payload, path=path)
  return HsmGuardBranch(
    target_id=_require_string(mapping, "target_id", path=f"{path}.target_id"),
    activities=_parse_callable_ref_list(
      mapping.get("activities", []),
      path=f"{path}.activities",
    ),
  )


def _derived_guard_node_id(transition_id: str) -> str:
  """Create a deterministic internal guard-node id from one authored transition id."""

  return f"{transition_id}_guard"




def _require_mapping(payload: object, *, path: str) -> dict[str, object]:
  """Require a JSON object at the given path."""

  if not isinstance(payload, dict):
    raise HsmValidationError(
      code="hsm_document.invalid_type",
      message=f"Expected object at '{path or 'root'}'.",
    )
  return payload


def _require_string(
  payload: dict[str, object],
  field_name: str,
  *,
  path: str,
) -> str:
  """Require one string field from a mapping."""

  return _require_string_value(payload[field_name], path=path)


def _require_string_value(value: object, *, path: str) -> str:
  """Require a string value."""

  if not isinstance(value, str):
    raise HsmValidationError(
      code="hsm_document.invalid_type",
      message=f"Expected string at '{path}'.",
    )
  return value


def _optional_string(value: object, *, path: str) -> str | None:
  """Return a string value or None."""

  if value is None:
    return None
  return _require_string_value(value, path=path)


def _require_list(payload: dict[str, object], field_name: str, *, path: str) -> list[object]:
  """Require one array field from a mapping."""

  return _require_list_value(payload[field_name], path=path)


def _require_list_value(value: object, *, path: str) -> list[object]:
  """Require an array value."""

  if not isinstance(value, list):
    raise HsmValidationError(
      code="hsm_document.invalid_type",
      message=f"Expected array at '{path}'.",
    )
  return value


def _validate_hsm_payload_schema(payload: dict[str, object]) -> None:
  """Validate raw payload shape against the JSON Schema."""

  validator = Draft202012Validator(load_hsm_schema())
  errors = sorted(validator.iter_errors(payload), key=lambda error: list(error.path))
  if not errors:
    return
  raise _schema_error_to_validation_error(errors[0], payload)


def _schema_error_to_validation_error(
  error,
  payload: dict[str, object],
) -> HsmValidationError:
  """Map one jsonschema error into the project validation shape."""

  path = _schema_error_path(error)
  value = _get_payload_value(payload, tuple(error.path))

  if error.validator == "additionalProperties":
    match = UNEXPECTED_PROPERTY_PATTERN.search(error.message)
    property_name = match.group(1) if match else "unknown"
    return HsmValidationError(
      code="hsm_document.additional_property",
      message=f"Unsupported property '{property_name}' at '{path}'.",
    )

  if error.validator == "required":
    match = REQUIRED_PROPERTY_PATTERN.search(error.message)
    field_name = match.group(1) if match else "unknown"
    return HsmValidationError(
      code="hsm_document.missing_field",
      message=f"HSM document missing required field '{field_name}'.",
    )

  if error.validator == "type":
    if isinstance(value, str) and _is_executable_slot_path(tuple(error.path)):
      return HsmValidationError(
        code="hsm_document.inline_string_not_allowed",
        message=(
          f"Inline executable strings are not allowed at '{path}'; "
          "use a callable ref object with 'module' and 'name'."
        ),
      )
    return HsmValidationError(
      code="hsm_document.invalid_type",
      message=f"Expected {error.validator_value} at '{path}'.",
    )

  if error.validator == "const" and path == "schema_version":
    return HsmValidationError(
      code="hsm_document.invalid_schema_version",
      message="HSM schema_version must equal 'hsm-v1'.",
    )

  return HsmValidationError(
    code="hsm_document.schema_validation_error",
    message=error.message,
  )


def _schema_error_path(error) -> str:
  """Format the most useful path from a schema error."""

  if error.path:
    return _format_path(tuple(error.path))
  return _format_path(tuple(error.absolute_path))


def _format_path(parts: tuple[object, ...]) -> str:
  """Format nested JSON path parts with dotted/index notation."""

  if not parts:
    return "root"

  formatted: list[str] = []
  for part in parts:
    if isinstance(part, int):
      if formatted:
        formatted[-1] = f"{formatted[-1]}[{part}]"
      else:
        formatted.append(f"[{part}]")
      continue
    formatted.append(str(part))
  return ".".join(formatted)


def _parse_callable_ref_list(
  payload: object,
  *,
  path: str,
) -> tuple[HsmCallableRef, ...]:
  """Parse a list of callable refs."""

  return tuple(
    _parse_callable_ref(item, path=f"{path}[{index}]")
    for index, item in enumerate(_require_list_value(payload, path=path))
  )


def _parse_callable_ref(payload: object, *, path: str) -> HsmCallableRef:
  """Parse and validate one callable ref."""

  mapping = _require_mapping(payload, path=path)
  ref = HsmCallableRef(
    module=_require_string(mapping, "module", path=f"{path}.module"),
    name=_require_string(mapping, "name", path=f"{path}.name"),
  )
  validate_parsed_callable_ref(ref, path=path)
  return ref


def _get_payload_value(payload: object, path: tuple[object, ...]) -> object:
  """Read a nested payload value when available."""

  current = payload
  for part in path:
    if isinstance(part, int):
      if not isinstance(current, list) or part >= len(current):
        return None
      current = current[part]
      continue
    if not isinstance(current, dict) or part not in current:
      return None
    current = current[part]
  return current


def _is_executable_slot_path(path: tuple[object, ...]) -> bool:
  """Return whether a schema path points to an executable slot."""

  executable_fields = {"on_initial", "on_entry", "on_exit", "activities", "guard"}
  return any(isinstance(part, str) and part in executable_fields for part in path)
