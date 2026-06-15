from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import sys

from mbse_web_viewer import build_viewer_session
from mbse_web_viewer.svg_render import extract_svg_ids
from tests.support.hsm_payloads import hsm_document
from tests.support.hsm_payloads import hsm_external_transition
from tests.support.hsm_payloads import hsm_guard
from tests.support.hsm_payloads import hsm_guard_branch
from tests.support.hsm_payloads import hsm_initial
from tests.support.hsm_payloads import hsm_internal_transition
from tests.support.hsm_payloads import hsm_state


def _callable_ref(name: str) -> dict[str, str]:
  return {
    "module": "tests.support.hsm_callable_fixtures",
    "name": name,
  }


def _hsm_payload() -> dict[str, object]:
  return hsm_document(
    "door_machine",
    variables=[{"id": "count", "default": 0}],
    events=[{"id": "open_evt", "parameters": [{"name": "source"}]}],
    initial_transition=hsm_initial("machine_init", "closed"),
    states=[
      hsm_state(
        "closed",
        label="Closed",
        on_entry=[_callable_ref("count_increment")],
        external_transitions=[
          hsm_external_transition(
            "closed_to_open",
            target_id="open",
            event_id="open_evt",
          )
        ],
      ),
      hsm_state("open", label="Open"),
    ],
  )


def _duplicate_label_hsm_payload() -> dict[str, object]:
  return hsm_document(
    "door_machine",
    events=[{"id": "open_evt"}],
    initial_transition=hsm_initial("machine_init", "left_closed"),
    states=[
      hsm_state(
        "left_closed",
        label="Closed",
        external_transitions=[
          hsm_external_transition(
            "left_to_right",
            target_id="right_closed",
            event_id="open_evt",
          )
        ],
      ),
      hsm_state("right_closed", label="Closed"),
    ],
  )


def _compound_hsm_payload() -> dict[str, object]:
  return hsm_document(
    "door_machine",
    events=[{"id": "open_evt"}],
    initial_transition=hsm_initial("machine_init", "parent"),
    states=[
      hsm_state(
        "parent",
        label="Parent",
        on_entry=[_callable_ref("enter_parent")],
        states=[
          hsm_state("child_a", label="Child A"),
          hsm_state("child_b", label="Child B"),
        ],
        initial_transition=hsm_initial("parent_init", "child_a"),
        external_transitions=[
          hsm_external_transition(
            "parent_to_sibling",
            target_id="sibling",
            event_id="open_evt",
          )
        ],
      ),
      hsm_state("sibling", label="Sibling"),
    ],
  )


def _compound_empty_actions_payload() -> dict[str, object]:
  return hsm_document(
    "empty_partition_machine",
    events=[{"id": "open_evt"}],
    initial_transition=hsm_initial("machine_init", "parent"),
    states=[
      hsm_state(
        "parent",
        label="Parent",
        states=[hsm_state("child", label="Child")],
        initial_transition=hsm_initial("parent_init", "child"),
        external_transitions=[
          hsm_external_transition(
            "parent_to_leaf",
            target_id="leaf",
            event_id="open_evt",
          )
        ],
      ),
      hsm_state("leaf", label="Leaf"),
    ],
  )


def _compound_local_initial_to_compound_payload() -> dict[str, object]:
  return hsm_document(
    "compound_local_init_machine",
    initial_transition=hsm_initial("machine_init", "parent"),
    states=[
      hsm_state(
        "parent",
        label="Parent",
        states=[
          hsm_state(
            "child_group",
            label="Child Group",
            states=[hsm_state("leaf", label="Leaf")],
            initial_transition=hsm_initial("child_group_init", "leaf"),
          ),
          hsm_state("child_b", label="Child B"),
        ],
        initial_transition=hsm_initial("parent_init", "child_group"),
      )
    ],
  )


