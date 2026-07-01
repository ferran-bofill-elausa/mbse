from __future__ import annotations

"""Internal render data shapes for the HSM render layer."""

from dataclasses import dataclass
import xml.etree.ElementTree as ET


@dataclass(frozen=True)
class HsmSvgHighlightIndex:
  """Stable lookup index from HSM structure to highlightable SVG ids."""

  state_ids_by_state_id: dict[str, str]
  state_label_text_ids: dict[str, tuple[str, ...]]
  initial_transition_ids_by_owner_id: dict[str | None, str]
  initial_transition_source_ids_by_owner_id: dict[str | None, str]
  initial_transition_label_text_ids: dict[str, tuple[str, ...]]
  initial_transition_activity_text_ids: dict[tuple[str, str], tuple[str, ...]]
  external_transition_ids_by_key: dict[tuple[str, str, str], tuple[str, ...]]
  guarded_transition_ids_by_key: dict[tuple[str, str], tuple[str, ...]]
  guard_node_ids_by_key: dict[tuple[str, str], tuple[str, ...]]
  guard_branch_ids_by_key: dict[tuple[str, str, bool, str], tuple[str, ...]]
  guard_node_text_ids_by_key: dict[tuple[str, str], tuple[str, ...]]
  internal_transition_ids_by_key: dict[tuple[str, str], tuple[str, ...]]
  internal_transition_owner_by_id: dict[str, tuple[str, str]]
  state_hook_section_text_ids: dict[tuple[str, str], tuple[str, ...]]
  state_hook_activity_text_ids: dict[tuple[str, str, str], tuple[str, ...]]
  external_transition_label_text_ids: dict[str, tuple[str, ...]]
  external_transition_activity_text_ids: dict[tuple[str, str], tuple[str, ...]]
  internal_transition_section_text_ids: dict[tuple[str, str], tuple[str, ...]]
  internal_transition_event_text_ids: dict[str, tuple[str, ...]]
  internal_transition_activity_text_ids: dict[tuple[str, str], tuple[str, ...]]
  highlightable_ids: tuple[str, ...]


@dataclass(frozen=True)
class RenderTextFragment:
  """One small text fragment optionally bound to one highlight payload."""

  text: str
  target_payload: str | None = None


@dataclass(frozen=True)
class RenderTextLine:
  """One logical line of text in the DOT label model."""

  fragments: tuple[RenderTextFragment, ...]


@dataclass(frozen=True)
class RenderStateSection:
  """One logical section inside one rendered state body."""

  title_line: RenderTextLine
  lines: tuple[RenderTextLine, ...]


@dataclass(frozen=True)
class RenderStateNode:
  """Prepared node data consumed directly by the DOT template."""

  svg_id: str
  state_id: str
  title_text: str
  body_sections: tuple[RenderStateSection, ...]
  parent_svg_id: str | None
  child_state_svg_ids: tuple[str, ...]
  depth: int
  fill_rgb: str


@dataclass(frozen=True)
class RenderGuardNode:
  """Prepared guard node data consumed directly by the DOT template."""

  svg_id: str
  title_line: RenderTextLine


@dataclass(frozen=True)
class RenderRoutingHelper:
  """Graphviz-only helper node used to stabilize edge routing.

  Helpers may be visible or invisible depending on the routing role they serve.
  """

  id: str
  parent_svg_id: str | None
  visibility: str


@dataclass(frozen=True)
class RenderInitialEdge:
  """Prepared initial-transition edge consumed by the DOT template."""

  svg_id: str
  source_id: str
  target_id: str
  label_line: RenderTextLine | None
  source_cluster_svg_id: str | None
  target_cluster_svg_id: str | None


@dataclass(frozen=True)
class RenderTransitionEdge:
  """Prepared external or guard-branch edge consumed by the DOT template."""

  svg_id: str
  source_id: str
  target_id: str
  label_line: RenderTextLine | None
  source_cluster_svg_id: str | None
  target_cluster_svg_id: str | None


@dataclass(frozen=True)
class RenderView:
  """Minimal template-ready view of one HSM diagram."""

  document_id: str
  state_nodes: tuple[RenderStateNode, ...]
  guard_nodes: tuple[RenderGuardNode, ...]
  routing_helpers: tuple[RenderRoutingHelper, ...]
  initial_edges: tuple[RenderInitialEdge, ...]
  transition_edges: tuple[RenderTransitionEdge, ...]


@dataclass(frozen=True)
class RenderBuildResult:
  """Prepared render view plus structural lookup tables for highlighting."""

  view: RenderView
  highlightable_ids: tuple[str, ...]
  state_ids_by_state_id: dict[str, str]
  initial_transition_ids_by_owner_id: dict[str | None, str]
  initial_transition_source_ids_by_owner_id: dict[str | None, str]
  external_transition_ids_by_key: dict[tuple[str, str, str], tuple[str, ...]]
  guarded_transition_ids_by_key: dict[tuple[str, str], tuple[str, ...]]
  guard_node_ids_by_key: dict[tuple[str, str], tuple[str, ...]]
  guard_branch_ids_by_key: dict[tuple[str, str, bool, str], tuple[str, ...]]
  internal_transition_ids_by_key: dict[tuple[str, str], tuple[str, ...]]
  internal_transition_owner_by_id: dict[str, tuple[str, str]]


@dataclass(frozen=True)
class InternalTransitionSpec:
  """Prepared internal-transition data used while building state sections."""

  svg_id: str
  event_id: str
  activities: list[dict[str, str]]


@dataclass(frozen=True)
class NormalizedSvgTextTargets:
  """Resolved text-fragment ids derived from Graphviz SVG output."""

  state_hook_section_ids: dict[tuple[str, str], tuple[str, ...]]
  state_hook_activity_ids: dict[tuple[str, str, str], tuple[str, ...]]
  state_label_ids: dict[str, tuple[str, ...]]
  initial_transition_label_ids: dict[str, tuple[str, ...]]
  initial_transition_activity_ids: dict[tuple[str, str], tuple[str, ...]]
  external_transition_label_ids: dict[str, tuple[str, ...]]
  external_transition_activity_ids: dict[tuple[str, str], tuple[str, ...]]
  guard_node_text_ids: dict[tuple[str, str], tuple[str, ...]]
  internal_transition_section_ids: dict[str, tuple[str, ...]]
  internal_transition_event_ids: dict[str, tuple[str, ...]]
  internal_transition_activity_ids: dict[tuple[str, str], tuple[str, ...]]


@dataclass(frozen=True)
class SvgTextFragment:
  """One fragment extracted from raw Graphviz SVG text output."""

  wrapper: ET.Element
  text_element: ET.Element
  payload: str | None
