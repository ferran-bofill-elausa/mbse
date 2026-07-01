from __future__ import annotations

"""Internal helpers used by `ActivityRender`."""

from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

from mbse_web_viewer.render.activity import activity_render_types as types


TEMPLATE_NAME = "activity_render.dot.j2"
TEMPLATES_DIR = Path(__file__).resolve().parent
SVG_NAMESPACE = "http://www.w3.org/2000/svg"
ANCHOR_TAG = f"{{{SVG_NAMESPACE}}}a"
_TEXT_FRAGMENT_ID_PREFIX = "text_fragment_"
_XLINK_NAMESPACE = "http://www.w3.org/1999/xlink"
_XML_NAMESPACE = "http://www.w3.org/XML/1998/namespace"
_GROUP_TAG = f"{{{SVG_NAMESPACE}}}g"
_TEXT_TAG = f"{{{SVG_NAMESPACE}}}text"
_TITLE_ATTR = f"{{{_XLINK_NAMESPACE}}}title"
_XML_SPACE_ATTR = f"{{{_XML_NAMESPACE}}}space"


def executableKey(executable: dict[str, Any]) -> str:
  """Return one stable key for one executable reference."""

  if executable["kind"] == "model":
    return executable["model_id"]
  return f"{executable['module']}.{executable['name']}"


def executableLabel(executable: dict[str, Any]) -> str:
  """Return the human-readable label used in rendered text."""

  if executable["kind"] == "model":
    return executable["model_id"]
  return executable["name"]


def actionLabelLines(action: dict[str, Any]) -> tuple[types.RenderTextLine, ...]:
  """Return rendered label lines for one action node."""

  executable = action["executable"]
  return (
    types.RenderTextLine(
      fragments=(
        types.RenderTextFragment(
          text=action["label"],
          target_payload=f"action_label|{action['id']}",
        ),
      )
    ),
    types.RenderTextLine(
      fragments=(
        types.RenderTextFragment(text="actions: "),
        types.RenderTextFragment(
          text=executableLabel(executable),
          target_payload=f"action_executable|{action['id']}|{executableKey(executable)}",
        ),
      )
    ),
  )


def decisionLabelLines(decision: dict[str, Any]) -> tuple[types.RenderTextLine, ...]:
  """Return rendered label lines for one decision node."""

  condition = decision["condition"]
  return (
    types.RenderTextLine(
      fragments=(
        types.RenderTextFragment(
          text=decision["label"],
          target_payload=f"decision_label|{decision['id']}",
        ),
      )
    ),
    types.RenderTextLine(
      fragments=(
        types.RenderTextFragment(text="if: "),
        types.RenderTextFragment(
          text=executableLabel(condition),
          target_payload=f"decision_condition|{decision['id']}|{executableKey(condition)}",
        ),
      )
    ),
  )


def finalLabelLines(final: dict[str, Any]) -> tuple[types.RenderTextLine, ...]:
  """Return rendered label lines for one final node."""

  return (
    types.RenderTextLine(
      fragments=(
        types.RenderTextFragment(
          text=final["label"],
          target_payload=f"final_label|{final['id']}",
        ),
      )
    ),
  )


def transitionLabelLine(edge_id: str, label: str) -> types.RenderTextLine:
  """Return the rendered label for one transition edge."""

  return types.RenderTextLine(
    fragments=(
      types.RenderTextFragment(
        text=label,
        target_payload=f"transition_label|{edge_id}",
      ),
    )
  )


def collapseTextFragmentRuns(parent: ET.Element, collector: TextTargetCollector) -> None:
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


def normalizeAnchorTarget(
  anchor: ET.Element,
  collector: TextTargetCollector,
) -> None:
  """Assign stable ids to unmerged anchored text fragments."""

  payload = anchor.attrib.get(_TITLE_ATTR)
  if payload is None:
    return
  for text_element in anchor.iter(_TEXT_TAG):
    fragment_id = collector.nextId()
    collector.record(payload, fragment_id)
    text_element.set("id", fragment_id)


