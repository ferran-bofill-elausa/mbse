from __future__ import annotations

import colorsys

from mbse.model.hsm import HsmDocument
from mbse.model.hsm import HsmEvent
from mbse.model.hsm import HsmGuardNode
from mbse.model.hsm import HsmInitialTransition
from mbse.model.hsm import HsmInternalTransition
from mbse.model.hsm import HsmState
from mbse.model.hsm import HsmExternalTransition
from mbse_web_viewer.svg_render.render_types import HsmPreparedRenderView
from mbse_web_viewer.svg_render.render_types import HsmRenderGuardNode
from mbse_web_viewer.svg_render.render_types import HsmRenderInitialEdge
from mbse_web_viewer.svg_render.render_types import HsmRenderRoutingHelper
from mbse_web_viewer.svg_render.render_types import HsmRenderStateNode
from mbse_web_viewer.svg_render.render_types import HsmRenderStateSection
from mbse_web_viewer.svg_render.render_types import HsmRenderTextFragment
from mbse_web_viewer.svg_render.render_types import HsmRenderTextLine
from mbse_web_viewer.svg_render.render_types import HsmRenderTransitionEdge


ROUTING_HELPER_PREFIX = "__routing_helper"
BASE_FILL_RGB = (220, 232, 242)
BASE_FILL_HLS = colorsys.rgb_to_hls(
  *(channel / 255 for channel in BASE_FILL_RGB)
)
DERIVED_FILL_SATURATION = min(BASE_FILL_HLS[2], 0.30)
DEPTH_HUE_STEP = -0.60
DEPTH_LIGHTNESS_STEP = 0.004
MAX_DERIVED_LIGHTNESS = 0.94


class _RoutedEndpoint:
  def __init__(self, node_id: str, *, cluster_id: str | None = None) -> None:
    self.node_id = node_id
    self.cluster_id = cluster_id


def prepare_hsm_render_view(document: HsmDocument) -> HsmPreparedRenderView:
  event_labels = {
    event.id: _format_event_label(event) for event in document.events
  }
  compound_state_ids = _collect_compound_state_ids(document.states)
  internal_transitions_by_source_id = _group_internal_transitions_by_source_id(
    document.internal_transitions,
  )
  routing_helpers = _RoutingHelperRegistry()
  state_nodes = tuple(
    _flatten_state_nodes(
      document.states,
      parent_id=None,
      internal_transitions_by_source_id=internal_transitions_by_source_id,
      event_labels=event_labels,
    )
  )
  guard_nodes = tuple(
    HsmRenderGuardNode(
      id=guard_node.id,
      title_text=str(guard_node.guard),
    )
    for guard_node in document.guard_nodes
  )
  initial_edges = tuple(
    _prepare_initial_edges(document, compound_state_ids, routing_helpers)
  )
  transition_edges = tuple(
    _prepare_transition_edges(
      document.external_transitions,
      document.guard_nodes,
      event_labels,
      compound_state_ids,
      routing_helpers,
    )
  )
  highlightable_ids = (
    tuple(state.id for state in state_nodes)
    + tuple(guard_node.id for guard_node in guard_nodes)
    + tuple(edge.id for edge in initial_edges)
    + tuple(edge.id for edge in transition_edges)
  )
  return HsmPreparedRenderView(
    document_id=document.document_id,
    root_state_ids=tuple(state.id for state in document.states),
    state_nodes=state_nodes,
    guard_nodes=guard_nodes,
    routing_helpers=tuple(routing_helpers.ordered()),
    initial_edges=initial_edges,
    transition_edges=transition_edges,
    highlightable_ids=highlightable_ids,
  )


def _flatten_state_nodes(
  states: tuple[HsmState, ...],
  *,
  parent_id: str | None,
  internal_transitions_by_source_id: dict[str, tuple[HsmInternalTransition, ...]],
  event_labels: dict[str, str],
  depth: int = 0,
) -> list[HsmRenderStateNode]:
  nodes: list[HsmRenderStateNode] = []
  for state in states:
    body_sections = _format_state_body_sections(
      state,
      internal_transitions_by_source_id.get(state.id, ()),
      event_labels,
    )
    nodes.append(
      HsmRenderStateNode(
        id=state.id,
        title_text=state.label or state.id,
        body_sections=body_sections,
        parent_id=parent_id,
        child_state_ids=tuple(child.id for child in state.states),
        depth=depth,
        fill_rgb=_derive_fill_rgb(depth),
        has_body_content=bool(body_sections),
      )
    )
    nodes.extend(
      _flatten_state_nodes(
        state.states,
        parent_id=state.id,
        internal_transitions_by_source_id=internal_transitions_by_source_id,
        event_labels=event_labels,
        depth=depth + 1,
      )
    )
  return nodes


