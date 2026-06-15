from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
import re

from mbse_web_viewer.app.viewer_state_types import RuntimeViewerTextTargets
from mbse_web_viewer.svg_render.graphviz.exceptions import GraphvizValidationError


@dataclass(frozen=True)
class PreparedGraphvizDocument:
  document_id: str
  dot_source: str
  highlightable_ids: tuple[str, ...]
  viewer_text_targets: RuntimeViewerTextTargets = field(
    default_factory=lambda: RuntimeViewerTextTargets()
  )


AUTHORED_ID_PATTERN = re.compile(r'id\s*=\s*"([^"]+)"')
REQUIRED_FIELDS = (
  "document_id",
  "dot_source",
  "highlightable_ids",
)
ROUTING_HELPER_ID_PREFIX = "__routing_helper_"


def load_prepared_document(payload: dict[str, object]) -> PreparedGraphvizDocument:
  for field_name in REQUIRED_FIELDS:
    if field_name not in payload:
      raise GraphvizValidationError(
        code="prepared_document.missing_field",
        message=f"Prepared document missing required field '{field_name}'.",
      )

  document = PreparedGraphvizDocument(
    document_id=str(payload["document_id"]),
    dot_source=str(payload["dot_source"]),
    highlightable_ids=tuple(str(item) for item in payload["highlightable_ids"]),
    viewer_text_targets=load_runtime_viewer_text_targets(
      payload.get("viewer_text_targets", {})
    ),
  )
  validate_prepared_document(document)
  return document


def validate_prepared_document(document: PreparedGraphvizDocument) -> None:
  duplicates = _duplicate_values(document.highlightable_ids)
  if duplicates:
    duplicate = duplicates[0]
    raise GraphvizValidationError(
      code="prepared_document.duplicate_highlightable_id",
      message=f"Duplicate highlightable_id '{duplicate}'.",
    )

  authored_id_values = extract_authored_ids(document.dot_source)
  authored_duplicates = _duplicate_values(authored_id_values)
  if authored_duplicates:
    duplicate = authored_duplicates[0]
    raise GraphvizValidationError(
      code="prepared_document.duplicate_authored_id",
      message=f"Duplicate authored id '{duplicate}' in dot_source.",
    )

  authored_ids = set(authored_id_values)
  for highlightable_id in document.highlightable_ids:
    if highlightable_id.startswith(ROUTING_HELPER_ID_PREFIX):
      raise GraphvizValidationError(
        code="prepared_document.private_helper_leaked",
        message=(
          f"Highlightable ID '{highlightable_id}' must remain private."
        ),
      )
    if highlightable_id not in authored_ids:
      raise GraphvizValidationError(
        code="prepared_document.id_not_authored",
        message=(
          f"Highlightable ID '{highlightable_id}' is not authored in dot_source."
        ),
      )

  unexpected_authored_ids = [
    authored_id
    for authored_id in authored_id_values
    if authored_id not in document.highlightable_ids
  ]
  if unexpected_authored_ids:
    unexpected_id = unexpected_authored_ids[0]
    raise GraphvizValidationError(
      code="prepared_document.unexpected_authored_id",
      message=(
        f"Authored ID '{unexpected_id}' must not appear as an extra public id."
      ),
    )


def extract_authored_ids(dot_source: str) -> tuple[str, ...]:
  authored_ids = tuple(AUTHORED_ID_PATTERN.findall(dot_source))
  for authored_id in authored_ids:
    if authored_id.startswith(ROUTING_HELPER_ID_PREFIX):
      raise GraphvizValidationError(
        code="prepared_document.private_helper_leaked",
        message=f"Authored ID '{authored_id}' must remain private.",
      )
  return authored_ids


def load_runtime_viewer_text_targets(payload: object) -> RuntimeViewerTextTargets:
  mapping = _require_mapping(payload, path="viewer_text_targets")
  return RuntimeViewerTextTargets(
    lifecycle_section_ids=_tuple_nested_3(mapping.get("lifecycle_section_ids", {})),
    lifecycle_activity_ids=_tuple_nested_4(
      mapping.get("lifecycle_activity_ids", {})
    ),
    external_transition_label_ids=_tuple_nested_2(
      mapping.get("external_transition_label_ids", {})
    ),
    external_transition_activity_ids=_tuple_nested_3(
      mapping.get("external_transition_activity_ids", {})
    ),
    internal_transition_section_ids=_tuple_nested_2(
      mapping.get("internal_transition_section_ids", {})
    ),
    internal_transition_event_ids=_tuple_nested_2(
      mapping.get("internal_transition_event_ids", {})
    ),
    internal_transition_activity_ids=_tuple_nested_3(
      mapping.get("internal_transition_activity_ids", {})
    ),
  )


def _tuple_nested_2(payload: object) -> dict[str, tuple[str, ...]]:
  mapping = _require_mapping(payload, path="viewer_text_targets")
  return {
    str(key): tuple(str(item) for item in _require_list_value(value, path=str(key)))
    for key, value in mapping.items()
  }


def _tuple_nested_3(payload: object) -> dict[str, dict[str, tuple[str, ...]]]:
  mapping = _require_mapping(payload, path="viewer_text_targets")
  return {
    str(outer_key): {
      str(inner_key): tuple(
        str(item) for item in _require_list_value(inner_value, path=str(inner_key))
      )
      for inner_key, inner_value in _require_mapping(
        outer_value,
        path=str(outer_key),
      ).items()
    }
    for outer_key, outer_value in mapping.items()
  }


def _tuple_nested_4(
  payload: object,
) -> dict[str, dict[str, dict[str, tuple[str, ...]]]]:
  mapping = _require_mapping(payload, path="viewer_text_targets")
  return {
    str(outer_key): {
      str(inner_key): {
        str(leaf_key): tuple(
          str(item) for item in _require_list_value(leaf_value, path=str(leaf_key))
        )
        for leaf_key, leaf_value in _require_mapping(
          inner_value,
          path=str(inner_key),
        ).items()
      }
      for inner_key, inner_value in _require_mapping(
        outer_value,
        path=str(outer_key),
      ).items()
    }
    for outer_key, outer_value in mapping.items()
  }


def _require_mapping(payload: object, *, path: str) -> dict[str, object]:
  if not isinstance(payload, dict):
    raise GraphvizValidationError(
      code="hsm_document.invalid_type",
      message=f"Expected object at '{path or 'root'}'.",
    )
  return payload


def _require_list_value(value: object, *, path: str) -> list[object]:
  if not isinstance(value, list):
    raise GraphvizValidationError(
      code="hsm_document.invalid_type",
      message=f"Expected array at '{path}'.",
    )
  return value


def _duplicate_values(values: tuple[str, ...]) -> list[str]:
  seen: set[str] = set()
  duplicates: list[str] = []
  for value in values:
    if value in seen and value not in duplicates:
      duplicates.append(value)
    seen.add(value)
  return duplicates


__all__ = [
  "PreparedGraphvizDocument",
  "extract_authored_ids",
  "load_prepared_document",
  "load_runtime_viewer_text_targets",
  "validate_prepared_document",
]
