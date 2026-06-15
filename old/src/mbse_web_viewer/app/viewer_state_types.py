from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field


@dataclass(frozen=True)
class RuntimeViewerTextTargets:
  lifecycle_section_ids: dict[str, dict[str, tuple[str, ...]]] = field(
    default_factory=dict
  )
  lifecycle_activity_ids: dict[
    str,
    dict[str, dict[str, tuple[str, ...]]],
  ] = field(default_factory=dict)
  external_transition_label_ids: dict[str, tuple[str, ...]] = field(
    default_factory=dict
  )
  external_transition_activity_ids: dict[
    str, dict[str, tuple[str, ...]]
  ] = field(
    default_factory=dict
  )
  internal_transition_section_ids: dict[str, tuple[str, ...]] = field(
    default_factory=dict
  )
  internal_transition_event_ids: dict[str, tuple[str, ...]] = field(
    default_factory=dict
  )
  internal_transition_activity_ids: dict[
    str,
    dict[str, tuple[str, ...]],
  ] = field(default_factory=dict)


@dataclass(frozen=True)
class ViewerAppState:
  document_id: str
  svg_url: str
  highlightable_ids: tuple[str, ...]
  text_targets: RuntimeViewerTextTargets = field(
    default_factory=lambda: RuntimeViewerTextTargets()
  )


@dataclass(frozen=True)
class RuntimeViewerSession:
  document_id: str
  svg_url: str
  event_ids: tuple[str, ...]
  variable_ids: tuple[str, ...]
  snapshot: dict[str, object]
  text_targets: RuntimeViewerTextTargets = field(
    default_factory=lambda: RuntimeViewerTextTargets()
  )


__all__ = [
  "RuntimeViewerSession",
  "RuntimeViewerTextTargets",
  "ViewerAppState",
]