def _collect_compound_state_ids(states: tuple[HsmState, ...]) -> set[str]:
  compound_state_ids: set[str] = set()
  for state in states:
    if state.states:
      compound_state_ids.add(state.id)
      compound_state_ids.update(_collect_compound_state_ids(state.states))
  return compound_state_ids


def _prepare_initial_edges(
  document: HsmDocument,
  compound_state_ids: set[str],
  routing_helpers: "_RoutingHelperRegistry",
) -> list[HsmRenderInitialEdge]:
  edges: list[HsmRenderInitialEdge] = []
  if document.initial is not None:
    edges.append(
      _prepare_initial_edge(
        document.initial,
        routing_helpers.root_initial_source(document.initial.id),
        compound_state_ids,
        routing_helpers,
      )
    )
  edges.extend(
    _flatten_local_initials(document.states, compound_state_ids, routing_helpers)
  )
  return edges


def _prepare_initial_edge(
  edge: HsmInitialTransition,
  source_id: str,
  compound_state_ids: set[str],
  routing_helpers: "_RoutingHelperRegistry",
) -> HsmRenderInitialEdge:
  target = _route_state_endpoint(
    edge.target_id,
    compound_state_ids,
    routing_helpers,
  )
  return HsmRenderInitialEdge(
    id=edge.id,
    source_id=source_id,
    target_id=target.node_id,
    target_cluster_id=target.cluster_id,
  )


def _prepare_transition_edge(
  transition: HsmExternalTransition,
  event_labels: dict[str, str],
  compound_state_ids: set[str],
  routing_helpers: "_RoutingHelperRegistry",
) -> HsmRenderTransitionEdge:
  source = _route_state_endpoint(
    transition.source_id,
    compound_state_ids,
    routing_helpers,
  )
  target = _route_state_endpoint(
    transition.target_id,
    compound_state_ids,
    routing_helpers,
  )
  return HsmRenderTransitionEdge(
    id=transition.id,
    source_id=source.node_id,
    target_id=target.node_id,
    label_line=_format_transition_label(transition, event_labels),
    source_cluster_id=source.cluster_id,
    target_cluster_id=target.cluster_id,
  )


def _prepare_transition_edges(
  external_transitions: tuple[HsmExternalTransition, ...],
  guard_nodes: tuple[HsmGuardNode, ...],
  event_labels: dict[str, str],
  compound_state_ids: set[str],
  routing_helpers: "_RoutingHelperRegistry",
) -> list[HsmRenderTransitionEdge]:
  guard_nodes_by_id = {guard_node.id: guard_node for guard_node in guard_nodes}
  edges: list[HsmRenderTransitionEdge] = []
  for transition in external_transitions:
    edges.append(
      _prepare_transition_edge(
        transition,
        event_labels,
        compound_state_ids,
        routing_helpers,
      )
    )
    guard_node = guard_nodes_by_id.get(transition.target_id)
    if guard_node is None:
      continue
    edges.append(
      _prepare_guard_branch_edge(
        guard_node,
        outcome="true",
        target_id=guard_node.true_branch.target_id,
        activities=guard_node.true_branch.activities,
        compound_state_ids=compound_state_ids,
        routing_helpers=routing_helpers,
      )
    )
    edges.append(
      _prepare_guard_branch_edge(
        guard_node,
        outcome="false",
        target_id=guard_node.false_branch.target_id,
        activities=guard_node.false_branch.activities,
        compound_state_ids=compound_state_ids,
        routing_helpers=routing_helpers,
      )
    )
  return edges


def _prepare_guard_branch_edge(
  guard_node: HsmGuardNode,
  *,
  outcome: str,
  target_id: str,
  activities: tuple,
  compound_state_ids: set[str],
  routing_helpers: "_RoutingHelperRegistry",
) -> HsmRenderTransitionEdge:
  target = _route_state_endpoint(
    target_id,
    compound_state_ids,
    routing_helpers,
  )
  edge_id = f"{guard_node.id}_{outcome}"
  return HsmRenderTransitionEdge(
    id=edge_id,
    source_id=guard_node.id,
    target_id=target.node_id,
    label_line=_format_guard_branch_label(
      edge_id,
      outcome=outcome,
      activities=activities,
    ),
    source_cluster_id=None,
    target_cluster_id=target.cluster_id,
  )


