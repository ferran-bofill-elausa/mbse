from __future__ import annotations

from dataclasses import dataclass
import xml.etree.ElementTree as ET

from mbse_web_viewer.app.viewer_state_types import RuntimeViewerTextTargets
from mbse_web_viewer.svg_render.graphviz.exceptions import GraphvizValidationError


TEXT_FRAGMENT_ID_PREFIX = "__mbse_text_fragment__"
SVG_NAMESPACE = "http://www.w3.org/2000/svg"
XLINK_NAMESPACE = "http://www.w3.org/1999/xlink"
XML_NAMESPACE = "http://www.w3.org/XML/1998/namespace"
GROUP_TAG = f"{{{SVG_NAMESPACE}}}g"
ANCHOR_TAG = f"{{{SVG_NAMESPACE}}}a"
TEXT_TAG = f"{{{SVG_NAMESPACE}}}text"
TITLE_ATTR = f"{{{XLINK_NAMESPACE}}}title"
XML_SPACE_ATTR = f"{{{XML_NAMESPACE}}}space"


@dataclass(frozen=True)
class NormalizedSvgTextFragments:
  svg_text: str
  text_targets: RuntimeViewerTextTargets


@dataclass(frozen=True)
class _SvgTextFragment:
  wrapper: ET.Element
  text_element: ET.Element
  payload: str | None


def extract_svg_ids(svg_text: str) -> tuple[str, ...]:
  root = ET.fromstring(svg_text)
  ids = tuple(
    element_id
    for element in root.iter()
    if (element_id := element.attrib.get("id")) is not None
  )
  duplicates = _duplicate_values(ids)
  if duplicates:
    duplicate = duplicates[0]
    raise GraphvizValidationError(
      code="rendered_svg.duplicate_id",
      message=f"Rendered SVG contains duplicate id '{duplicate}'.",
    )
  return ids


def normalize_svg_text_fragments(svg_text: str) -> NormalizedSvgTextFragments:
  ET.register_namespace("", SVG_NAMESPACE)
  root = ET.fromstring(svg_text)
  collector = _TextTargetCollector()
  _collapse_text_fragment_runs(root, collector)
  for element in root.iter():
    if element.tag == ANCHOR_TAG:
      _normalize_anchor_target(element, collector)
  _strip_generated_anchor_group_ids(root)
  normalized_svg = ET.tostring(root, encoding="unicode")
  return NormalizedSvgTextFragments(
    svg_text=normalized_svg,
    text_targets=collector.build(),
  )


def validate_rendered_contract(
  expected_ids: tuple[str, ...],
  rendered_ids: tuple[str, ...],
) -> None:
  rendered_id_set = set(rendered_ids)
  for expected_id in expected_ids:
    if expected_id not in rendered_id_set:
      raise GraphvizValidationError(
        code="rendered_svg.missing_id",
        message=f"Rendered SVG is missing expected id '{expected_id}'.",
      )


def _normalize_anchor_target(
  anchor: ET.Element,
  collector: "_TextTargetCollector",
) -> None:
  payload = anchor.attrib.pop(TITLE_ATTR, None)
  if payload is None:
    return
  text_elements = [element for element in anchor.iter() if element.tag == TEXT_TAG]
  if len(text_elements) != 1:
    return
  text_element = text_elements[0]
  if not (text_element.text or ""):
    return
  fragment_id = collector.next_id()
  collector.record(payload, fragment_id)
  text_element.set("id", fragment_id)


