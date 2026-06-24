from __future__ import annotations

"""Internal helpers used by `HsmRender`."""

import colorsys
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

from mbse.model.hsm.hsm_model import HsmModel
from mbse_web_viewer.render.hsm import hsm_render_types as types


TEMPLATE_NAME = "hsm_render.dot.j2"
TEMPLATES_DIR = Path(__file__).resolve().parent
_TEXT_FRAGMENT_ID_PREFIX = "text_fragment_"
SVG_NAMESPACE = "http://www.w3.org/2000/svg"
_XLINK_NAMESPACE = "http://www.w3.org/1999/xlink"
_XML_NAMESPACE = "http://www.w3.org/XML/1998/namespace"
_GROUP_TAG = f"{{{SVG_NAMESPACE}}}g"
ANCHOR_TAG = f"{{{SVG_NAMESPACE}}}a"
_TEXT_TAG = f"{{{SVG_NAMESPACE}}}text"
_TITLE_ATTR = f"{{{_XLINK_NAMESPACE}}}title"
_XML_SPACE_ATTR = f"{{{_XML_NAMESPACE}}}space"
_BASE_FILL_RGB = (220, 232, 242)
_BASE_FILL_HLS = colorsys.rgb_to_hls(*((channel / 255) for channel in _BASE_FILL_RGB))
_DERIVED_FILL_SATURATION = min(_BASE_FILL_HLS[2], 0.30)
_DEPTH_HUE_STEP = -0.60
_DEPTH_LIGHTNESS_STEP = 0.004
_MAX_DERIVED_LIGHTNESS = 0.94

_SVG_NAMESPACE = SVG_NAMESPACE
_ANCHOR_TAG = ANCHOR_TAG


# Domain helpers.


def callableKey(activity: dict[str, str] | str) -> str:
  """Return one stable key for one callable reference or literal name."""

  if isinstance(activity, str):
    return activity
  return f"{activity['module']}.{activity['name']}"


def callableLabel(activity: dict[str, str] | str) -> str:
  """Return the human-readable label used in rendered text."""

  if isinstance(activity, str):
    return activity
  return activity["name"]


def formatEventLabel(event: dict[str, Any]) -> str:
  """Format one event label including parameter names when present."""

  parameters = event.get("parameters", [])
  if not parameters:
    return event["id"]
  return f"{event['id']}({', '.join(parameter['name'] for parameter in parameters)})"


# View preparation.


def buildStateNodes(
  model: HsmModel,
  states: list[dict[str, Any]],
  *,
  parent_svg_id: str | None,
  depth: int,
  event_labels: dict[str, str],
  id_registry: SvgIdRegistry,
  state_ids_by_state_id: dict[str, str],
  internal_transition_ids_by_key: dict[tuple[str, str], list[str]],
  internal_transition_owner_by_id: dict[str, tuple[str, str]],
) -> list[types.RenderStateNode]:
  """Flatten one state tree into template-ready nodes with nested body sections."""

  nodes: list[types.RenderStateNode] = []
  for state in states:
    state_id = state["id"]
    svg_id = id_registry.make(f"state_{state_id}")
    state_ids_by_state_id[state_id] = svg_id

    internal_transitions = _buildInternalTransitionSpecs(
      model,
      state_id,
      id_registry=id_registry,
      internal_transition_ids_by_key=internal_transition_ids_by_key,
      internal_transition_owner_by_id=internal_transition_owner_by_id,
    )
    body_sections = _formatStateBodySections(
      state_id,
      model.getStateOnEntry(state_id),
      model.getStateOnExit(state_id),
      internal_transitions,
      event_labels,
    )

    child_states = model.getChildStates(state_id)
    child_nodes = buildStateNodes(
      model,
      child_states,
      parent_svg_id=svg_id,
      depth=depth + 1,
      event_labels=event_labels,
      id_registry=id_registry,
      state_ids_by_state_id=state_ids_by_state_id,
      internal_transition_ids_by_key=internal_transition_ids_by_key,
      internal_transition_owner_by_id=internal_transition_owner_by_id,
    )
    child_state_svg_ids = tuple(
      child_node.svg_id
      for child_node in child_nodes
      if child_node.parent_svg_id == svg_id
    )

    nodes.append(
      types.RenderStateNode(
        svg_id=svg_id,
        title_text=model.getStateLabel(state_id),
        body_sections=body_sections,
        parent_svg_id=parent_svg_id,
        child_state_svg_ids=child_state_svg_ids,
        depth=depth,
        fill_rgb=_deriveFillRgb(depth),
      )
    )
    nodes.extend(child_nodes)
  return nodes