def _flatten_local_initials(
  states: tuple[HsmState, ...],
  compound_state_ids: set[str],
  routing_helpers: "_RoutingHelperRegistry",
) -> list[HsmRenderInitialEdge]:
  edges: list[HsmRenderInitialEdge] = []
  for state in states:
    if state.initial is not None:
      edges.append(
        _prepare_initial_edge(
          state.initial,
          routing_helpers.local_initial_source(state.id, state.initial.id),
          compound_state_ids,
          routing_helpers,
        )
      )
    edges.extend(
      _flatten_local_initials(
        state.states,
        compound_state_ids,
        routing_helpers,
      )
    )
  return edges


class _RoutingHelperRegistry:
  def __init__(self) -> None:
    self._helpers_by_id: dict[str, HsmRenderRoutingHelper] = {}
    self._ordered_helper_ids: list[str] = []

  def ordered(self) -> tuple[HsmRenderRoutingHelper, ...]:
    return tuple(self._helpers_by_id[helper_id] for helper_id in self._ordered_helper_ids)

  def root_initial_source(self, edge_id: str) -> str:
    helper_id = f"{ROUTING_HELPER_PREFIX}_root_initial_source__{edge_id}"
    return self._register(
      helper_id,
      kind="root_initial_source",
      parent_id=None,
      owner_id=edge_id,
      visibility="visible_source",
    )

  def local_initial_source(self, state_id: str, edge_id: str) -> str:
    helper_id = f"{ROUTING_HELPER_PREFIX}_local_initial_source__{state_id}"
    return self._register(
      helper_id,
      kind="local_initial_source",
      parent_id=state_id,
      owner_id=edge_id,
      visibility="visible_source",
    )

  def compound_anchor(self, state_id: str) -> str:
    helper_id = f"{ROUTING_HELPER_PREFIX}_compound_anchor__{state_id}"
    return self._register(
      helper_id,
      kind="compound_anchor",
      parent_id=state_id,
      owner_id=state_id,
      visibility="private_anchor",
    )

  def _register(
    self,
    helper_id: str,
    *,
    kind: str,
    parent_id: str | None,
    owner_id: str,
    visibility: str,
  ) -> str:
    if helper_id not in self._helpers_by_id:
      self._helpers_by_id[helper_id] = HsmRenderRoutingHelper(
        id=helper_id,
        kind=kind,
        parent_id=parent_id,
        owner_id=owner_id,
        visibility=visibility,
      )
      self._ordered_helper_ids.append(helper_id)
    return helper_id


def _route_state_endpoint(
  state_id: str,
  compound_state_ids: set[str],
  routing_helpers: _RoutingHelperRegistry,
) -> _RoutedEndpoint:
  if state_id not in compound_state_ids:
    return _RoutedEndpoint(state_id)
  return _RoutedEndpoint(
    routing_helpers.compound_anchor(state_id),
    cluster_id=state_id,
  )


def _format_state_body_sections(
  state: HsmState,
  internal_transitions: tuple[HsmInternalTransition, ...],
  event_labels: dict[str, str],
) -> tuple[HsmRenderStateSection, ...]:
  sections: list[HsmRenderStateSection] = []
  _append_lifecycle_section(
    sections,
    state_id=state.id,
    section_name="on_entry",
    activities=state.on_entry,
  )
  _append_lifecycle_section(
    sections,
    state_id=state.id,
    section_name="on_initial",
    activities=state.on_initial,
  )
  _append_lifecycle_section(
    sections,
    state_id=state.id,
    section_name="on_exit",
    activities=state.on_exit,
  )
  if internal_transitions:
    sections.append(
      HsmRenderStateSection(
        title_line=HsmRenderTextLine(
          fragments=(
            HsmRenderTextFragment(
              text="internal_transitions:",
              target_payload=f"internal_transition_section|{state.id}",
            ),
          )
        ),
        lines=tuple(
          _format_internal_transition_line(transition, event_labels)
          for transition in internal_transitions
        ),
      )
    )
  return tuple(sections)


def _append_lifecycle_section(
  sections: list[HsmRenderStateSection],
  *,
  state_id: str,
  section_name: str,
  activities: tuple,
) -> None:
  if not activities:
    return
  sections.append(
    HsmRenderStateSection(
      title_line=HsmRenderTextLine(
        fragments=(
          HsmRenderTextFragment(
            text=f"{section_name}:",
            target_payload=f"lifecycle_section|{state_id}|{section_name}",
          ),
        )
      ),
      lines=tuple(
        _activity_bullet_line(
          activity_name=str(activity),
          target_payload=(
            f"lifecycle_activity|{state_id}|{section_name}|{activity}"
          ),
        )
        for activity in activities
      ),
    )
  )


def _activity_bullet_line(
  *,
  activity_name: str,
  target_payload: str,
) -> HsmRenderTextLine:
  return HsmRenderTextLine(
    fragments=(
      HsmRenderTextFragment(text="- "),
      HsmRenderTextFragment(
        text=activity_name,
        target_payload=target_payload,
      ),
    )
  )