def _activity_parity_hsm_payload() -> dict[str, object]:
  return hsm_document(
    "activity_parity_machine",
    events=[
      {"id": "open_evt", "parameters": [{"name": "source"}]},
      {"id": "tick_evt"},
      {"id": "close_evt"},
    ],
    initial_transition=hsm_initial("machine_init", "parent"),
    states=[
      hsm_state(
        "parent",
        label="Parent",
        on_initial=[_callable_ref("trace_parent_initial")],
        on_entry=[_callable_ref("enter_parent")],
        on_exit=[_callable_ref("exit_parent")],
        states=[hsm_state("child", label="Child")],
        initial_transition=hsm_initial("parent_init", "child"),
        external_transitions=[
          hsm_external_transition(
            "parent_to_sibling",
            event_id="open_evt",
            guard=hsm_guard(
              guard_id="parent_to_sibling_guard",
              guard=_callable_ref("guard_true"),
              true_branch=hsm_guard_branch(
                "sibling",
                activities=[_callable_ref("trace_transition_activity")],
              ),
              false_branch=hsm_guard_branch("child", activities=[]),
            ),
          )
        ],
        internal_transitions=[
          hsm_internal_transition(
            "parent_internal",
            event_id="tick_evt",
            activities=[_callable_ref("trace_internal_activity")],
          )
        ],
      ),
      hsm_state("sibling", label="Sibling"),
    ],
  )


def _write_hsm_input(path: Path) -> None:
  path.write_text(json.dumps(_hsm_payload(), indent=2), encoding="utf-8")


def _write_duplicate_label_hsm_input(path: Path) -> None:
  path.write_text(json.dumps(_duplicate_label_hsm_payload(), indent=2), encoding="utf-8")


def _write_compound_hsm_input(path: Path) -> None:
  path.write_text(json.dumps(_compound_hsm_payload(), indent=2), encoding="utf-8")


def _write_compound_empty_actions_hsm_input(path: Path) -> None:
  path.write_text(
    json.dumps(_compound_empty_actions_payload(), indent=2),
    encoding="utf-8",
  )


def _write_compound_local_initial_to_compound_hsm_input(path: Path) -> None:
  path.write_text(
    json.dumps(_compound_local_initial_to_compound_payload(), indent=2),
    encoding="utf-8",
  )


def _write_activity_parity_hsm_input(path: Path) -> None:
  path.write_text(
    json.dumps(_activity_parity_hsm_payload(), indent=2),
    encoding="utf-8",
  )


def _test_hsm_demo_path() -> Path:
  return Path(__file__).resolve().parents[2] / "test_hsm" / "hsm.json"


def _fake_graphviz_command() -> tuple[str, ...]:
  script = (
    "import re, sys; "
    "dot = sys.stdin.read(); "
    "ids = re.findall(r'id=\\\"([^\\\"]+)\\\"', dot); "
    "body = ''.join(f'<g id=\\\"{item}\\\"></g>' for item in ids); "
    "sys.stdout.write(f'<svg xmlns=\\\"http://www.w3.org/2000/svg\\\">{body}</svg>')"
  )
  return (sys.executable, "-c", script)


def _fake_helper_visibility_contract_command() -> tuple[str, ...]:
  script = (
    "import re, sys; "
    "dot = sys.stdin.read(); "
    "public_ids = re.findall(r'id=\\\"([^\\\"]+)\\\"', dot); "
    "node_matches = re.finditer(r'\\\"([^\\\"]+)\\\" \\[(.*?)\\];', dot, re.S); "
    "helper_visuals = [m.group(1) for m in node_matches if 'style=\\\"invis\\\"' not in m.group(2) and 'style=invis' not in m.group(2) and 'id=' not in m.group(2)]; "
    "public_body = ''.join(f'<g id=\\\"{item}\\\"></g>' for item in public_ids); "
    "helper_body = ''.join(f'<g class=\\\"node\\\"><title>{item}</title><ellipse fill=\\\"black\\\" stroke=\\\"black\\\"></ellipse></g>' for item in helper_visuals); "
    "body = public_body + helper_body; "
    "sys.stdout.write(f'<svg xmlns=\\\"http://www.w3.org/2000/svg\\\">{body}</svg>')"
  )
  return (sys.executable, "-c", script)


def _fake_graphviz_text_contract_command() -> tuple[str, ...]:
  script = (
    "import html, re, sys; "
    "dot = sys.stdin.read(); "
    "ids = re.findall(r'id=\\\"([^\\\"]+)\\\"', dot); "
    "public_body = ''.join(f'<g id=\\\"{item}\\\"></g>' for item in ids); "
    "targets = re.findall(r'TOOLTIP=\\\"([^\\\"]+)\\\">([^<]+)</TD>', dot); "
    "target_body = ''.join(f'<g><a xmlns:xlink=\\\"http://www.w3.org/1999/xlink\\\" xlink:title=\\\"{html.escape(payload)}\\\"><text>{html.escape(text)}</text></a></g>' for payload, text in targets); "
    "sys.stdout.write("
    "f'<svg xmlns=\\\"http://www.w3.org/2000/svg\\\">'"
    "f'{public_body}{target_body}</svg>'"
    ")"
  )
  return (sys.executable, "-c", script)