def prepareInitialEdge(
  *,
  source_id: str,
  source_cluster_svg_id: str | None,
  target_state_id: str,
  svg_id: str,
  label_line: types.RenderTextLine | None,
  state_ids_by_state_id: dict[str, str],
  compound_state_ids: set[str],
  routing_helpers: RoutingHelperRegistry,
) -> types.RenderInitialEdge:
  """Prepare one initial-transition edge for DOT rendering."""

  target_id, target_cluster_svg_id = _routeStateEndpoint(
    target_state_id,
    state_ids_by_state_id=state_ids_by_state_id,
    compound_state_ids=compound_state_ids,
    routing_helpers=routing_helpers,
  )
  return types.RenderInitialEdge(
    svg_id=svg_id,
    source_id=source_id,
    target_id=target_id,
    label_line=label_line,
    source_cluster_svg_id=source_cluster_svg_id,
    target_cluster_svg_id=target_cluster_svg_id,
  )


def prepareTransitionEdge(
  *,
  svg_id: str,
  source_state_id: str | None,
  target_state_id: str | None,
  label_line: types.RenderTextLine | None,
  state_ids_by_state_id: dict[str, str],
  compound_state_ids: set[str],
  routing_helpers: RoutingHelperRegistry,
  explicit_source_svg_id: str | None = None,
  explicit_target_svg_id: str | None = None,
) -> types.RenderTransitionEdge:
  """Prepare one external or guard-branch edge for DOT rendering."""

  if explicit_source_svg_id is None:
    source_id, source_cluster_svg_id = _routeStateEndpoint(
      source_state_id,
      state_ids_by_state_id=state_ids_by_state_id,
      compound_state_ids=compound_state_ids,
      routing_helpers=routing_helpers,
    )
  else:
    source_id = explicit_source_svg_id
    source_cluster_svg_id = None

  if explicit_target_svg_id is None:
    target_id, target_cluster_svg_id = _routeStateEndpoint(
      target_state_id,
      state_ids_by_state_id=state_ids_by_state_id,
      compound_state_ids=compound_state_ids,
      routing_helpers=routing_helpers,
    )
  else:
    target_id = explicit_target_svg_id
    target_cluster_svg_id = None

  return types.RenderTransitionEdge(
    svg_id=svg_id,
    source_id=source_id,
    target_id=target_id,
    label_line=label_line,
    source_cluster_svg_id=source_cluster_svg_id,
    target_cluster_svg_id=target_cluster_svg_id,
  )


def _buildInternalTransitionSpecs(
  model: HsmModel,
  state_id: str,
  *,
  id_registry: SvgIdRegistry,
  internal_transition_ids_by_key: dict[tuple[str, str], list[str]],
  internal_transition_owner_by_id: dict[str, tuple[str, str]],
) -> list[types.InternalTransitionSpec]:
  """Assign stable render ids to one state's internal transitions."""

  specs: list[types.InternalTransitionSpec] = []
  for transition in model.getStateInternalTransitions(state_id):
    event_id = transition["event_id"]
    svg_id = id_registry.make(f"internal_transition_{state_id}_{event_id}")
    internal_transition_ids_by_key.setdefault((state_id, event_id), []).append(svg_id)
    internal_transition_owner_by_id[svg_id] = (state_id, event_id)
    specs.append(
      types.InternalTransitionSpec(
        svg_id=svg_id,
        event_id=event_id,
        activities=transition.get("activities", []),
      )
    )
  return specs