def _collapse_text_fragment_runs(
  parent: ET.Element,
  collector: "_TextTargetCollector",
) -> None:
  children = list(parent)
  if not children:
    return
  normalized_children: list[ET.Element] = []
  index = 0
  while index < len(children):
    child = children[index]
    fragment = _extract_svg_text_fragment(child)
    if fragment is None:
      _collapse_text_fragment_runs(child, collector)
      normalized_children.append(child)
      index += 1
      continue
    run = [fragment]
    next_index = index + 1
    while next_index < len(children):
      next_fragment = _extract_svg_text_fragment(children[next_index])
      if next_fragment is None or not _same_text_line(run[0], next_fragment):
        break
      run.append(next_fragment)
      next_index += 1
    if len(run) == 1:
      normalized_children.append(child)
    else:
      normalized_children.append(_merge_text_fragments(run, collector))
    index = next_index
  parent[:] = normalized_children


def _extract_svg_text_fragment(element: ET.Element) -> _SvgTextFragment | None:
  if element.tag == TEXT_TAG and (element.text or ""):
    return _SvgTextFragment(
      wrapper=element,
      text_element=element,
      payload=None,
    )
  if element.tag == ANCHOR_TAG:
    return _extract_anchor_fragment(element, wrapper=element)
  if element.tag != GROUP_TAG or len(element) != 1 or element[0].tag != ANCHOR_TAG:
    return None
  return _extract_anchor_fragment(element[0], wrapper=element)


def _extract_anchor_fragment(
  anchor: ET.Element,
  *,
  wrapper: ET.Element,
) -> _SvgTextFragment | None:
  payload = anchor.attrib.get(TITLE_ATTR)
  if payload is None:
    return None
  text_elements = [element for element in anchor.iter() if element.tag == TEXT_TAG]
  if len(text_elements) != 1:
    return None
  text_element = text_elements[0]
  if not (text_element.text or ""):
    return None
  return _SvgTextFragment(
    wrapper=wrapper,
    text_element=text_element,
    payload=payload,
  )


def _same_text_line(left: _SvgTextFragment, right: _SvgTextFragment) -> bool:
  return (
    left.text_element.attrib.get("y") == right.text_element.attrib.get("y")
    and _text_style_signature(left.text_element)
    == _text_style_signature(right.text_element)
  )


def _text_style_signature(text_element: ET.Element) -> tuple[str | None, ...]:
  return (
    text_element.attrib.get("text-anchor"),
    text_element.attrib.get("font-family"),
    text_element.attrib.get("font-size"),
    text_element.attrib.get("font-weight"),
    text_element.attrib.get("font-style"),
    text_element.attrib.get("fill"),
  )


def _merge_text_fragments(
  fragments: list[_SvgTextFragment],
  collector: "_TextTargetCollector",
) -> ET.Element:
  merged_text = ET.Element(TEXT_TAG)
  first_text = fragments[0].text_element
  for key, value in first_text.attrib.items():
    if key == "id":
      continue
    merged_text.set(key, value)
  merged_text.set(XML_SPACE_ATTR, "preserve")
  for fragment in fragments:
    tspan = ET.SubElement(merged_text, f"{{{SVG_NAMESPACE}}}tspan")
    tspan.text = fragment.text_element.text or ""
    if fragment.payload is None:
      continue
    fragment_id = collector.next_id()
    collector.record(fragment.payload, fragment_id)
    tspan.set("id", fragment_id)
  return merged_text


def _strip_generated_anchor_group_ids(root: ET.Element) -> None:
  for element in root.iter():
    if element.tag != GROUP_TAG:
      continue
    if len(element) != 1:
      continue
    child = element[0]
    if child.tag != ANCHOR_TAG:
      continue
    element.attrib.pop("id", None)