def _assert_svg_contains_exact_public_ids(
  svg_text: str,
  public_ids: tuple[str, ...],
  *,
  private_ids: tuple[str, ...] = (),
) -> None:
  extracted_ids = extract_svg_ids(svg_text)
  for public_id in public_ids:
    assert extracted_ids.count(public_id) == 1
  for private_id in private_ids:
    assert private_id not in extracted_ids


def _assert_dot_contains_exact_public_ids(
  dot_source: str,
  public_ids: tuple[str, ...],
) -> None:
  assert tuple(re.findall(r'id="([^"]+)"', dot_source)) == public_ids


def _strip_text_markers(value: str) -> str:
  value = re.sub(r"__MBSE_START__[\s\S]*?__", "", value)
  value = re.sub(r"__MBSE_END__[\s\S]*?__", "", value)
  return value


def test_build_viewer_session_accepts_hsm_json_and_emits_deterministic_prepared_output(
  tmp_path,
):
  hsm_path = tmp_path / "door-machine.json"
  first_output_dir = tmp_path / "session-a"
  second_output_dir = tmp_path / "session-b"
  _write_hsm_input(hsm_path)

  first_session = build_viewer_session(
    hsm_path,
    first_output_dir,
    graphviz_command=_fake_graphviz_command(),
  )
  second_session = build_viewer_session(
    hsm_path,
    second_output_dir,
    graphviz_command=_fake_graphviz_command(),
  )

  assert first_session == second_session
  assert json.loads(
    (first_output_dir / "prepared-document.json").read_text(encoding="utf-8")
  ) == json.loads(
    (second_output_dir / "prepared-document.json").read_text(encoding="utf-8")
  )


def test_build_viewer_session_accepts_test_hsm_guard_node_demo(tmp_path):
  output_dir = tmp_path / "session-artifacts"

  session = build_viewer_session(
    _test_hsm_demo_path(),
    output_dir,
    graphviz_command=_fake_graphviz_command(),
  )

  assert session.highlightable_ids == (
    "session",
    "idle",
    "active",
    "shutdown",
    "job_check",
    "machine_init",
    "session_init",
    "idle_to_job_check",
    "job_check_true",
    "job_check_false",
    "active_refresh",
    "active_to_idle",
    "session_to_shutdown",
  )
  prepared_document = json.loads(
    (output_dir / "prepared-document.json").read_text(encoding="utf-8")
  )
  assert '"job_check" -> "active" [id="job_check_true", label=<' in prepared_document["dot_source"]
  assert '"__routing_helper_compound_anchor__session" -> "shutdown" ' in prepared_document["dot_source"]
  assert 'id="session_to_shutdown"' in prepared_document["dot_source"]
  assert 'ltail="cluster_session"' in prepared_document["dot_source"]


def test_build_viewer_session_preserves_exact_svg_ids_for_hsm_contract(tmp_path):
  hsm_path = tmp_path / "door-machine.json"
  output_dir = tmp_path / "session-artifacts"
  _write_hsm_input(hsm_path)

  session = build_viewer_session(
    hsm_path,
    output_dir,
    graphviz_command=_fake_graphviz_command(),
  )

  assert session.highlightable_ids == (
    "closed",
    "open",
    "machine_init",
    "closed_to_open",
  )
  prepared_document = json.loads(
    (output_dir / "prepared-document.json").read_text(encoding="utf-8")
  )
  _assert_dot_contains_exact_public_ids(
    prepared_document["dot_source"],
    session.highlightable_ids,
  )
  assert prepared_document["document_id"] == "door_machine"
  assert prepared_document["highlightable_ids"] == [
    "closed",
    "open",
    "machine_init",
    "closed_to_open",
  ]
  assert '"closed" [id="closed", shape=box, label=<' in prepared_document[
    "dot_source"
  ]
  assert "<B>Closed</B>" in prepared_document["dot_source"]
  assert "on_entry:" in prepared_document["dot_source"]
  assert "count_increment" in prepared_document["dot_source"]
  assert '"open" [id="open", shape=box, label=<' in prepared_document[
    "dot_source"
  ]
  assert "Variables:" not in prepared_document["dot_source"]
  assert "Events:" not in prepared_document["dot_source"]
  svg_text = (output_dir / "diagram.svg").read_text(encoding="utf-8")
  _assert_svg_contains_exact_public_ids(svg_text, session.highlightable_ids)