def _routeStateEndpoint(
  state_id: str | None,
  *,
  state_ids_by_state_id: dict[str, str],
  compound_state_ids: set[str],
  routing_helpers: RoutingHelperRegistry,
) -> tuple[str, str | None]:
  """Route one state endpoint through a helper when the state is compound."""

  if state_id is None:
    raise ValueError("State endpoint requires one state_id.")

  svg_id = state_ids_by_state_id[state_id]
  if state_id not in compound_state_ids:
    return svg_id, None

  # Graphviz edges entering clusters route more predictably through helper anchors.
  return routing_helpers.compoundAnchor(svg_id), svg_id


def _formatStateBodySections(
  state_id: str,
  on_entry: list[dict[str, str]],
  on_exit: list[dict[str, str]],
  internal_transitions: list[types.InternalTransitionSpec],
  event_labels: dict[str, str],
) -> tuple[types.RenderStateSection, ...]:
  """Format state hooks and internal transitions for one state body."""

  sections: list[types.RenderStateSection] = []
  _appendStateHookSection(
    sections,
    state_id=state_id,
    section_name="on_entry",
    activities=on_entry,
  )
  _appendStateHookSection(
    sections,
    state_id=state_id,
    section_name="on_exit",
    activities=on_exit,
  )

  if internal_transitions:
    sections.append(
      types.RenderStateSection(
        title_line=types.RenderTextLine(
          fragments=(
            types.RenderTextFragment(
              text="internal_transitions:",
              target_payload=f"internal_transition_section|{state_id}",
            ),
          )
        ),
        lines=tuple(
          _formatInternalTransitionLine(transition, event_labels)
          for transition in internal_transitions
        ),
      )
    )
  return tuple(sections)


def _appendStateHookSection(
  sections: list[types.RenderStateSection],
  *,
  state_id: str,
  section_name: str,
  activities: list[dict[str, str]],
) -> None:
  """Append one state-hook section if the authored state declares it."""

  if not activities:
    return

  sections.append(
    types.RenderStateSection(
      title_line=types.RenderTextLine(
        fragments=(
          types.RenderTextFragment(
            text=f"{section_name}:",
            target_payload=f"state_hook_section|{state_id}|{section_name}",
          ),
        )
      ),
      lines=tuple(
        _activityBulletLine(
          activity=activity,
          target_payload=(
            f"state_hook_activity|{state_id}|{section_name}|{callableKey(activity)}"
          ),
        )
        for activity in activities
      ),
    )
  )


def _activityBulletLine(
  *,
  activity: dict[str, str],
  target_payload: str,
) -> types.RenderTextLine:
  """Return one bulleted activity line for state or transition labels."""

  return types.RenderTextLine(
    fragments=(
      types.RenderTextFragment(text="- "),
      types.RenderTextFragment(
        text=callableLabel(activity),
        target_payload=target_payload,
      ),
    )
  )


def _formatInternalTransitionLine(
  transition: types.InternalTransitionSpec,
  event_labels: dict[str, str],
) -> types.RenderTextLine:
  """Format one internal transition line inside a state body."""

  event_text = event_labels[transition.event_id]
  if transition.activities:
    event_text = f"{event_text}/"

  fragments: list[types.RenderTextFragment] = [
    types.RenderTextFragment(text="- "),
    types.RenderTextFragment(
      text=event_text,
      target_payload=f"internal_transition_event|{transition.svg_id}",
    ),
  ]
  if transition.activities:
    fragments.extend(
      _activityFragments(
        transition.svg_id,
        transition.activities,
        payload_prefix="internal_transition_activity",
      )
    )
  return types.RenderTextLine(fragments=tuple(fragments))


# Label formatting.


