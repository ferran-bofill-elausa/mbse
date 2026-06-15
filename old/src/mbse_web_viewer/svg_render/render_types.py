from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HsmPreparedRenderView:
  document_id: str
  root_state_ids: tuple[str, ...]
  state_nodes: tuple["HsmRenderStateNode", ...]
  guard_nodes: tuple["HsmRenderGuardNode", ...]
  routing_helpers: tuple["HsmRenderRoutingHelper", ...]
  initial_edges: tuple["HsmRenderInitialEdge", ...]
  transition_edges: tuple["HsmRenderTransitionEdge", ...]
  highlightable_ids: tuple[str, ...]


@dataclass(frozen=True)
class HsmRenderRoutingHelper:
  id: str
  kind: str
  parent_id: str | None
  owner_id: str | None
  visibility: str


@dataclass(frozen=True)
class HsmRenderTextFragment:
  text: str
  target_payload: str | None = None


@dataclass(frozen=True)
class HsmRenderTextLine:
  fragments: tuple[HsmRenderTextFragment, ...]

  @property
  def text(self) -> str:
    return "".join(fragment.text for fragment in self.fragments)


@dataclass(frozen=True)
class HsmRenderStateSection:
  title_line: HsmRenderTextLine
  lines: tuple[HsmRenderTextLine, ...]

  @property
  def title_text(self) -> str:
    return self.title_line.text


@dataclass(frozen=True)
class HsmRenderStateNode:
  id: str
  title_text: str
  body_sections: tuple[HsmRenderStateSection, ...]
  parent_id: str | None
  child_state_ids: tuple[str, ...]
  depth: int
  fill_rgb: str
  has_body_content: bool

  @property
  def body_lines(self) -> tuple[str, ...]:
    lines: list[str] = []
    for section in self.body_sections:
      lines.append(section.title_text)
      lines.extend(line.text for line in section.lines)
    return tuple(lines)


@dataclass(frozen=True)
class HsmRenderGuardNode:
  id: str
  title_text: str


@dataclass(frozen=True)
class HsmRenderInitialEdge:
  id: str
  source_id: str
  target_id: str
  label: str | None = None
  source_cluster_id: str | None = None
  target_cluster_id: str | None = None


@dataclass(frozen=True)
class HsmRenderTransitionEdge:
  id: str
  source_id: str
  target_id: str
  label_line: HsmRenderTextLine | None
  xlabel_line: HsmRenderTextLine | None = None
  tail_label_lines: tuple[HsmRenderTextLine, ...] = ()
  source_cluster_id: str | None = None
  target_cluster_id: str | None = None

  @property
  def label(self) -> str | None:
    if self.label_line is None:
      return None
    return self.label_line.text

  @property
  def xlabel(self) -> str | None:
    if self.xlabel_line is None:
      return None
    return self.xlabel_line.text


__all__ = [
  "HsmPreparedRenderView",
  "HsmRenderGuardNode",
  "HsmRenderInitialEdge",
  "HsmRenderRoutingHelper",
  "HsmRenderStateNode",
  "HsmRenderStateSection",
  "HsmRenderTextFragment",
  "HsmRenderTextLine",
  "HsmRenderTransitionEdge",
]