def test_build_viewer_session_keeps_distinct_ids_when_labels_repeat(tmp_path):
  hsm_path = tmp_path / "duplicate-labels.json"
  output_dir = tmp_path / "session-artifacts"
  _write_duplicate_label_hsm_input(hsm_path)

  session = build_viewer_session(
    hsm_path,
    output_dir,
    graphviz_command=_fake_graphviz_command(),
  )

  assert session.highlightable_ids == (
    "left_closed",
    "right_closed",
    "machine_init",
    "left_to_right",
  )
  prepared_document = json.loads(
    (output_dir / "prepared-document.json").read_text(encoding="utf-8")
  )
  _assert_dot_contains_exact_public_ids(
    prepared_document["dot_source"],
    session.highlightable_ids,
  )
  assert prepared_document["highlightable_ids"] == [
    "left_closed",
    "right_closed",
    "machine_init",
    "left_to_right",
  ]
  assert 'id="left_closed"' in prepared_document["dot_source"]
  assert 'id="right_closed"' in prepared_document["dot_source"]
  svg_text = (output_dir / "diagram.svg").read_text(encoding="utf-8")
  _assert_svg_contains_exact_public_ids(svg_text, session.highlightable_ids)
  assert '<B>Closed</B>' in prepared_document["dot_source"]


def test_build_viewer_session_keeps_exact_compound_svg_id_once(tmp_path):
  hsm_path = tmp_path / "compound.json"
  output_dir = tmp_path / "session-artifacts"
  _write_compound_hsm_input(hsm_path)

  session = build_viewer_session(
    hsm_path,
    output_dir,
    graphviz_command=_fake_graphviz_command(),
  )

  assert session.highlightable_ids == (
    "parent",
    "child_a",
    "child_b",
    "sibling",
    "machine_init",
    "parent_init",
    "parent_to_sibling",
  )
  prepared_document = json.loads(
    (output_dir / "prepared-document.json").read_text(encoding="utf-8")
  )
  _assert_dot_contains_exact_public_ids(
    prepared_document["dot_source"],
    session.highlightable_ids,
  )
  assert prepared_document["highlightable_ids"] == [
    "parent",
    "child_a",
    "child_b",
    "sibling",
    "machine_init",
    "parent_init",
    "parent_to_sibling",
  ]
  assert 'subgraph "cluster_parent" {' in prepared_document["dot_source"]
  assert 'id="parent";' in prepared_document["dot_source"]
  assert 'label=<' in prepared_document[
    "dot_source"
  ]
  assert "<B>Parent</B>" in prepared_document["dot_source"]
  assert "on_entry:" in prepared_document["dot_source"]
  assert "enter_parent" in prepared_document["dot_source"]
  assert '"parent" [id="parent", shape=box' not in prepared_document[
    "dot_source"
  ]
  assert (
    '"__routing_helper_compound_anchor__parent" '
    '[shape=point, label="", width=0.1, height=0.1, fixedsize=true, '
    'style=invis];'
  ) in prepared_document["dot_source"]
  svg_text = (output_dir / "diagram.svg").read_text(encoding="utf-8")
  _assert_svg_contains_exact_public_ids(
    svg_text,
    session.highlightable_ids,
    private_ids=("__routing_helper_compound_anchor__parent",),
  )