def formatExternalTransitionLabel(
  edge_id: str,
  transition: dict[str, Any],
  event_labels: dict[str, str],
) -> types.RenderTextLine | None:
  """Format the label for one external transition edge."""

  activities = transition.get("activities", [])
  event_id = transition.get("event_id")
  if event_id is None and not activities:
    return None

  fragments: list[types.RenderTextFragment] = []
  if event_id is not None:
    event_text = event_labels[event_id]
    if activities:
      event_text = f"{event_text}/"
    fragments.append(
      types.RenderTextFragment(
        text=event_text,
        target_payload=f"external_transition_label|{edge_id}",
      )
    )
  fragments.extend(
    _activityFragments(
      edge_id,
      activities,
      payload_prefix="external_transition_activity",
    )
  )
  return types.RenderTextLine(fragments=tuple(fragments))


def formatInitialTransitionLabel(
  edge_id: str,
  activities: list[dict[str, str]],
) -> types.RenderTextLine | None:
  """Format the label for one initial transition edge."""

  if not activities:
    return None

  return types.RenderTextLine(
    fragments=(
      types.RenderTextFragment(
        text="/ ",
        target_payload=f"initial_transition_label|{edge_id}",
      ),
      *_activityFragments(
        edge_id,
        activities,
        payload_prefix="initial_transition_activity",
      ),
    )
  )


def formatGuardBranchLabel(
  edge_id: str,
  *,
  outcome: bool,
  branch: dict[str, Any],
) -> types.RenderTextLine:
  """Format the label for one guard branch edge."""

  fragments: list[types.RenderTextFragment] = [
    types.RenderTextFragment(
      text="true" if outcome else "false",
      target_payload=f"external_transition_label|{edge_id}",
    )
  ]
  fragments.extend(
    _activityFragments(
      edge_id,
      branch.get("activities", []),
      payload_prefix="external_transition_activity",
      separator_prefix=" / ",
    )
  )
  return types.RenderTextLine(fragments=tuple(fragments))


def _activityFragments(
  edge_id: str,
  activities: list[dict[str, str]],
  *,
  payload_prefix: str,
  separator_prefix: str = "",
) -> list[types.RenderTextFragment]:
  """Format activity fragments for one edge label."""

  fragments: list[types.RenderTextFragment] = []
  for index, activity in enumerate(activities):
    if index == 0 and separator_prefix:
      fragments.append(types.RenderTextFragment(text=separator_prefix))
    elif index > 0:
      fragments.append(types.RenderTextFragment(text=", "))
    fragments.append(
      types.RenderTextFragment(
        text=callableLabel(activity),
        target_payload=f"{payload_prefix}|{edge_id}|{callableKey(activity)}",
      )
    )
  return fragments


# SVG normalization.


def normalizeAnchorTarget(
  anchor: ET.Element,
  collector: TextTargetCollector,
) -> None:
  """Replace one Graphviz anchor payload by one concrete SVG text-fragment id."""

  payload = anchor.attrib.pop(_TITLE_ATTR, None)
  if payload is None:
    return

  text_elements = [element for element in anchor.iter() if element.tag == _TEXT_TAG]
  if len(text_elements) != 1:
    return

  text_element = text_elements[0]
  if not (text_element.text or ""):
    return

  fragment_id = collector.nextId()
  collector.record(payload, fragment_id)
  text_element.set("id", fragment_id)


def collapseTextFragmentRuns(
  parent: ET.Element,
  collector: TextTargetCollector,
) -> None:
  """Merge adjacent text fragments on the same line so each line is stable to highlight."""

  children = list(parent)
  if not children:
    return

  normalized_children: list[ET.Element] = []
  index = 0
  while index < len(children):
    child = children[index]
    fragment = _extractSvgTextFragment(child)
    if fragment is None:
      collapseTextFragmentRuns(child, collector)
      normalized_children.append(child)
      index += 1
      continue

    run = [fragment]
    next_index = index + 1
    while next_index < len(children):
      next_fragment = _extractSvgTextFragment(children[next_index])
      if next_fragment is None or not _sameTextLine(run[0], next_fragment):
        break
      run.append(next_fragment)
      next_index += 1

    if len(run) == 1:
      normalized_children.append(child)
    else:
      normalized_children.append(_mergeTextFragments(run, collector))
    index = next_index

  parent[:] = normalized_children