def _format_internal_transition_line(
  transition: HsmInternalTransition,
  event_labels: dict[str, str],
) -> HsmRenderTextLine:
  fragments: list[HsmRenderTextFragment] = [HsmRenderTextFragment(text="- ")]
  event_label = event_labels[transition.event_id]
  if transition.activities:
    fragments.append(
      HsmRenderTextFragment(
        text=f"{event_label}/",
        target_payload=f"internal_transition_event|{transition.id}",
      )
    )
    fragments.extend(
      _activity_fragments(
        transition.id,
        transition.activities,
        payload_prefix="internal_transition_activity",
      )
    )
  else:
    fragments.append(
      HsmRenderTextFragment(
        text=event_label,
        target_payload=f"internal_transition_event|{transition.id}",
      )
    )
  return HsmRenderTextLine(fragments=tuple(fragments))


def _format_transition_label(
  transition: HsmExternalTransition,
  event_labels: dict[str, str],
) -> HsmRenderTextLine | None:
  if transition.event_id is None and not transition.activities:
    return None
  fragments: list[HsmRenderTextFragment] = []
  if transition.event_id is not None:
    label = event_labels[transition.event_id]
    text = label if not transition.activities else f"{label}/"
    fragments.append(
      HsmRenderTextFragment(
        text=text,
        target_payload=f"external_transition_label|{transition.id}",
      )
    )
  fragments.extend(
    _activity_fragments(
      transition.id,
      transition.activities,
      payload_prefix="external_transition_activity",
    )
  )
  return HsmRenderTextLine(fragments=tuple(fragments))


def _format_guard_branch_label(
  edge_id: str,
  *,
  outcome: str,
  activities: tuple,
) -> HsmRenderTextLine:
  fragments: list[HsmRenderTextFragment] = [
    HsmRenderTextFragment(
      text=outcome,
      target_payload=f"external_transition_label|{edge_id}",
    )
  ]
  if activities:
    first_activity = str(activities[0])
    fragments.append(
      HsmRenderTextFragment(
        text=f" / {first_activity}",
        target_payload=f"external_transition_activity|{edge_id}|{first_activity}",
      )
    )
    for activity in activities[1:]:
      activity_name = str(activity)
      fragments.append(HsmRenderTextFragment(text=", "))
      fragments.append(
        HsmRenderTextFragment(
          text=activity_name,
          target_payload=(
            f"external_transition_activity|{edge_id}|{activity_name}"
          ),
        )
      )
  return HsmRenderTextLine(fragments=tuple(fragments))


def _activity_fragments(
  edge_id: str,
  activities: tuple,
  *,
  payload_prefix: str,
) -> list[HsmRenderTextFragment]:
  fragments: list[HsmRenderTextFragment] = []
  for index, activity in enumerate(activities):
    activity_name = str(activity)
    if index > 0:
      fragments.append(HsmRenderTextFragment(text=", "))
    fragments.append(
      HsmRenderTextFragment(
        text=activity_name,
        target_payload=f"{payload_prefix}|{edge_id}|{activity_name}",
      )
    )
  return fragments


def _group_internal_transitions_by_source_id(
  internal_transitions: tuple[HsmInternalTransition, ...],
) -> dict[str, tuple[HsmInternalTransition, ...]]:
  grouped: dict[str, list[HsmInternalTransition]] = {}
  for transition in internal_transitions:
    grouped.setdefault(transition.source_id, []).append(transition)
  return {
    source_id: tuple(source_transitions)
    for source_id, source_transitions in grouped.items()
  }


def _format_event_label(event: HsmEvent) -> str:
  if not event.parameters:
    return event.id
  parameters = ", ".join(parameter.name for parameter in event.parameters)
  return f"{event.id}({parameters})"


def _derive_fill_rgb(depth: int) -> str:
  if depth == 0:
    return _hex_rgb(BASE_FILL_RGB)
  hue = (BASE_FILL_HLS[0] + (depth * DEPTH_HUE_STEP)) % 1.0
  lightness = min(
    BASE_FILL_HLS[1] + (depth * DEPTH_LIGHTNESS_STEP),
    MAX_DERIVED_LIGHTNESS,
  )
  rgb = tuple(
    round(channel * 255)
    for channel in colorsys.hls_to_rgb(
      hue,
      lightness,
      DERIVED_FILL_SATURATION,
    )
  )
  return _hex_rgb(rgb)


def _hex_rgb(rgb: tuple[int, int, int]) -> str:
  return "#%02X%02X%02X" % rgb