def test_build_viewer_session_renders_on_initial_text_without_new_public_ids(
  tmp_path,
):
  hsm_path = tmp_path / "activity-parity.json"
  output_dir = tmp_path / "session-artifacts"
  _write_activity_parity_hsm_input(hsm_path)

  session = build_viewer_session(
    hsm_path,
    output_dir,
    graphviz_command=_fake_graphviz_text_contract_command(),
  )

  assert session.highlightable_ids == (
    "parent",
    "child",
    "sibling",
    "parent_to_sibling_guard",
    "machine_init",
    "parent_init",
    "parent_to_sibling",
    "parent_to_sibling_guard_true",
    "parent_to_sibling_guard_false",
  )
  prepared_document = json.loads(
    (output_dir / "prepared-document.json").read_text(encoding="utf-8")
  )
  assert prepared_document["highlightable_ids"] == [
    "parent",
    "child",
    "sibling",
    "parent_to_sibling_guard",
    "machine_init",
    "parent_init",
    "parent_to_sibling",
    "parent_to_sibling_guard_true",
    "parent_to_sibling_guard_false",
  ]
  assert "on_initial:" in prepared_document["dot_source"]
  assert "initial_transition:" not in prepared_document["dot_source"]
  assert "on_entry:" in prepared_document["dot_source"]
  assert "on_exit:" in prepared_document["dot_source"]
  assert "internal_transitions:" in prepared_document["dot_source"]
  assert 'TOOLTIP="internal_transition_event|parent_internal"' in prepared_document[
    "dot_source"
  ]
  assert 'TOOLTIP="internal_transition_activity|parent_internal|trace_internal_activity"' in prepared_document[
    "dot_source"
  ]
  assert 'TOOLTIP="external_transition_label|parent_to_sibling"' in prepared_document[
    "dot_source"
  ]
  assert 'TOOLTIP="external_transition_activity|parent_to_sibling_guard_true|trace_transition_activity"' in prepared_document[
    "dot_source"
  ]
  assert "trace_child_initial_activity" not in prepared_document["dot_source"]
  assert "trace_parent_initial" in prepared_document["dot_source"]
  svg_text = (output_dir / "diagram.svg").read_text(encoding="utf-8")
  _assert_svg_contains_exact_public_ids(svg_text, session.highlightable_ids)
  assert "on_initial:" in svg_text
  assert "initial_transition:" not in svg_text
  assert "internal_transitions:" in svg_text
  assert "open_evt(source)" in svg_text
  assert "trace_transition_activity" in svg_text
  assert "/trace_root_initial_activity" not in svg_text
  assert "/trace_child_initial_activity, record_activity" not in svg_text
  assert "trace_child_initial_activity" not in svg_text
  assert "trace_internal_activity" in svg_text
  assert 'id="trace_parent_initial"' not in svg_text
  assert 'id="tick_parent"' not in svg_text
  assert 'id="guard_true"' not in svg_text


def test_build_viewer_session_preserves_public_ids_with_empty_partitions(
  tmp_path,
):
  hsm_path = tmp_path / "compound-empty-actions.json"
  output_dir = tmp_path / "session-artifacts"
  _write_compound_empty_actions_hsm_input(hsm_path)

  session = build_viewer_session(
    hsm_path,
    output_dir,
    graphviz_command=_fake_graphviz_command(),
  )

  assert session.highlightable_ids == (
    "parent",
    "child",
    "leaf",
    "machine_init",
    "parent_init",
    "parent_to_leaf",
  )
  prepared_document = json.loads(
    (output_dir / "prepared-document.json").read_text(encoding="utf-8")
  )
  assert prepared_document["highlightable_ids"] == [
    "parent",
    "child",
    "leaf",
    "machine_init",
    "parent_init",
    "parent_to_leaf",
  ]
  assert prepared_document["dot_source"].count(
    '<TR><TD ALIGN="LEFT">&#160;</TD></TR>'
  ) == 3
  svg_text = (output_dir / "diagram.svg").read_text(encoding="utf-8")
  _assert_svg_contains_exact_public_ids(
    svg_text,
    session.highlightable_ids,
    private_ids=("__routing_helper_compound_anchor__parent",),
  )


def test_build_viewer_session_routes_local_initials_to_private_compound_anchors(
  tmp_path,
):
  hsm_path = tmp_path / "compound-local-init.json"
  output_dir = tmp_path / "session-artifacts"
  _write_compound_local_initial_to_compound_hsm_input(hsm_path)

  session = build_viewer_session(
    hsm_path,
    output_dir,
    graphviz_command=_fake_graphviz_command(),
  )

  assert session.highlightable_ids == (
    "parent",
    "child_group",
    "leaf",
    "child_b",
    "machine_init",
    "parent_init",
    "child_group_init",
  )
  prepared_document = json.loads(
    (output_dir / "prepared-document.json").read_text(encoding="utf-8")
  )
  assert prepared_document["highlightable_ids"] == [
    "parent",
    "child_group",
    "leaf",
    "child_b",
    "machine_init",
    "parent_init",
    "child_group_init",
  ]
  assert (
    '"__routing_helper_local_initial_source__parent" -> '
    '"__routing_helper_compound_anchor__child_group" '
    '[id="parent_init", label="", lhead="cluster_child_group"];'
  ) in prepared_document["dot_source"]
  assert (
    '"__routing_helper_local_initial_source__parent" -> "child_group" '
    '[id="parent_init", label=""];'
    not in prepared_document["dot_source"]
  )
  svg_text = (output_dir / "diagram.svg").read_text(encoding="utf-8")
  _assert_svg_contains_exact_public_ids(
    svg_text,
    session.highlightable_ids,
    private_ids=(
      "__routing_helper_compound_anchor__parent",
      "__routing_helper_compound_anchor__child_group",
      "__routing_helper_local_initial_source__parent",
      "__routing_helper_local_initial_source__child_group",
      "__routing_helper_root_initial_source__machine_init",
    ),
  )