class _TextTargetCollector:
  def __init__(self) -> None:
    self._next_fragment_index = 1
    self._lifecycle_section_ids: dict[str, dict[str, list[str]]] = {}
    self._lifecycle_activity_ids: dict[str, dict[str, dict[str, list[str]]]] = {}
    self._external_transition_label_ids: dict[str, list[str]] = {}
    self._external_transition_activity_ids: dict[str, dict[str, list[str]]] = {}
    self._internal_transition_section_ids: dict[str, list[str]] = {}
    self._internal_transition_event_ids: dict[str, list[str]] = {}
    self._internal_transition_activity_ids: dict[str, dict[str, list[str]]] = {}

  def next_id(self) -> str:
    fragment_id = f"{TEXT_FRAGMENT_ID_PREFIX}{self._next_fragment_index:04d}"
    self._next_fragment_index += 1
    return fragment_id

  def record(self, payload: str, fragment_id: str) -> None:
    parts = payload.split("|")
    kind = parts[0]
    if kind == "lifecycle_section" and len(parts) == 3:
      self._lifecycle_section_ids.setdefault(parts[1], {}).setdefault(
        parts[2], []
      ).append(fragment_id)
      return
    if kind == "lifecycle_activity" and len(parts) == 4:
      self._lifecycle_activity_ids.setdefault(parts[1], {}).setdefault(
        parts[2], {}
      ).setdefault(parts[3], []).append(fragment_id)
      return
    if kind == "external_transition_label" and len(parts) == 2:
      self._external_transition_label_ids.setdefault(parts[1], []).append(
        fragment_id
      )
      return
    if kind == "external_transition_activity" and len(parts) == 3:
      self._external_transition_activity_ids.setdefault(parts[1], {}).setdefault(
        parts[2], []
      ).append(fragment_id)
      return
    if kind == "internal_transition_section" and len(parts) == 2:
      self._internal_transition_section_ids.setdefault(parts[1], []).append(
        fragment_id
      )
      return
    if kind == "internal_transition_event" and len(parts) == 2:
      self._internal_transition_event_ids.setdefault(parts[1], []).append(
        fragment_id
      )
      return
    if kind == "internal_transition_activity" and len(parts) == 3:
      self._internal_transition_activity_ids.setdefault(parts[1], {}).setdefault(
        parts[2], []
      ).append(fragment_id)

  def build(self) -> RuntimeViewerTextTargets:
    return RuntimeViewerTextTargets(
      lifecycle_section_ids=_freeze_nested_3(self._lifecycle_section_ids),
      lifecycle_activity_ids=_freeze_nested_4(self._lifecycle_activity_ids),
      external_transition_label_ids=_freeze_nested_2(
        self._external_transition_label_ids
      ),
      external_transition_activity_ids=_freeze_nested_3(
        self._external_transition_activity_ids
      ),
      internal_transition_section_ids=_freeze_nested_2(
        self._internal_transition_section_ids
      ),
      internal_transition_event_ids=_freeze_nested_2(
        self._internal_transition_event_ids
      ),
      internal_transition_activity_ids=_freeze_nested_3(
        self._internal_transition_activity_ids
      ),
    )


def _freeze_nested_2(values: dict[str, list[str]]) -> dict[str, tuple[str, ...]]:
  return {key: tuple(items) for key, items in values.items()}


def _freeze_nested_3(
  values: dict[str, dict[str, list[str]]],
) -> dict[str, dict[str, tuple[str, ...]]]:
  return {
    key: {inner_key: tuple(items) for inner_key, items in inner.items()}
    for key, inner in values.items()
  }


def _freeze_nested_4(
  values: dict[str, dict[str, dict[str, list[str]]]],
) -> dict[str, dict[str, dict[str, tuple[str, ...]]]]:
  return {
    key: {
      inner_key: {
        leaf_key: tuple(items) for leaf_key, items in leaf.items()
      }
      for inner_key, leaf in inner.items()
    }
    for key, inner in values.items()
  }


def _duplicate_values(values: tuple[str, ...]) -> list[str]:
  seen: set[str] = set()
  duplicates: list[str] = []
  for value in values:
    if value in seen and value not in duplicates:
      duplicates.append(value)
    seen.add(value)
  return duplicates


__all__ = [
  "NormalizedSvgTextFragments",
  "extract_svg_ids",
  "normalize_svg_text_fragments",
  "validate_rendered_contract",
]