def stripGeneratedAnchorGroupIds(root: ET.Element) -> None:
  """Drop wrapper ids introduced by Graphviz so only semantic ids remain public."""

  for element in root.iter():
    if element.tag != _GROUP_TAG or len(element) != 1 or element[0].tag != _ANCHOR_TAG:
      continue
    element.attrib.pop("id", None)


def _extractSvgTextFragment(element: ET.Element) -> types.SvgTextFragment | None:
  """Extract one candidate text fragment from the raw Graphviz SVG tree."""

  if element.tag == _TEXT_TAG and (element.text or ""):
    return types.SvgTextFragment(wrapper=element, text_element=element, payload=None)
  if element.tag == _ANCHOR_TAG:
    return _extractAnchorFragment(element, wrapper=element)
  if element.tag != _GROUP_TAG or len(element) != 1 or element[0].tag != _ANCHOR_TAG:
    return None
  return _extractAnchorFragment(element[0], wrapper=element)


def _extractAnchorFragment(
  anchor: ET.Element,
  *,
  wrapper: ET.Element,
) -> types.SvgTextFragment | None:
  """Extract one text fragment from one Graphviz-generated anchor."""

  payload = anchor.attrib.get(_TITLE_ATTR)
  if payload is None:
    return None

  text_elements = [element for element in anchor.iter() if element.tag == _TEXT_TAG]
  if len(text_elements) != 1:
    return None

  text_element = text_elements[0]
  if not (text_element.text or ""):
    return None
  return types.SvgTextFragment(wrapper=wrapper, text_element=text_element, payload=payload)


def _sameTextLine(left: types.SvgTextFragment, right: types.SvgTextFragment) -> bool:
  """Return whether two text fragments belong to the same visual line."""

  return (
    left.text_element.attrib.get("y") == right.text_element.attrib.get("y")
    and _textStyleSignature(left.text_element)
    == _textStyleSignature(right.text_element)
  )


def _textStyleSignature(text_element: ET.Element) -> tuple[str | None, ...]:
  """Return the subset of SVG text styling needed to compare line affinity."""

  return (
    text_element.attrib.get("text-anchor"),
    text_element.attrib.get("font-family"),
    text_element.attrib.get("font-size"),
    text_element.attrib.get("font-weight"),
    text_element.attrib.get("font-style"),
    text_element.attrib.get("fill"),
  )


def _mergeTextFragments(
  fragments: list[types.SvgTextFragment],
  collector: TextTargetCollector,
) -> ET.Element:
  """Merge one run of adjacent fragments into one text element with tspans."""

  merged_text = ET.Element(_TEXT_TAG)
  first_text = fragments[0].text_element
  for key, value in first_text.attrib.items():
    if key == "id":
      continue
    merged_text.set(key, value)

  merged_text.set(_XML_SPACE_ATTR, "preserve")
  for fragment in fragments:
    tspan = ET.SubElement(merged_text, f"{{{_SVG_NAMESPACE}}}tspan")
    tspan.text = fragment.text_element.text or ""
    if fragment.payload is None:
      continue
    fragment_id = collector.nextId()
    collector.record(fragment.payload, fragment_id)
    tspan.set("id", fragment_id)
  return merged_text


# Stateful helpers.