def stripGeneratedAnchorGroupIds(root: ET.Element) -> None:
  """Drop wrapper ids introduced by Graphviz so only semantic ids remain public."""

  for element in root.iter():
    if element.tag != _GROUP_TAG or len(element) != 1 or element[0].tag != ANCHOR_TAG:
      continue
    element.attrib.pop("id", None)


def duplicateValues(values: tuple[str, ...]) -> list[str]:
  """Return the distinct duplicate values present in one sequence."""

  seen: set[str] = set()
  duplicates: list[str] = []
  for value in values:
    if value in seen and value not in duplicates:
      duplicates.append(value)
    seen.add(value)
  return duplicates


def _extractSvgTextFragment(element: ET.Element) -> types.SvgTextFragment | None:
  """Extract one candidate text fragment from the raw Graphviz SVG tree."""

  if element.tag == _TEXT_TAG and (element.text or ""):
    return types.SvgTextFragment(wrapper=element, text_element=element, payload=None)
  if element.tag == ANCHOR_TAG:
    return _extractAnchorFragment(element, wrapper=element)
  if element.tag != _GROUP_TAG or len(element) != 1 or element[0].tag != ANCHOR_TAG:
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
    tspan = ET.SubElement(merged_text, f"{{{SVG_NAMESPACE}}}tspan")
    tspan.text = fragment.text_element.text or ""
    if fragment.payload is None:
      continue
    fragment_id = collector.nextId()
    collector.record(fragment.payload, fragment_id)
    tspan.set("id", fragment_id)
  return merged_text


class TextTargetCollector:
  """Collect normalized SVG text fragments back into semantic highlight maps."""

  def __init__(self) -> None:
    """Initialize empty text-target buckets for Activity highlight kinds."""

    self._next_fragment_index = 1
    self._action_label_ids: dict[str, list[str]] = {}
    self._action_executable_ids: dict[tuple[str, str], list[str]] = {}
    self._decision_label_ids: dict[str, list[str]] = {}
    self._decision_condition_ids: dict[tuple[str, str], list[str]] = {}
    self._final_label_ids: dict[str, list[str]] = {}
    self._transition_label_ids: dict[str, list[str]] = {}

  def nextId(self) -> str:
    """Return the next deterministic generated text-fragment id."""

    fragment_id = f"{_TEXT_FRAGMENT_ID_PREFIX}{self._next_fragment_index:04d}"
    self._next_fragment_index += 1
    return fragment_id

  def record(self, payload: str, fragment_id: str) -> None:
    """Record one semantic payload against one generated text-fragment id."""

    parts = payload.split("|")
    kind = parts[0]
    if kind == "action_label" and len(parts) == 2:
      self._action_label_ids.setdefault(parts[1], []).append(fragment_id)
      return
    if kind == "action_executable" and len(parts) == 3:
      self._action_executable_ids.setdefault((parts[1], parts[2]), []).append(
        fragment_id
      )
      return
    if kind == "decision_label" and len(parts) == 2:
      self._decision_label_ids.setdefault(parts[1], []).append(fragment_id)
      return
    if kind == "decision_condition" and len(parts) == 3:
      self._decision_condition_ids.setdefault((parts[1], parts[2]), []).append(
        fragment_id
      )
      return
    if kind == "final_label" and len(parts) == 2:
      self._final_label_ids.setdefault(parts[1], []).append(fragment_id)
      return
    if kind == "transition_label" and len(parts) == 2:
      self._transition_label_ids.setdefault(parts[1], []).append(fragment_id)

  def build(self) -> types.NormalizedSvgTextTargets:
    """Freeze the collected text-target maps into tuples for public use."""

    return types.NormalizedSvgTextTargets(
      action_label_ids={key: tuple(value) for key, value in self._action_label_ids.items()},
      action_executable_ids={
        key: tuple(value)
        for key, value in self._action_executable_ids.items()
      },
      decision_label_ids={
        key: tuple(value)
        for key, value in self._decision_label_ids.items()
      },
      decision_condition_ids={
        key: tuple(value)
        for key, value in self._decision_condition_ids.items()
      },
      final_label_ids={key: tuple(value) for key, value in self._final_label_ids.items()},
      transition_label_ids={
        key: tuple(value)
        for key, value in self._transition_label_ids.items()
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
