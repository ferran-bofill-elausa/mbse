from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from mbse_web_viewer.svg_render import extract_svg_ids
from mbse_web_viewer.svg_render import normalize_svg_text_fragments
from mbse_web_viewer.svg_render.graphviz.exceptions import GraphvizValidationError


def test_extract_svg_ids_returns_authored_exact_ids_in_document_order():
  svg_text = """
  <svg xmlns="http://www.w3.org/2000/svg">
    <g id="state_idle">
      <title>Idle</title>
    </g>
    <path id="edge_start" d="M0 0 L10 10" />
  </svg>
  """

  assert extract_svg_ids(svg_text) == ("state_idle", "edge_start")


def test_extract_svg_ids_rejects_duplicate_ids():
  svg_text = """
  <svg xmlns="http://www.w3.org/2000/svg">
    <g id="state_idle" />
    <path id="state_idle" d="M0 0 L10 10" />
  </svg>
  """

  with pytest.raises(GraphvizValidationError) as excinfo:
    extract_svg_ids(svg_text)

  assert excinfo.value.code == "rendered_svg.duplicate_id"
  assert excinfo.value.message == "Rendered SVG contains duplicate id 'state_idle'."


def test_normalize_svg_text_fragments_mints_private_ids_and_strips_markers():
  svg_text = (
    '<svg xmlns="http://www.w3.org/2000/svg">'
    '<g id="state_idle"></g>'
    '<g id="generated_wrapper">'
    '<a xmlns:xlink="http://www.w3.org/1999/xlink" xlink:title="lifecycle_section|idle|on_entry">'
    '<text x="10" y="10">on_entry:</text>'
    '</a>'
    '</g>'
    '<g id="generated_wrapper_2">'
    '<a xmlns:xlink="http://www.w3.org/1999/xlink" xlink:title="lifecycle_activity|idle|on_entry|enter_idle">'
    '<text x="10" y="20">enter_idle</text>'
    '</a>'
    '</g>'
    '<g id="generated_wrapper_3">'
    '<a xmlns:xlink="http://www.w3.org/1999/xlink" xlink:title="external_transition_label|idle_to_open">'
    '<text x="10" y="30">open_evt</text>'
    '</a>'
    '</g>'
    '<g id="generated_wrapper_4">'
    '<a xmlns:xlink="http://www.w3.org/1999/xlink" xlink:title="external_transition_activity|idle_to_open|trace_open">'
    '<text x="10" y="40">trace_open</text>'
    '</a>'
    '</g>'
    '</svg>'
  )

  normalized = normalize_svg_text_fragments(svg_text)

  assert extract_svg_ids(normalized.svg_text) == (
    "state_idle",
    "__mbse_text_fragment__0001",
    "__mbse_text_fragment__0002",
    "__mbse_text_fragment__0003",
    "__mbse_text_fragment__0004",
  )
  assert "xlink:title" not in normalized.svg_text
  assert "generated_wrapper" not in normalized.svg_text
  assert normalized.text_targets.lifecycle_section_ids == {
    "idle": {"on_entry": ("__mbse_text_fragment__0001",)}
  }
  assert normalized.text_targets.lifecycle_activity_ids == {
    "idle": {"on_entry": {"enter_idle": ("__mbse_text_fragment__0002",)}}
  }
  assert normalized.text_targets.external_transition_label_ids == {
    "idle_to_open": ("__mbse_text_fragment__0003",)
  }
  assert normalized.text_targets.external_transition_activity_ids == {
    "idle_to_open": {"trace_open": ("__mbse_text_fragment__0004",)}
  }


def test_normalize_svg_text_fragments_omits_unmappable_targets_without_retargeting():
  svg_text = (
    '<svg xmlns="http://www.w3.org/2000/svg">'
    '<g id="state_idle"></g>'
    '<g>'
    '<a xmlns:xlink="http://www.w3.org/1999/xlink" xlink:title="external_transition_label|idle_to_open">'
    '<text>open_evt</text>'
    '<text>duplicate</text>'
    '</a>'
    '</g>'
    '</svg>'
  )

  normalized = normalize_svg_text_fragments(svg_text)

  assert extract_svg_ids(normalized.svg_text) == ("state_idle",)
  assert normalized.text_targets.external_transition_label_ids == {}


def test_normalize_svg_text_fragments_preserves_existing_text_positions_and_alignment():
  svg_text = (
    '<svg xmlns="http://www.w3.org/2000/svg">'
    '<g id="state_idle">'
    '<text x="15" y="20">on_exit:</text>'
    '<text x="15" y="35">&#45; </text>'
    '<g id="generated_wrapper">'
    '<a xmlns:xlink="http://www.w3.org/1999/xlink" xlink:title="lifecycle_activity|idle|on_exit|exit_idle">'
    '<text x="25" y="35">exit_idle</text>'
    '</a>'
    '</g>'
    '</g>'
    '</svg>'
  )

  normalized = normalize_svg_text_fragments(svg_text)
  root = ET.fromstring(normalized.svg_text)
  text_nodes = root.findall('.//{http://www.w3.org/2000/svg}text')
  merged_line = next(node for node in text_nodes if node.attrib.get("y") == "35")
  spans = merged_line.findall('{http://www.w3.org/2000/svg}tspan')

  assert 'x="15" y="20"' in normalized.svg_text
  assert 'x="15" y="35"' in normalized.svg_text
  assert merged_line.attrib["x"] == "15"
  assert merged_line.attrib['{http://www.w3.org/XML/1998/namespace}space'] == "preserve"
  assert [span.text for span in spans] == ["- ", "exit_idle"]
  assert spans[1].attrib["id"] == "__mbse_text_fragment__0001"
  assert normalized.text_targets.lifecycle_activity_ids == {
    "idle": {"on_exit": {"exit_idle": ("__mbse_text_fragment__0001",)}}
  }


def test_normalize_svg_text_fragments_collapses_transition_separator_spacing():
  svg_text = (
    '<svg xmlns="http://www.w3.org/2000/svg">'
    '<g id="edge_idle_to_open">'
    '<g id="generated_event">'
    '<a xmlns:xlink="http://www.w3.org/1999/xlink" xlink:title="external_transition_label|idle_to_open">'
    '<text x="10" y="25">open_evt/</text>'
    '</a>'
    '</g>'
    '<g id="generated_activity">'
    '<a xmlns:xlink="http://www.w3.org/1999/xlink" xlink:title="external_transition_activity|idle_to_open|trace_open">'
    '<text x="80" y="25">trace_open</text>'
    '</a>'
    '</g>'
    '</g>'
    '</svg>'
  )

  normalized = normalize_svg_text_fragments(svg_text)
  root = ET.fromstring(normalized.svg_text)
  merged_line = root.find('.//{http://www.w3.org/2000/svg}text')
  assert merged_line is not None
  spans = merged_line.findall('{http://www.w3.org/2000/svg}tspan')

  assert merged_line.attrib["x"] == "10"
  assert [span.text for span in spans] == ["open_evt/", "trace_open"]
  assert spans[0].attrib["id"] == "__mbse_text_fragment__0001"
  assert spans[1].attrib["id"] == "__mbse_text_fragment__0002"
  assert normalized.text_targets.external_transition_label_ids == {
    "idle_to_open": ("__mbse_text_fragment__0001",)
  }
  assert normalized.text_targets.external_transition_activity_ids == {
    "idle_to_open": {"trace_open": ("__mbse_text_fragment__0002",)}
  }