class TextTargetCollector:
  """Collect normalized SVG text fragments back into semantic highlight maps."""

  def __init__(self) -> None:
    """Initialize empty text-target buckets for all supported highlight kinds."""

    self._next_fragment_index = 1
    self._state_hook_section_ids: dict[tuple[str, str], list[str]] = {}
    self._state_hook_activity_ids: dict[tuple[str, str, str], list[str]] = {}
    self._initial_transition_label_ids: dict[str, list[str]] = {}
    self._initial_transition_activity_ids: dict[tuple[str, str], list[str]] = {}
    self._external_transition_label_ids: dict[str, list[str]] = {}
    self._external_transition_activity_ids: dict[tuple[str, str], list[str]] = {}
    self._guard_node_text_ids: dict[tuple[str, str], list[str]] = {}
    self._internal_transition_section_ids: dict[str, list[str]] = {}
    self._internal_transition_event_ids: dict[str, list[str]] = {}
    self._internal_transition_activity_ids: dict[tuple[str, str], list[str]] = {}

  def nextId(self) -> str:
    """Return the next deterministic generated text-fragment id."""

    fragment_id = f"{_TEXT_FRAGMENT_ID_PREFIX}{self._next_fragment_index:04d}"
    self._next_fragment_index += 1
    return fragment_id

  def record(self, payload: str, fragment_id: str) -> None:
    """Record one semantic payload against one generated text-fragment id."""

    parts = payload.split("|")
    kind = parts[0]
    if kind == "state_hook_section" and len(parts) == 3:
      self._state_hook_section_ids.setdefault((parts[1], parts[2]), []).append(
        fragment_id
      )
      return
    if kind == "state_hook_activity" and len(parts) == 4:
      self._state_hook_activity_ids.setdefault(
        (parts[1], parts[2], parts[3]),
        [],
      ).append(fragment_id)
      return
    if kind == "initial_transition_label" and len(parts) == 2:
      self._initial_transition_label_ids.setdefault(parts[1], []).append(fragment_id)
      return
    if kind == "initial_transition_activity" and len(parts) == 3:
      self._initial_transition_activity_ids.setdefault(
        (parts[1], parts[2]),
        [],
      ).append(fragment_id)
      return
    if kind == "external_transition_label" and len(parts) == 2:
      self._external_transition_label_ids.setdefault(parts[1], []).append(fragment_id)
      return
    if kind == "external_transition_activity" and len(parts) == 3:
      self._external_transition_activity_ids.setdefault(
        (parts[1], parts[2]),
        [],
      ).append(fragment_id)
      return
    if kind == "guard_node_text" and len(parts) == 3:
      self._guard_node_text_ids.setdefault((parts[1], parts[2]), []).append(fragment_id)
      return
    if kind == "internal_transition_section" and len(parts) == 2:
      self._internal_transition_section_ids.setdefault(parts[1], []).append(fragment_id)
      return
    if kind == "internal_transition_event" and len(parts) == 2:
      self._internal_transition_event_ids.setdefault(parts[1], []).append(fragment_id)
      return
    if kind == "internal_transition_activity" and len(parts) == 3:
      self._internal_transition_activity_ids.setdefault(
        (parts[1], parts[2]),
        [],
      ).append(fragment_id)

  def build(self) -> types.NormalizedSvgTextTargets:
    """Freeze the collected text-target maps into tuples for public use."""

    return types.NormalizedSvgTextTargets(
      state_hook_section_ids={
        key: tuple(value)
        for key, value in self._state_hook_section_ids.items()
      },
      state_hook_activity_ids={
        key: tuple(value)
        for key, value in self._state_hook_activity_ids.items()
      },
      initial_transition_label_ids={
        key: tuple(value)
        for key, value in self._initial_transition_label_ids.items()
      },
      initial_transition_activity_ids={
        key: tuple(value)
        for key, value in self._initial_transition_activity_ids.items()
      },
      external_transition_label_ids={
        key: tuple(value)
        for key, value in self._external_transition_label_ids.items()
      },
      external_transition_activity_ids={
        key: tuple(value)
        for key, value in self._external_transition_activity_ids.items()
      },
      guard_node_text_ids={
        key: tuple(value)
        for key, value in self._guard_node_text_ids.items()
      },
      internal_transition_section_ids={
        key: tuple(value)
        for key, value in self._internal_transition_section_ids.items()
      },
      internal_transition_event_ids={
        key: tuple(value)
        for key, value in self._internal_transition_event_ids.items()
      },
      internal_transition_activity_ids={
        key: tuple(value)
        for key, value in self._internal_transition_activity_ids.items()
      },
    )


