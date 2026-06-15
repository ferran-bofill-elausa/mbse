"""Callable-ref resolution and signature validation."""

from __future__ import annotations

import importlib
import inspect

from mbse.model.hsm.model_types import HsmCallableRef
from mbse.model.hsm.model_types import HsmDocument
from mbse.model.hsm.model_types import HsmState
from mbse.model.hsm.validation.exceptions import HsmValidationError


def validate_hsm_document_callables(document: HsmDocument) -> None:
  """Resolve every declared callable ref and validate its signature."""

  for state in _iter_states(document.states):
    _validate_callable_refs(
      state.on_initial,
      path_prefix=f"state '{state.id}' on_initial",
      ref_kind="Activity",
      expected_args=1,
    )
    _validate_callable_refs(
      state.on_entry,
      path_prefix=f"state '{state.id}' on_entry",
      ref_kind="Activity",
      expected_args=1,
    )
    _validate_callable_refs(
      state.on_exit,
      path_prefix=f"state '{state.id}' on_exit",
      ref_kind="Activity",
      expected_args=1,
    )

  for transition in document.external_transitions:
    _validate_callable_refs(
      transition.activities,
      path_prefix=f"external transition '{transition.id}' activities",
      ref_kind="Activity",
      expected_args=1,
    )

  for guard_node in document.guard_nodes:
    _validate_callable_ref_signature(
      guard_node.guard,
      path=f"guard node '{guard_node.id}' guard",
      ref_kind="Guard",
      expected_args=1,
    )
    _validate_callable_refs(
      guard_node.true_branch.activities,
      path_prefix=f"guard node '{guard_node.id}' true_branch activities",
      ref_kind="Activity",
      expected_args=1,
    )
    _validate_callable_refs(
      guard_node.false_branch.activities,
      path_prefix=f"guard node '{guard_node.id}' false_branch activities",
      ref_kind="Activity",
      expected_args=1,
    )

  for transition in document.internal_transitions:
    _validate_callable_refs(
      transition.activities,
      path_prefix=f"internal transition '{transition.id}' activities",
      ref_kind="Activity",
      expected_args=1,
    )


def validate_parsed_callable_ref(ref: HsmCallableRef, *, path: str) -> None:
  """Validate one parsed callable ref using its owning slot semantics."""

  ref_kind = "Guard" if path.endswith(".guard") else "Activity"
  _validate_callable_ref_signature(
    ref,
    path=path,
    ref_kind=ref_kind,
    expected_args=1,
  )


def _iter_states(states: tuple[HsmState, ...]) -> tuple[HsmState, ...]:
  """Flatten a state tree into traversal order."""

  collected: list[HsmState] = []
  for state in states:
    collected.append(state)
    collected.extend(_iter_states(state.states))
  return tuple(collected)


def _validate_callable_refs(
  refs: tuple[HsmCallableRef, ...],
  *,
  path_prefix: str,
  ref_kind: str,
  expected_args: int,
) -> None:
  """Validate a sequence of callable refs."""

  for index, ref in enumerate(refs):
    _validate_callable_ref_signature(
      ref,
      path=f"{path_prefix}[{index}]",
      ref_kind=ref_kind,
      expected_args=expected_args,
    )


def _validate_callable_ref_signature(
  ref: HsmCallableRef,
  *,
  path: str,
  ref_kind: str,
  expected_args: int,
) -> None:
  """Resolve one callable ref and enforce its positional arity."""

  resolved = _resolve_callable_ref(ref, path=path)
  parameters = [
    parameter
    for parameter in inspect.signature(resolved).parameters.values()
    if parameter.kind in (
      inspect.Parameter.POSITIONAL_ONLY,
      inspect.Parameter.POSITIONAL_OR_KEYWORD,
    )
  ]
  if len(parameters) != expected_args:
    expected_label = (
      "one argument" if expected_args == 1 else f"{expected_args} arguments"
    )
    raise HsmValidationError(
      code="hsm_document.invalid_callable_signature",
      message=(
        f"{ref_kind} ref '{_format_callable_ref_id(ref)}' at '{path}' must accept "
        f"exactly {expected_label}."
      ),
    )


def _resolve_callable_ref(ref: HsmCallableRef, *, path: str):
  """Import and return the referenced callable."""

  try:
    module = importlib.import_module(ref.module)
  except ImportError as error:
    raise HsmValidationError(
      code="hsm_document.callable_ref_not_found",
      message=(
        f"Callable ref '{_format_callable_ref_id(ref)}' at '{path}' could not be resolved."
      ),
    ) from error
  if not hasattr(module, ref.name):
    raise HsmValidationError(
      code="hsm_document.callable_ref_not_found",
      message=(
        f"Callable ref '{_format_callable_ref_id(ref)}' at '{path}' could not be resolved."
      ),
    )
  resolved = getattr(module, ref.name)
  if not callable(resolved):
    raise HsmValidationError(
      code="hsm_document.callable_ref_not_found",
      message=(
        f"Callable ref '{_format_callable_ref_id(ref)}' at '{path}' could not be resolved."
      ),
    )
  return resolved


def _format_callable_ref_id(ref: HsmCallableRef) -> str:
  """Return the fully qualified callable-ref id."""

  return f"{ref.module}.{ref.name}"


__all__ = ["validate_hsm_document_callables", "validate_parsed_callable_ref"]