def test_build_viewer_session_keeps_private_anchors_out_of_public_svg_ids(
  tmp_path,
):
  hsm_path = tmp_path / "compound-local-init.json"
  output_dir = tmp_path / "session-artifacts"
  _write_compound_local_initial_to_compound_hsm_input(hsm_path)

  session = build_viewer_session(
    hsm_path,
    output_dir,
    graphviz_command=_fake_helper_visibility_contract_command(),
  )

  svg_text = (output_dir / "diagram.svg").read_text(encoding="utf-8")
  _assert_svg_contains_exact_public_ids(svg_text, session.highlightable_ids)
  assert 'id="__routing_helper_root_initial_source__machine_init"' not in svg_text
  assert 'id="__routing_helper_local_initial_source__parent"' not in svg_text
  assert 'id="__routing_helper_local_initial_source__child_group"' not in svg_text
  assert 'id="__routing_helper_compound_anchor__child_group"' not in svg_text
  assert '<title>__routing_helper_root_initial_source__machine_init</title>' in svg_text
  assert '<title>__routing_helper_local_initial_source__parent</title>' in svg_text
  assert '<ellipse fill="black" stroke="black"' in svg_text


def test_build_viewer_session_real_graphviz_keeps_visible_source_dots_and_hides_private_anchors(
  tmp_path,
):
  if shutil.which("dot") is None:
    import pytest

    pytest.skip("Graphviz 'dot' is unavailable")

  hsm_path = tmp_path / "compound-local-init.json"
  output_dir = tmp_path / "session-artifacts"
  _write_compound_local_initial_to_compound_hsm_input(hsm_path)

  session = build_viewer_session(hsm_path, output_dir)

  svg_text = (output_dir / "diagram.svg").read_text(encoding="utf-8")
  _assert_svg_contains_exact_public_ids(svg_text, session.highlightable_ids)
  assert re.search(
    r'<g id="node\d+" class="node">\s*<title>__routing_helper_compound_anchor__',
    svg_text,
  ) is None
  assert re.search(
    r'<g id="node\d+" class="node">\s*<title>__routing_helper_(root|local)_initial_source__',
    svg_text,
  ) is not None
  assert '<ellipse fill="black" stroke="black"' in svg_text


def test_build_viewer_session_emits_private_text_target_metadata_without_new_public_ids(
  tmp_path,
):
  hsm_path = tmp_path / "activity-parity.json"
  output_dir = tmp_path / "session-artifacts"
  _write_activity_parity_hsm_input(hsm_path)

  session = build_viewer_session(
    hsm_path,
    output_dir,
    graphviz_command=_fake_graphviz_text_contract_command(),
  )

  prepared_document = json.loads(
    (output_dir / "prepared-document.json").read_text(encoding="utf-8")
  )

  assert prepared_document["highlightable_ids"] == list(session.highlightable_ids)
  assert set(prepared_document["viewer_text_targets"]["external_transition_label_ids"]) == {
    "parent_to_sibling",
    "parent_to_sibling_guard_true",
    "parent_to_sibling_guard_false",
  }
  assert set(prepared_document["viewer_text_targets"]["lifecycle_section_ids"]) == {
    "parent"
  }
  assert set(
    prepared_document["viewer_text_targets"]["lifecycle_section_ids"]["parent"]
  ) == {"on_initial", "on_entry", "on_exit"}
  svg_text = (output_dir / "diagram.svg").read_text(encoding="utf-8")
  _assert_svg_contains_exact_public_ids(svg_text, session.highlightable_ids)
  assert '__mbse_text_fragment__' in svg_text