class SvgIdRegistry:
  """Allocate deterministic SVG ids and suffix only when a collision occurs."""

  def __init__(self) -> None:
    """Initialize one empty derived-id registry."""

    self._counts: dict[str, int] = {}

  def make(self, base_id: str) -> str:
    """Return one unique public SVG id from one structural base id."""

    count = self._counts.get(base_id, 0) + 1
    self._counts[base_id] = count
    if count == 1:
      return base_id
    return f"{base_id}_{count}"


class RoutingHelperRegistry:
  """Own the small set of helper nodes used to route edges through Graphviz."""

  def __init__(self) -> None:
    """Initialize one empty helper-node registry."""

    self._helpers_by_id: dict[str, types.RenderRoutingHelper] = {}
    self._ordered_helper_ids: list[str] = []

  def ordered(self) -> tuple[types.RenderRoutingHelper, ...]:
    """Return helpers in deterministic registration order."""

    return tuple(
      self._helpers_by_id[helper_id]
      for helper_id in self._ordered_helper_ids
    )

  def rootInitialSource(self, owner_svg_id: str) -> str:
    """Return the helper source id used for the root initial transition."""

    return self._register(
      f"routing_helper_root_initial_source_{owner_svg_id}",
      None,
      "visible_source",
    )

  def localInitialSource(self, parent_svg_id: str) -> str:
    """Return the helper source id used for one local initial transition."""

    return self._register(
      f"routing_helper_local_initial_source_{parent_svg_id}",
      parent_svg_id,
      "visible_source",
    )

  def compoundAnchor(self, parent_svg_id: str) -> str:
    """Return the private helper anchor used to target one compound state."""

    return self._register(
      f"routing_helper_compound_anchor_{parent_svg_id}",
      parent_svg_id,
      "private_anchor",
    )

  def _register(
    self,
    helper_id: str,
    parent_svg_id: str | None,
    visibility: str,
  ) -> str:
    """Register one helper node only once and return its id."""

    if helper_id not in self._helpers_by_id:
      self._helpers_by_id[helper_id] = types.RenderRoutingHelper(
        id=helper_id,
        parent_svg_id=parent_svg_id,
        visibility=visibility,
      )
      self._ordered_helper_ids.append(helper_id)
    return helper_id


# Small utilities.


def _deriveFillRgb(depth: int) -> str:
  """Derive one readable fill color from one state nesting depth."""

  if depth == 0:
    return _hexRgb(_BASE_FILL_RGB)
  hue = (_BASE_FILL_HLS[0] + (depth * _DEPTH_HUE_STEP)) % 1.0
  lightness = min(
    _BASE_FILL_HLS[1] + (depth * _DEPTH_LIGHTNESS_STEP),
    _MAX_DERIVED_LIGHTNESS,
  )
  rgb = tuple(
    round(channel * 255)
    for channel in colorsys.hls_to_rgb(
      hue,
      lightness,
      _DERIVED_FILL_SATURATION,
    )
  )
  return _hexRgb(rgb)


def _hexRgb(rgb: tuple[int, int, int]) -> str:
  """Return one RGB triple formatted as a hex color string."""

  return "#%02X%02X%02X" % rgb


def duplicateValues(values: tuple[str, ...]) -> list[str]:
  """Return the distinct duplicate values present in one sequence."""

  seen: set[str] = set()
  duplicates: list[str] = []
  for value in values:
    if value in seen and value not in duplicates:
      duplicates.append(value)
    seen.add(value)
  return duplicates
