from __future__ import annotations

import json
from pathlib import Path
import re
import sys
from urllib.error import HTTPError
from urllib.request import Request
from urllib.request import urlopen

import pytest

from mbse.runtime.hsm import build_hsm_runtime
from mbse_web_viewer.app.runtime_bridge import ViewerRuntimeBridge
from mbse_web_viewer.app.server import start_viewer_server
from mbse_web_viewer.app.viewer_state_types import RuntimeViewerTextTargets
from mbse_web_viewer.app.viewer_state_types import ViewerAppState
from mbse_web_viewer.main import build_and_start_viewer
from mbse_web_viewer.svg_render.graphviz.exceptions import GraphvizValidationError
from tests.support.viewer_browser_harness import ViewerBrowserHarness
from tests.support.hsm_payloads import hsm_document
from tests.support.hsm_payloads import hsm_external_transition
from tests.support.hsm_payloads import hsm_guard
from tests.support.hsm_payloads import hsm_guard_branch
from tests.support.hsm_payloads import hsm_initial
from tests.support.hsm_payloads import hsm_internal_transition
from tests.support.hsm_payloads import hsm_state


def _runtime_payload() -> dict[str, object]:
  return hsm_document(
    "door_machine",
    variables=[{"id": "speed", "default": 0}],
    events=[
      {"id": "open_evt"},
      {"id": "close_evt"},
      {"id": "pulse_evt"},
      {"id": "missing_evt"},
    ],
    initial_transition=hsm_initial("machine_init", "idle"),
    states=[
      hsm_state(
        "idle",
        states=[
          hsm_state(
            "idle_waiting",
            external_transitions=[
              hsm_external_transition(
                "waiting_to_open",
                target_id="open",
                event_id="open_evt",
              )
            ],
          )
        ],
        initial_transition=hsm_initial("idle_init", "idle_waiting"),
        internal_transitions=[
          hsm_internal_transition("idle_pulse", event_id="pulse_evt")
        ],
      ),
      hsm_state(
        "open",
        external_transitions=[
          hsm_external_transition(
            "open_to_idle",
            target_id="idle",
            event_id="close_evt",
          )
        ],
      ),
    ],
  )


def _build_runtime_bridge() -> ViewerRuntimeBridge:
  return ViewerRuntimeBridge(
    runtime_factory=lambda: build_hsm_runtime(_runtime_payload()),
    app_state=ViewerAppState(
      document_id="door_machine",
      svg_url="/artifacts/diagram.svg",
      highlightable_ids=(
        "idle",
        "idle_waiting",
        "open",
        "idle_init",
        "waiting_to_open",
        "open_to_idle",
      ),
      text_targets=RuntimeViewerTextTargets(),
    ),
  )


def _guard_runtime_payload() -> dict[str, object]:
  return hsm_document(
    "guard_machine",
    variables=[
      {"id": "trace", "default": []},
      {"id": "job_queue", "default": 0},
    ],
    events=[{"id": "advance_evt"}],
    initial_transition=hsm_initial("machine_init", "idle"),
    states=[
      hsm_state(
        "idle",
        external_transitions=[
          hsm_external_transition(
            "idle_to_job_check",
            event_id="advance_evt",
            guard=hsm_guard(
              guard_id="job_check",
              guard={
                "module": "tests.support.hsm_callable_fixtures",
                "name": "guard_job_available",
              },
              true_branch=hsm_guard_branch("processing"),
              false_branch=hsm_guard_branch("blocked"),
            ),
          )
        ],
      ),
      hsm_state("processing"),
      hsm_state("blocked"),
    ],
  )


def _build_guard_runtime_bridge(
  *,
  highlightable_ids: tuple[str, ...],
) -> ViewerRuntimeBridge:
  return ViewerRuntimeBridge(
    runtime_factory=lambda: build_hsm_runtime(_guard_runtime_payload()),
    app_state=ViewerAppState(
      document_id="guard_machine",
      svg_url="/artifacts/diagram.svg",
      highlightable_ids=highlightable_ids,
      text_targets=RuntimeViewerTextTargets(),
    ),
  )


def _viewer_session_payload(*, variables: dict[str, object]) -> dict[str, object]:
  return {
    "document_id": "door_machine",
    "svg_url": "/artifacts/diagram.svg",
    "event_ids": ["open_evt", "close_evt", "pulse_evt", "missing_evt"],
    "variable_ids": ["speed", "mode"],
    "text_targets": {
      "lifecycle_section_ids": {},
      "lifecycle_activity_ids": {},
      "external_transition_label_ids": {},
      "external_transition_activity_ids": {},
      "internal_transition_section_ids": {},
      "internal_transition_event_ids": {},
      "internal_transition_activity_ids": {},
    },
    "snapshot": {
      "state_id": "idle_waiting",
      "active_path": ["idle", "idle_waiting"],
      "active_ids": ["idle_waiting"],
      "last_event": {
        "event_id": None,
        "handled": False,
        "handler_kind": None,
        "handler_id": None,
        "guard_node_id": None,
        "guard_branch_id": None,
        "transition_path_ids": [],
        "executed_activities": [],
      },
      "variables": variables,
    },
  }


def _expected_variable_row(
  variable_id: str,
  *,
  textbox_value: str,
  inline_unset_text: str = "",
) -> dict[str, object]:
  return {
    "variable_id": variable_id,
    "textbox_value": textbox_value,
    "inline_unset_text": inline_unset_text,
    "has_value_display": False,
    "unset": inline_unset_text != "",
  }


def _empty_text_targets() -> dict[str, object]:
  return {
    "lifecycle_section_ids": {},
    "lifecycle_activity_ids": {},
    "external_transition_label_ids": {},
    "external_transition_activity_ids": {},
    "internal_transition_section_ids": {},
    "internal_transition_event_ids": {},
    "internal_transition_activity_ids": {},
  }


def _expected_init_last_event(*, visible_transition_ids: list[str]) -> dict[str, object]:
  return {
    "event_id": None,
    "handled": True,
    "handler_kind": "init",
    "handler_id": None,
    "guard_node_id": None,
    "guard_branch_id": None,
    "transition_path_ids": visible_transition_ids,
    "executed_activities": [],
  }


def _highlight_fixture_session(
  *,
  active_id: str,
  transition_path_ids: list[str],
) -> dict[str, object]:
  session = _viewer_session_payload(variables={})
  session["snapshot"]["state_id"] = active_id
  session["snapshot"]["active_path"] = [active_id]
  session["snapshot"]["active_ids"] = [active_id]
  session["snapshot"]["last_event"] = {
    "event_id": "fixture_evt" if transition_path_ids else None,
    "handled": bool(transition_path_ids),
    "handler_kind": "external_transition" if transition_path_ids else None,
    "handler_id": transition_path_ids[0] if transition_path_ids else None,
    "guard_node_id": None,
    "guard_branch_id": None,
    "transition_path_ids": transition_path_ids,
    "executed_activities": [],
  }
  return session


def _highlight_fixture_svg() -> str:
  return (
    '<svg xmlns="http://www.w3.org/2000/svg">'
    '<g id="leaf_state">'
    '<title>Leaf</title>'
    '<polygon points="0,0 10,0 10,10 0,10"></polygon>'
    '<text>Leaf label</text>'
    '</g>'
    '<g id="compound_state">'
    '<title>Compound</title>'
    '<polygon points="0,0 40,0 40,40 0,40"></polygon>'
    '<text>Compound label</text>'
    '<g id="compound_child">'
    '<polygon points="5,5 20,5 20,20 5,20"></polygon>'
    '<text>Nested child label</text>'
    '</g>'
    '</g>'
     '<g id="idle_init">'
     '<title>idle_init</title>'
     '<path d="M0 0 L10 10"></path>'
     '<polygon points="10,10 12,8 12,12"></polygon>'
     '<text>open_evt</text>'
     '</g>'
     '<g id="second_edge">'
     '<title>second_edge</title>'
     '<path d="M10 10 L20 20"></path>'
     '<polygon points="20,20 22,18 22,22"></polygon>'
     '<text>nested_evt</text>'
     '</g>'
     '</svg>'
  )


def _text_highlight_fixture_svg() -> str:
  return (
    '<svg xmlns="http://www.w3.org/2000/svg">'
    '<g id="closed"><polygon points="0,0 10,0 10,10 0,10"></polygon></g>'
    '<g id="closed_to_open"><path d="M0 0 L10 10"></path><polygon points="10,10 12,8 12,12"></polygon></g>'
    '<text id="__mbse_text_fragment__0001">on_entry:</text>'
    '<text id="__mbse_text_fragment__0002">count_increment</text>'
    '<text id="__mbse_text_fragment__0003">open_evt</text>'
    '<text id="__mbse_text_fragment__0004">trace_transition_activity</text>'
    '<text id="__mbse_text_fragment__0005">internal_transitions:</text>'
    '<text id="__mbse_text_fragment__0006">pulse_evt</text>'
    '<text id="__mbse_text_fragment__0007">trace_internal_activity</text>'
    '<text id="neutral_text">neutral label</text>'
    '</svg>'
  )


def _fake_graphviz_command() -> tuple[str, ...]:
  script = (
    "import re, sys; "
    "dot = sys.stdin.read(); "
    "ids = re.findall(r'id=\\\"([^\\\"]+)\\\"', dot); "
    "body = ''.join(f'<g id=\\\"{item}\\\"></g>' for item in ids); "
    "sys.stdout.write(f'<svg xmlns=\\\"http://www.w3.org/2000/svg\\\">{body}</svg>')"
  )
  return (sys.executable, "-c", script)


def _post_json(base_url: str, path: str, payload: dict[str, object]) -> dict[str, object]:
  return json.loads(
    urlopen(
      Request(
        f"{base_url}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
      )
    ).read().decode("utf-8")
  )


def _write_runtime_svg(session_dir: Path) -> None:
  (session_dir / "diagram.svg").write_text(
    (
      '<svg xmlns="http://www.w3.org/2000/svg">'
      '<g id="idle"></g>'
      '<g id="idle_waiting"></g>'
      '<g id="idle_init"></g>'
      '<g id="waiting_to_open"></g>'
      '<g id="open_to_idle"></g>'
      '<g id="open"></g>'
      "</svg>"
    ),
    encoding="utf-8",
  )


def _write_guard_runtime_svg(session_dir: Path) -> None:
  (session_dir / "diagram.svg").write_text(
    (
      '<svg xmlns="http://www.w3.org/2000/svg">'
      '<g id="idle"></g>'
      '<g id="processing"></g>'
      '<g id="blocked"></g>'
      '<g id="machine_init"></g>'
      '<g id="idle_to_job_check"></g>'
      '<g id="job_check"></g>'
      '<g id="job_check_true"></g>'
      '<g id="job_check_false"></g>'
      "</svg>"
    ),
    encoding="utf-8",
  )


def test_start_viewer_server_serves_runtime_session_endpoints_and_svg(tmp_path):
  session_dir = tmp_path / "session-artifacts"
  session_dir.mkdir()
  (session_dir / "diagram.svg").write_text(
    (
      '<svg xmlns="http://www.w3.org/2000/svg">'
      '<g id="idle"></g>'
      '<g id="idle_waiting"></g>'
      '<g id="idle_init"></g>'
      '<g id="waiting_to_open"></g>'
      '<g id="open_to_idle"></g>'
      '<g id="open"></g>'
      "</svg>"
    ),
    encoding="utf-8",
  )

  server = start_viewer_server(
    session_dir,
    runtime_bridge=_build_runtime_bridge(),
    host="127.0.0.1",
    port=0,
  )

  try:
    index_html = urlopen(f"{server.base_url}/").read().decode("utf-8")
    assert "Reset runtime" in index_html
    assert "Reset view" in index_html
    assert "Send event" in index_html
    assert "SVG workbench" not in index_html
    assert "Inspect one rendered diagram with backend-owned runtime controls." not in index_html
    assert "Current state" not in index_html
    assert index_html.index("Reset") < index_html.index("Events")
    assert index_html.index("Events") < index_html.index("Variables")
    assert "Variables" in index_html
    assert "Events" in index_html
    assert "Status" not in index_html
    assert "Current snapshot" not in index_html
    assert "Runtime actions" not in index_html
    assert "Zoom in" not in index_html
    assert "Zoom out" not in index_html
    assert 'id="layout-splitter"' in index_html
    assert 'class="workbench-page"' in index_html
    assert 'id="reset-runtime-button"' in index_html
    assert 'id="reset-view-button"' in index_html
    assert 'id="variable-list"' in index_html
    assert 'id="runtime-status"' not in index_html
    assert 'class="sidebar-header"' not in index_html
    assert 'class="reset-row"' in index_html
    assert re.search(
      r'class="reset-row"[\s\S]*id="reset-form"[\s\S]*id="reset-view-button"',
      index_html,
    )

    session_payload = json.loads(
      urlopen(f"{server.base_url}/api/session.json").read().decode("utf-8")
    )
    assert session_payload == {
      "document_id": "door_machine",
      "svg_url": "/artifacts/diagram.svg",
      "event_ids": ["open_evt", "close_evt", "pulse_evt", "missing_evt"],
      "variable_ids": ["speed"],
      "text_targets": _empty_text_targets(),
      "snapshot": {
        "state_id": "idle_waiting",
        "active_path": ["idle", "idle_waiting"],
        "active_ids": ["idle_waiting"],
        "last_event": _expected_init_last_event(
          visible_transition_ids=["idle_init"]
        ),
        "variables": {"speed": 0},
      },
    }

    variable_payload = json.loads(
      urlopen(
        Request(
          f"{server.base_url}/api/runtime/variables",
          data=json.dumps({"variable_id": "speed", "value": 3}).encode("utf-8"),
          headers={"Content-Type": "application/json"},
          method="POST",
        )
      ).read().decode("utf-8")
    )
    assert variable_payload["snapshot"]["variables"] == {"speed": 3}
    assert variable_payload["snapshot"]["last_event"] == _expected_init_last_event(
      visible_transition_ids=["idle_init"]
    )

    event_payload = json.loads(
      urlopen(
        Request(
          f"{server.base_url}/api/runtime/events",
          data=json.dumps({"event_id": "open_evt"}).encode("utf-8"),
          headers={"Content-Type": "application/json"},
          method="POST",
        )
      ).read().decode("utf-8")
    )
    assert event_payload["snapshot"] == {
      "state_id": "open",
      "active_path": ["open"],
      "active_ids": ["open"],
      "last_event": {
        "event_id": "open_evt",
        "handled": True,
        "handler_kind": "external_transition",
        "handler_id": "waiting_to_open",
        "guard_node_id": None,
        "guard_branch_id": None,
        "transition_path_ids": ["waiting_to_open"],
        "executed_activities": [],
      },
      "variables": {"speed": 3},
    }

    internal_payload = json.loads(
      urlopen(
        Request(
          f"{server.base_url}/api/runtime/reset",
          data=b"{}",
          headers={"Content-Type": "application/json"},
          method="POST",
        )
      ).read().decode("utf-8")
    )
    internal_payload = json.loads(
      urlopen(
        Request(
          f"{server.base_url}/api/runtime/events",
          data=json.dumps({"event_id": "pulse_evt"}).encode("utf-8"),
          headers={"Content-Type": "application/json"},
          method="POST",
        )
      ).read().decode("utf-8")
    )
    assert internal_payload["snapshot"] == {
      "state_id": "idle_waiting",
      "active_path": ["idle", "idle_waiting"],
      "active_ids": ["idle_waiting"],
      "last_event": {
        "event_id": "pulse_evt",
        "handled": True,
        "handler_kind": "internal_transition",
        "handler_id": "idle_pulse",
        "guard_node_id": None,
        "guard_branch_id": None,
        "transition_path_ids": [],
        "executed_activities": [],
      },
      "variables": {"speed": 0},
    }

    unhandled_payload = json.loads(
      urlopen(
        Request(
          f"{server.base_url}/api/runtime/events",
          data=json.dumps({"event_id": "missing_evt"}).encode("utf-8"),
          headers={"Content-Type": "application/json"},
          method="POST",
        )
      ).read().decode("utf-8")
    )
    assert unhandled_payload["snapshot"] == {
      "state_id": "idle_waiting",
      "active_path": ["idle", "idle_waiting"],
      "active_ids": ["idle_waiting"],
      "last_event": {
        "event_id": "missing_evt",
        "handled": False,
        "handler_kind": None,
        "handler_id": None,
        "guard_node_id": None,
        "guard_branch_id": None,
        "transition_path_ids": [],
        "executed_activities": [],
      },
      "variables": {"speed": 0},
    }

    reset_payload = json.loads(
      urlopen(
        Request(
          f"{server.base_url}/api/runtime/reset",
          data=b"{}",
          headers={"Content-Type": "application/json"},
          method="POST",
        )
      ).read().decode("utf-8")
    )
    assert reset_payload["snapshot"] == {
      "state_id": "idle_waiting",
      "active_path": ["idle", "idle_waiting"],
      "active_ids": ["idle_waiting"],
      "last_event": _expected_init_last_event(
        visible_transition_ids=["idle_init"]
      ),
      "variables": {"speed": 0},
    }

    viewer_css = urlopen(f"{server.base_url}/viewer.css").read().decode("utf-8")
    assert "--surface-page: #f6f8fa;" in viewer_css
    assert "--surface-panel: #ffffff;" in viewer_css
    assert "--surface-panel-muted: #eef2f6;" in viewer_css
    assert "--surface-control: #ffffff;" in viewer_css
    assert "background: #ffffff;" in viewer_css

    svg_text = urlopen(f"{server.base_url}/artifacts/diagram.svg").read().decode(
      "utf-8"
    )
    assert 'id="idle"' in svg_text
    assert 'id="open"' in svg_text
    assert 'id="idle_init"' in svg_text
  finally:
    server.close()


def test_http_contract_get_session_json_shape_for_hsm_runtime(tmp_path):
  session_dir = tmp_path / "session-artifacts"
  session_dir.mkdir()
  _write_runtime_svg(session_dir)
   
  server = start_viewer_server(
    session_dir,
    runtime_bridge=_build_runtime_bridge(),
    host="127.0.0.1",
    port=0,
  )

  try:
    payload = json.loads(
      urlopen(f"{server.base_url}/api/session.json").read().decode("utf-8")
    )

    assert payload == {
      "document_id": "door_machine",
      "svg_url": "/artifacts/diagram.svg",
      "event_ids": ["open_evt", "close_evt", "pulse_evt", "missing_evt"],
      "variable_ids": ["speed"],
      "text_targets": _empty_text_targets(),
      "snapshot": {
        "state_id": "idle_waiting",
        "active_path": ["idle", "idle_waiting"],
        "active_ids": ["idle_waiting"],
        "last_event": _expected_init_last_event(
          visible_transition_ids=["idle_init"]
        ),
        "variables": {"speed": 0},
      },
    }
  finally:
    server.close()


def test_http_contract_post_runtime_variables_shape_for_hsm_runtime(tmp_path):
  session_dir = tmp_path / "session-artifacts"
  session_dir.mkdir()
  _write_runtime_svg(session_dir)

  server = start_viewer_server(
    session_dir,
    runtime_bridge=_build_runtime_bridge(),
    host="127.0.0.1",
    port=0,
  )

  try:
    payload = _post_json(
      server.base_url,
      "/api/runtime/variables",
      {"variable_id": "speed", "value": 3},
    )

    assert payload == {
      "document_id": "door_machine",
      "svg_url": "/artifacts/diagram.svg",
      "event_ids": ["open_evt", "close_evt", "pulse_evt", "missing_evt"],
      "variable_ids": ["speed"],
      "text_targets": _empty_text_targets(),
      "snapshot": {
        "state_id": "idle_waiting",
        "active_path": ["idle", "idle_waiting"],
        "active_ids": ["idle_waiting"],
        "last_event": _expected_init_last_event(
          visible_transition_ids=["idle_init"]
        ),
        "variables": {"speed": 3},
      },
    }
  finally:
    server.close()


def test_http_contract_post_runtime_events_shape_for_hsm_runtime(tmp_path):
  session_dir = tmp_path / "session-artifacts"
  session_dir.mkdir()
  _write_runtime_svg(session_dir)

  server = start_viewer_server(
    session_dir,
    runtime_bridge=_build_runtime_bridge(),
    host="127.0.0.1",
    port=0,
  )

  try:
    payload = _post_json(
      server.base_url,
      "/api/runtime/events",
      {"event_id": "open_evt"},
    )

    assert payload == {
      "document_id": "door_machine",
      "svg_url": "/artifacts/diagram.svg",
      "event_ids": ["open_evt", "close_evt", "pulse_evt", "missing_evt"],
      "variable_ids": ["speed"],
      "text_targets": _empty_text_targets(),
      "snapshot": {
        "state_id": "open",
        "active_path": ["open"],
        "active_ids": ["open"],
        "last_event": {
          "event_id": "open_evt",
          "handled": True,
        "handler_kind": "external_transition",
          "handler_id": "waiting_to_open",
          "guard_node_id": None,
          "guard_branch_id": None,
          "transition_path_ids": ["waiting_to_open"],
          "executed_activities": [],
        },
        "variables": {"speed": 0},
      },
    }
  finally:
    server.close()


def test_http_contract_post_runtime_reset_shape_for_hsm_runtime(tmp_path):
  session_dir = tmp_path / "session-artifacts"
  session_dir.mkdir()
  _write_runtime_svg(session_dir)

  server = start_viewer_server(
    session_dir,
    runtime_bridge=_build_runtime_bridge(),
    host="127.0.0.1",
    port=0,
  )

  try:
    _post_json(
      server.base_url,
      "/api/runtime/variables",
      {"variable_id": "speed", "value": 3},
    )
    _post_json(
      server.base_url,
      "/api/runtime/events",
      {"event_id": "open_evt"},
    )

    payload = _post_json(server.base_url, "/api/runtime/reset", {})

    assert payload == {
      "document_id": "door_machine",
      "svg_url": "/artifacts/diagram.svg",
      "event_ids": ["open_evt", "close_evt", "pulse_evt", "missing_evt"],
      "variable_ids": ["speed"],
      "text_targets": _empty_text_targets(),
      "snapshot": {
        "state_id": "idle_waiting",
        "active_path": ["idle", "idle_waiting"],
        "active_ids": ["idle_waiting"],
        "last_event": _expected_init_last_event(
          visible_transition_ids=["idle_init"]
        ),
        "variables": {"speed": 0},
      },
    }
  finally:
    server.close()


def test_http_contract_prepared_document_without_runtime_keeps_empty_session_shape(
  tmp_path,
):
  prepared_path = tmp_path / "prepared-document.json"
  output_dir = tmp_path / "session-artifacts"
  prepared_path.write_text(
    json.dumps(
      {
        "document_id": "demo-machine",
        "dot_source": 'digraph G { idle [id="state_idle", label="Idle"]; }',
        "highlightable_ids": ["state_idle"],
      }
    ),
    encoding="utf-8",
  )
  fake_svg = (
    '<svg xmlns="http://www.w3.org/2000/svg">'
    '<g id="state_idle"><title>Idle</title></g>'
    "</svg>"
  )

  server = build_and_start_viewer(
    prepared_path,
    output_dir,
    host="127.0.0.1",
    port=0,
    open_browser=False,
    graphviz_command=(
      sys.executable,
      "-c",
      f"import sys; sys.stdout.write({fake_svg!r})",
    ),
  )

  try:
    expected = {
      "document_id": "demo-machine",
      "svg_url": "/artifacts/diagram.svg",
      "event_ids": [],
      "variable_ids": [],
      "text_targets": _empty_text_targets(),
      "snapshot": {
        "state_id": "",
        "active_path": [],
        "active_ids": [],
        "last_event": {
          "event_id": None,
          "handled": False,
          "handler_kind": None,
          "handler_id": None,
          "guard_node_id": None,
          "guard_branch_id": None,
          "transition_path_ids": [],
          "executed_activities": [],
        },
        "variables": {},
      },
    }

    assert json.loads(
      urlopen(f"{server.base_url}/api/session.json").read().decode("utf-8")
    ) == expected
    assert _post_json(server.base_url, "/api/runtime/reset", {}) == expected
  finally:
    server.close()


def test_http_contract_filters_guard_and_transition_ids_to_visible_svg_ids(
  tmp_path,
):
  session_dir = tmp_path / "session-artifacts"
  session_dir.mkdir()
  _write_guard_runtime_svg(session_dir)

  server = start_viewer_server(
    session_dir,
    runtime_bridge=_build_guard_runtime_bridge(
      highlightable_ids=("processing", "idle_to_job_check"),
    ),
    host="127.0.0.1",
    port=0,
  )

  try:
    payload = _post_json(
      server.base_url,
      "/api/runtime/variables",
      {"variable_id": "job_queue", "value": 1},
    )
    assert payload["snapshot"]["last_event"] == {
      "event_id": None,
      "handled": True,
      "handler_kind": "init",
      "handler_id": None,
      "guard_node_id": None,
      "guard_branch_id": None,
      "transition_path_ids": [],
      "executed_activities": [],
    }

    payload = _post_json(
      server.base_url,
      "/api/runtime/events",
      {"event_id": "advance_evt"},
    )

    assert payload["snapshot"] == {
      "state_id": "processing",
      "active_path": ["processing"],
      "active_ids": ["processing"],
      "last_event": {
        "event_id": "advance_evt",
        "handled": True,
        "handler_kind": "guard_transition",
        "handler_id": "idle_to_job_check",
        "guard_node_id": None,
        "guard_branch_id": None,
        "transition_path_ids": ["idle_to_job_check"],
        "executed_activities": [],
      },
      "variables": {"trace": ["guard.job_available"], "job_queue": 1},
    }
  finally:
    server.close()


def test_build_and_start_viewer_serves_runtime_ready_static_viewer(tmp_path):
  prepared_path = tmp_path / "door-machine.json"
  output_dir = tmp_path / "session-artifacts"
  prepared_path.write_text(
    json.dumps(_runtime_payload()),
    encoding="utf-8",
  )
  server = build_and_start_viewer(
    prepared_path,
    output_dir,
    host="127.0.0.1",
    port=0,
    open_browser=False,
    graphviz_command=_fake_graphviz_command(),
  )

  try:
    index_html = urlopen(f"{server.base_url}/").read().decode("utf-8")
    assert "Reset runtime" in index_html
    assert "Reset view" in index_html
    assert "Send event" in index_html
    assert "SVG workbench" not in index_html
    assert "Inspect one rendered diagram with backend-owned runtime controls." not in index_html
    assert "Current snapshot" not in index_html
    assert "Current state" not in index_html
    assert index_html.index("Reset") < index_html.index("Events")
    assert index_html.index("Events") < index_html.index("Variables")
    assert "Variables" in index_html
    assert "Events" in index_html
    assert "Status" not in index_html
    assert "Runtime actions" not in index_html
    assert "Zoom in" not in index_html
    assert "Zoom out" not in index_html
    assert 'id="layout-splitter"' in index_html
    assert 'id="reset-runtime-button"' in index_html
    assert 'id="reset-view-button"' in index_html
    assert 'id="variable-list"' in index_html
    assert 'class="sidebar-header"' not in index_html
    assert 'class="reset-row"' in index_html
    assert "Edit diagram" not in index_html
    assert "Open workspace" not in index_html
    assert "Apply highlight" not in index_html

    session_payload = json.loads(
      urlopen(f"{server.base_url}/api/session.json").read().decode("utf-8")
    )
    assert session_payload["event_ids"] == [
      "open_evt",
      "close_evt",
      "pulse_evt",
      "missing_evt",
    ]
    assert session_payload["variable_ids"] == ["speed"]
    assert session_payload["snapshot"]["active_ids"] == ["idle_waiting"]
    assert session_payload["snapshot"]["last_event"] == _expected_init_last_event(
      visible_transition_ids=["machine_init", "idle_init"]
    )

    svg_text = urlopen(
      f"{server.base_url}{session_payload['svg_url']}"
    ).read().decode("utf-8")
    rendered = ViewerBrowserHarness(
      session_payload=session_payload,
      svg_text=svg_text,
    ).render()
    assert rendered["state_highlight_ids"] == ["idle_waiting"]
    assert rendered["transition_highlight_ids"] == [
      "idle_init",
      "machine_init",
    ]

    viewer_js = urlopen(f"{server.base_url}/viewer.js").read().decode("utf-8")
    runtime_endpoints = set(re.findall(r'"(/api/runtime/[^"]+)"', viewer_js))
    assert runtime_endpoints == {
      "/api/runtime/reset",
      "/api/runtime/events",
      "/api/runtime/variables",
    }
    assert "/api/highlight" not in viewer_js
    assert "applyZoom" in viewer_js
    assert "scrollLeft" in viewer_js
    assert "scrollTop" in viewer_js
    assert "zoom-in-button" not in viewer_js
    assert "zoom-out-button" not in viewer_js
    assert "reset-view-button" in viewer_js
    assert 'addEventListener("wheel"' in viewer_js
    assert "runtime-status" not in viewer_js

    viewer_css = urlopen(f"{server.base_url}/viewer.css").read().decode("utf-8")
    assert "--sidebar-width" in viewer_css
    assert "--surface-page: #f6f8fa;" in viewer_css
    assert "--surface-panel: #ffffff;" in viewer_css
    assert "--surface-panel-muted: #eef2f6;" in viewer_css
    assert "--surface-control: #ffffff;" in viewer_css
    assert "grid-template-columns: var(--sidebar-width) 0.5rem minmax(0, 1fr);" in viewer_css
    assert ".reset-row" in viewer_css
    assert ".variable-row-main" in viewer_css
    assert ".variable-row-input" in viewer_css
    assert ".variable-unset" in viewer_css
    assert ".value-display" not in viewer_css
    assert ".layout {" in viewer_css
    assert "overflow: hidden;" in viewer_css
    assert ".sidebar {" in viewer_css
    assert "overflow-y: auto;" in viewer_css
    assert "#svg-viewport {" in viewer_css
    assert "overflow: auto;" in viewer_css
    assert "background: #ffffff;" in viewer_css
    assert ".workbench-page.is-pan-active" in viewer_css
    assert "#svg-viewport.is-pan-active" in viewer_css
    assert "#runtime-status" not in viewer_css
    assert ".is-active-state > polygon" in viewer_css
    assert ".is-active-state > path" in viewer_css
    assert ".is-active-transition > path" in viewer_css
    assert ".is-active-transition > polygon" in viewer_css
    assert ".is-active-state {" not in viewer_css
    assert ".is-active-transition {" not in viewer_css
  finally:
    server.close()


def test_build_and_start_viewer_keeps_prepared_graphviz_input_bootable(tmp_path):
  prepared_path = tmp_path / "prepared-document.json"
  output_dir = tmp_path / "session-artifacts"
  prepared_path.write_text(
    json.dumps(
      {
        "document_id": "demo-machine",
        "dot_source": 'digraph G { idle [id="state_idle", label="Idle"]; }',
        "highlightable_ids": ["state_idle"],
      }
    ),
    encoding="utf-8",
  )
  fake_svg = (
    '<svg xmlns="http://www.w3.org/2000/svg">'
    '<g id="state_idle"><title>Idle</title></g>'
    "</svg>"
  )

  server = build_and_start_viewer(
    prepared_path,
    output_dir,
    host="127.0.0.1",
    port=0,
    open_browser=False,
    graphviz_command=(
      sys.executable,
      "-c",
      f"import sys; sys.stdout.write({fake_svg!r})",
    ),
  )

  try:
    index_html = urlopen(f"{server.base_url}/").read().decode("utf-8")
    assert "Reset runtime" in index_html
    assert "Send event" in index_html
    assert "Current state" not in index_html
    assert "Current snapshot" not in index_html

    session_payload = json.loads(
      urlopen(f"{server.base_url}/api/session.json").read().decode("utf-8")
    )
    assert session_payload == {
      "document_id": "demo-machine",
      "svg_url": "/artifacts/diagram.svg",
      "event_ids": [],
      "variable_ids": [],
      "text_targets": _empty_text_targets(),
      "snapshot": {
        "state_id": "",
        "active_path": [],
        "active_ids": [],
        "last_event": {
          "event_id": None,
          "handled": False,
          "handler_kind": None,
          "handler_id": None,
          "guard_node_id": None,
          "guard_branch_id": None,
          "transition_path_ids": [],
          "executed_activities": [],
        },
        "variables": {},
      },
    }
  finally:
    server.close()


def test_viewer_renders_declared_variables_with_current_value_or_unset():
  harness = ViewerBrowserHarness(
    session_payload=_viewer_session_payload(variables={"speed": 3}),
    svg_text=(
      '<svg xmlns="http://www.w3.org/2000/svg">'
      '<g id="idle"></g><g id="idle_waiting"></g><g id="idle_init"></g></svg>'
    ),
  )

  rendered = harness.render()

  assert rendered["compact_variable_rows"] is True
  assert rendered["state_highlight_ids"] == ["idle_waiting"]
  assert rendered["transition_highlight_ids"] == []
  assert rendered["variable_rows"] == [
    _expected_variable_row("speed", textbox_value="3"),
    _expected_variable_row("mode", textbox_value="", inline_unset_text="Unset"),
  ]


def test_viewer_highlight_snapshot_exposes_leaf_state_shape_targets_only():
  harness = ViewerBrowserHarness(
    session_payload=_highlight_fixture_session(
      active_id="leaf_state",
      transition_path_ids=[],
    ),
    svg_text=_highlight_fixture_svg(),
  )

  rendered = harness.render()

  assert rendered["state_highlight_ids"] == ["leaf_state"]
  assert rendered["state_highlight_groups"] == [
    {
      "id": "leaf_state",
      "direct_child_tags": ["title", "polygon", "text"],
      "direct_shape_tags": ["polygon"],
      "text_descendant_tags": ["text"],
      "nested_group_ids": [],
    }
  ]


def test_viewer_highlight_snapshot_exposes_compound_state_nested_descendants_without_targeting_them():
  harness = ViewerBrowserHarness(
    session_payload=_highlight_fixture_session(
      active_id="compound_state",
      transition_path_ids=[],
    ),
    svg_text=_highlight_fixture_svg(),
  )

  rendered = harness.render()

  assert rendered["state_highlight_ids"] == ["compound_state"]
  assert rendered["state_highlight_groups"] == [
    {
      "id": "compound_state",
      "direct_child_tags": ["title", "polygon", "text", "g"],
      "direct_shape_tags": ["polygon"],
      "text_descendant_tags": ["text", "text"],
      "nested_group_ids": ["compound_child"],
    }
  ]


def test_viewer_highlight_snapshot_exposes_transition_edge_and_arrowhead_separately_from_label_text():
  harness = ViewerBrowserHarness(
    session_payload=_highlight_fixture_session(
      active_id="leaf_state",
      transition_path_ids=["idle_init", "second_edge"],
    ),
    svg_text=_highlight_fixture_svg(),
  )

  rendered = harness.render()

  assert rendered["transition_highlight_ids"] == ["idle_init", "second_edge"]
  assert rendered["transition_highlight_groups"] == [
    {
      "id": "idle_init",
      "direct_child_tags": ["title", "path", "polygon", "text"],
      "direct_shape_tags": ["path", "polygon"],
      "text_descendant_tags": ["text"],
      "nested_group_ids": [],
    },
    {
      "id": "second_edge",
      "direct_child_tags": ["title", "path", "polygon", "text"],
      "direct_shape_tags": ["path", "polygon"],
      "text_descendant_tags": ["text"],
      "nested_group_ids": [],
    },
  ]


def test_viewer_highlights_exact_transition_and_lifecycle_text_fragments_only():
  session = _viewer_session_payload(variables={})
  session["snapshot"]["state_id"] = "closed"
  session["snapshot"]["active_path"] = ["closed"]
  session["snapshot"]["active_ids"] = ["closed"]
  session["snapshot"]["last_event"] = {
    "event_id": "open_evt",
    "handled": True,
    "handler_kind": "external_transition",
    "handler_id": "closed_to_open",
    "transition_path_ids": ["closed_to_open"],
    "executed_activities": [
      {
        "activity_id": "count_increment",
        "owner_kind": "state_on_entry",
        "owner_id": "closed",
      },
      {
        "activity_id": "trace_transition_activity",
        "owner_kind": "external_transition",
        "owner_id": "closed_to_open",
      },
    ],
  }
  session["text_targets"] = {
    "lifecycle_section_ids": {"closed": {"on_entry": ["__mbse_text_fragment__0001"]}},
    "lifecycle_activity_ids": {
      "closed": {"on_entry": {"count_increment": ["__mbse_text_fragment__0002"]}}
    },
    "external_transition_label_ids": {"closed_to_open": ["__mbse_text_fragment__0003"]},
    "external_transition_activity_ids": {
      "closed_to_open": {"trace_transition_activity": ["__mbse_text_fragment__0004"]}
    },
    "internal_transition_section_ids": {},
    "internal_transition_event_ids": {},
    "internal_transition_activity_ids": {},
  }

  rendered = ViewerBrowserHarness(
    session_payload=session,
    svg_text=_text_highlight_fixture_svg(),
  ).render()

  assert rendered["state_highlight_ids"] == ["closed"]
  assert rendered["transition_highlight_ids"] == ["closed_to_open"]
  assert rendered["text_highlight_ids"] == [
    "__mbse_text_fragment__0001",
    "__mbse_text_fragment__0002",
    "__mbse_text_fragment__0003",
    "__mbse_text_fragment__0004",
  ]


def test_viewer_keeps_internal_transition_text_row_specific():
  session = _viewer_session_payload(variables={})
  session["snapshot"]["last_event"] = {
    "event_id": "pulse_evt",
    "handled": True,
    "handler_kind": "internal_transition",
    "handler_id": "idle_pulse",
    "transition_path_ids": [],
    "executed_activities": [
      {
        "activity_id": "trace_internal_activity",
        "owner_kind": "internal_transition",
        "owner_id": "idle_pulse",
      }
    ],
  }
  session["text_targets"] = {
    "lifecycle_section_ids": {},
    "lifecycle_activity_ids": {},
    "external_transition_label_ids": {},
    "external_transition_activity_ids": {},
    "internal_transition_section_ids": {"idle_pulse": ["__mbse_text_fragment__0005"]},
    "internal_transition_event_ids": {"idle_pulse": ["__mbse_text_fragment__0006"]},
    "internal_transition_activity_ids": {
      "idle_pulse": {"trace_internal_activity": ["__mbse_text_fragment__0007"]}
    },
  }

  rendered = ViewerBrowserHarness(
    session_payload=session,
    svg_text=_text_highlight_fixture_svg(),
  ).render()

  assert rendered["transition_highlight_ids"] == []
  assert rendered["text_highlight_ids"] == [
    "__mbse_text_fragment__0005",
    "__mbse_text_fragment__0006",
    "__mbse_text_fragment__0007",
  ]
  assert "neutral_text" not in rendered["text_highlight_ids"]


def test_viewer_highlights_guard_node_and_taken_branch_for_guard_transition():
  session = _viewer_session_payload(variables={})
  session["snapshot"]["state_id"] = "processing"
  session["snapshot"]["active_path"] = ["processing"]
  session["snapshot"]["active_ids"] = ["processing"]
  session["snapshot"]["last_event"] = {
    "event_id": "advance_evt",
    "handled": True,
    "handler_kind": "guard_transition",
    "handler_id": "idle_to_job_check",
    "guard_node_id": "job_check",
    "guard_branch_id": "job_check_true",
    "transition_path_ids": ["idle_to_job_check", "job_check_true"],
    "executed_activities": [
      {
        "activity_id": "trace_guard_true_branch",
        "owner_kind": "guard_branch",
        "owner_id": "job_check_true",
      }
    ],
  }
  session["text_targets"] = {
    "lifecycle_section_ids": {},
    "lifecycle_activity_ids": {},
    "external_transition_label_ids": {
      "idle_to_job_check": ["__mbse_text_fragment__0003"],
      "job_check_true": ["__mbse_text_fragment__0008"],
    },
    "external_transition_activity_ids": {
      "job_check_true": {"trace_guard_true_branch": ["__mbse_text_fragment__0009"]}
    },
    "internal_transition_section_ids": {},
    "internal_transition_event_ids": {},
    "internal_transition_activity_ids": {},
  }

  rendered = ViewerBrowserHarness(
    session_payload=session,
    svg_text=(
      '<svg xmlns="http://www.w3.org/2000/svg">'
      '<g id="processing"><polygon points="0,0 10,0 10,10 0,10"></polygon></g>'
      '<g id="job_check"><polygon points="0,0 10,5 0,10 -10,5"></polygon></g>'
      '<g id="idle_to_job_check"><path d="M0 0 L10 10"></path><polygon points="10,10 12,8 12,12"></polygon></g>'
      '<g id="job_check_true"><path d="M10 10 L20 20"></path><polygon points="20,20 22,18 22,22"></polygon></g>'
      '<text id="__mbse_text_fragment__0003">advance_evt</text>'
      '<text id="__mbse_text_fragment__0008">true</text>'
      '<text id="__mbse_text_fragment__0009">trace_guard_true_branch</text>'
      '</svg>'
    ),
  ).render()

  assert rendered["state_highlight_ids"] == ["job_check", "processing"]
  assert rendered["transition_highlight_ids"] == [
    "idle_to_job_check",
    "job_check_true",
  ]
  assert rendered["text_highlight_ids"] == [
    "__mbse_text_fragment__0003",
    "__mbse_text_fragment__0008",
    "__mbse_text_fragment__0009",
  ]


def test_viewer_submits_inline_variable_edits_with_existing_contract():
  updated_session = _viewer_session_payload(variables={"speed": 7, "mode": "auto"})
  harness = ViewerBrowserHarness(
    session_payload=_viewer_session_payload(variables={"speed": 3}),
    svg_text=(
      '<svg xmlns="http://www.w3.org/2000/svg">'
      '<g id="idle"></g><g id="idle_waiting"></g></svg>'
    ),
    fetch_responses={
      "/api/runtime/variables": [{"body": updated_session}],
    },
  )

  harness.render()
  submitted = harness.submit_variable("speed", "7")

  assert submitted["last_requests"]["/api/runtime/variables"] == {
    "variable_id": "speed",
    "value": 7,
  }
  assert submitted["variable_rows"] == [
    _expected_variable_row("speed", textbox_value="7"),
    _expected_variable_row("mode", textbox_value='"auto"'),
  ]


def test_viewer_submits_events_with_existing_contract_only():
  updated_session = _viewer_session_payload(variables={"speed": 11})
  updated_session["snapshot"]["active_ids"] = ["open"]
  updated_session["snapshot"]["active_path"] = ["open"]
  updated_session["snapshot"]["state_id"] = "open"
  updated_session["snapshot"]["last_event"] = {
    "event_id": "open_evt",
    "handled": True,
    "handler_kind": "external_transition",
    "handler_id": "waiting_to_open",
    "transition_path_ids": ["waiting_to_open"],
    "executed_activities": [],
  }
  harness = ViewerBrowserHarness(
    session_payload=_viewer_session_payload(variables={"speed": 3}),
    svg_text=(
      '<svg xmlns="http://www.w3.org/2000/svg">'
      '<g id="idle"></g><g id="idle_waiting"></g><g id="idle_init"></g>'
      '<g id="waiting_to_open"></g><g id="open"></g></svg>'
    ),
    fetch_responses={
      "/api/runtime/events": [{"body": updated_session}],
    },
  )

  harness.render()
  submitted = harness.submit_event("open_evt")

  assert submitted["last_requests"]["/api/runtime/events"] == {
    "event_id": "open_evt",
  }
  assert submitted["state_highlight_ids"] == ["open"]
  assert submitted["transition_highlight_ids"] == ["waiting_to_open"]
  assert submitted["fetch_counts"]["/api/runtime/events"] == 1
  assert submitted["fetch_counts"]["/api/session.json"] == 1
  assert submitted["variable_rows"] == [
    _expected_variable_row("speed", textbox_value="11"),
    _expected_variable_row("mode", textbox_value="", inline_unset_text="Unset"),
  ]


def test_viewer_submits_selected_event_without_extra_fields_for_other_option():
  updated_session = _viewer_session_payload(variables={"speed": 5})
  updated_session["snapshot"]["active_ids"] = ["idle_waiting"]
  updated_session["snapshot"]["active_path"] = ["idle", "idle_waiting"]
  updated_session["snapshot"]["state_id"] = "idle_waiting"
  updated_session["snapshot"]["last_event"] = {
    "event_id": "close_evt",
    "handled": False,
    "handler_kind": None,
    "handler_id": None,
    "transition_path_ids": [],
    "executed_activities": [],
  }
  harness = ViewerBrowserHarness(
    session_payload=_viewer_session_payload(variables={"speed": 3}),
    svg_text=(
      '<svg xmlns="http://www.w3.org/2000/svg">'
      '<g id="idle"></g><g id="idle_waiting"></g><g id="idle_init"></g>'
      '<g id="open"></g></svg>'
    ),
    fetch_responses={
      "/api/runtime/events": [{"body": updated_session}],
    },
  )

  harness.render()
  submitted = harness.submit_event("close_evt")

  assert submitted["last_requests"]["/api/runtime/events"] == {
    "event_id": "close_evt",
  }
  assert submitted["state_highlight_ids"] == ["idle_waiting"]
  assert submitted["transition_highlight_ids"] == []
  assert submitted["fetch_counts"]["/api/runtime/events"] == 1
  assert submitted["variable_rows"][0] == _expected_variable_row(
    "speed",
    textbox_value="5",
  )


def test_viewer_wheel_zoom_stays_client_side_without_extra_requests():
  harness = ViewerBrowserHarness(
    session_payload=_viewer_session_payload(variables={"speed": 3}),
    svg_text=(
      '<svg xmlns="http://www.w3.org/2000/svg">'
      '<g id="idle"></g><g id="idle_waiting"></g></svg>'
    ),
  )

  initial = harness.render()
  zoomed_in = harness.wheel_viewport(delta_y=-1)
  zoomed_out = harness.wheel_viewport(delta_y=1)

  assert initial["fetch_counts"] == {
    "/api/session.json": 1,
    "/artifacts/diagram.svg": 1,
    "/api/runtime/reset": 0,
    "/api/runtime/events": 0,
    "/api/runtime/variables": 0,
  }
  assert zoomed_in["zoom_transform"] == "scale(1.2)"
  assert zoomed_out["zoom_transform"] == "scale(1)"
  assert zoomed_out["fetch_counts"] == initial["fetch_counts"]


def test_viewer_sidebar_wheel_scroll_stays_isolated_from_diagram_zoom():
  harness = ViewerBrowserHarness(
    session_payload=_viewer_session_payload(variables={"speed": 3}),
    svg_text=(
      '<svg xmlns="http://www.w3.org/2000/svg">'
      '<g id="idle"></g><g id="idle_waiting"></g></svg>'
    ),
  )

  initial = harness.render()
  scrolled = harness.wheel_sidebar(delta_y=24)

  assert initial["zoom_transform"] == "scale(1)"
  assert scrolled["zoom_transform"] == "scale(1)"
  assert scrolled["sidebar_scroll_top"] > initial["sidebar_scroll_top"]
  assert scrolled["viewport_scroll_top"] == initial["viewport_scroll_top"]
  assert scrolled["fetch_counts"] == initial["fetch_counts"]


def test_viewer_sidebar_wheel_scroll_keeps_page_scroll_fixed():
  harness = ViewerBrowserHarness(
    session_payload=_viewer_session_payload(variables={"speed": 3}),
    svg_text=(
      '<svg xmlns="http://www.w3.org/2000/svg">'
      '<g id="idle"></g><g id="idle_waiting"></g></svg>'
    ),
  )

  initial = harness.render()
  scrolled = harness.wheel_sidebar(delta_y=48)

  assert initial["page_scroll_top"] == 0
  assert scrolled["page_scroll_top"] == 0
  assert scrolled["sidebar_scroll_top"] > initial["sidebar_scroll_top"]
  assert scrolled["zoom_transform"] == initial["zoom_transform"]


def test_viewer_viewport_wheel_zoom_does_not_scroll_sidebar():
  harness = ViewerBrowserHarness(
    session_payload=_viewer_session_payload(variables={"speed": 3}),
    svg_text=(
      '<svg xmlns="http://www.w3.org/2000/svg">'
      '<g id="idle"></g><g id="idle_waiting"></g></svg>'
    ),
  )

  initial = harness.render()
  zoomed = harness.wheel_viewport(delta_y=-1)

  assert zoomed["zoom_transform"] == "scale(1.2)"
  assert zoomed["sidebar_scroll_top"] == initial["sidebar_scroll_top"]
  assert zoomed["fetch_counts"] == initial["fetch_counts"]


def test_viewer_viewport_wheel_zoom_keeps_page_and_sidebar_scroll_fixed():
  harness = ViewerBrowserHarness(
    session_payload=_viewer_session_payload(variables={"speed": 3}),
    svg_text=(
      '<svg xmlns="http://www.w3.org/2000/svg">'
      '<g id="idle"></g><g id="idle_waiting"></g></svg>'
    ),
  )

  harness.render()
  sidebar_scrolled = harness.wheel_sidebar(delta_y=36)
  zoomed = harness.wheel_viewport(delta_y=-1)

  assert sidebar_scrolled["sidebar_scroll_top"] > 0
  assert zoomed["page_scroll_top"] == 0
  assert zoomed["sidebar_scroll_top"] == sidebar_scrolled["sidebar_scroll_top"]
  assert zoomed["zoom_transform"] == "scale(1.2)"


def test_viewer_drag_pan_updates_viewport_scroll_without_extra_requests():
  harness = ViewerBrowserHarness(
    session_payload=_viewer_session_payload(variables={"speed": 3}),
    svg_text=(
      '<svg xmlns="http://www.w3.org/2000/svg">'
      '<g id="idle"></g><g id="idle_waiting"></g></svg>'
    ),
  )

  harness.render()
  harness.wheel_viewport(delta_y=-1)
  panned = harness.drag_viewport(
    start_x=120,
    start_y=90,
    move_x=80,
    move_y=50,
  )

  assert panned["viewport_scroll_left"] == 40
  assert panned["viewport_scroll_top"] == 40
  assert panned["sidebar_scroll_top"] == 0
  assert panned["fetch_counts"] == {
    "/api/session.json": 1,
    "/artifacts/diagram.svg": 1,
    "/api/runtime/reset": 0,
    "/api/runtime/events": 0,
    "/api/runtime/variables": 0,
  }


def test_viewer_drag_pan_uses_document_lifecycle_and_clears_selection_guards():
  harness = ViewerBrowserHarness(
    session_payload=_viewer_session_payload(variables={"speed": 3}),
    svg_text=(
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 400">'
      '<g id="idle"></g><g id="idle_waiting"></g></svg>'
    ),
  )

  harness.render()
  harness.wheel_viewport(delta_y=-1)
  started = harness.start_viewport_drag(start_x=120, start_y=90)
  moved = harness.move_document_drag(move_x=80, move_y=50)
  ended = harness.end_document_drag(end_x=80, end_y=50)

  assert started["is_pan_active"] is True
  assert started["selection_guard_active"] is True
  assert started["document_listener_types"] == ["mousemove", "mouseup"]
  assert moved["viewport_scroll_left"] == 40
  assert moved["viewport_scroll_top"] == 40
  assert ended["is_pan_active"] is False
  assert ended["selection_guard_active"] is False
  assert ended["document_listener_types"] == []


def test_viewer_drag_pan_keeps_selection_side_effects_disabled_across_document_moves():
  harness = ViewerBrowserHarness(
    session_payload=_viewer_session_payload(variables={"speed": 3}),
    svg_text=(
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 400">'
      '<g id="idle"></g><g id="idle_waiting"></g></svg>'
    ),
  )

  harness.render()
  harness.wheel_viewport(delta_y=-1)
  harness.start_viewport_drag(start_x=120, start_y=90)
  moved_once = harness.move_document_drag(move_x=80, move_y=50)
  moved_twice = harness.move_document_drag(move_x=60, move_y=30)
  ended = harness.end_document_drag(end_x=60, end_y=30)

  assert moved_once["selection_side_effects"] == {
    "range_count": 0,
    "text": "",
  }
  assert moved_twice["selection_side_effects"] == {
    "range_count": 0,
    "text": "",
  }
  assert moved_twice["viewport_scroll_left"] == 60
  assert moved_twice["viewport_scroll_top"] == 60
  assert ended["selection_side_effects"] == {
    "range_count": 0,
    "text": "",
  }


def test_viewer_initial_fit_sets_baseline_and_preserves_pan_zoom_client_side():
  harness = ViewerBrowserHarness(
    session_payload=_viewer_session_payload(variables={"speed": 3}),
    svg_text=(
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 400">'
      '<g id="idle"></g><g id="idle_waiting"></g></svg>'
    ),
    viewport_size={"width": 400, "height": 200},
  )

  initial = harness.render()
  zoomed = harness.wheel_viewport(delta_y=-1)
  panned = harness.drag_viewport(
    start_x=120,
    start_y=90,
    move_x=80,
    move_y=50,
  )

  assert initial["fit_baseline"] == {
    "zoom_scale": 0.5,
    "scroll_left": 0,
    "scroll_top": 0,
  }
  assert initial["zoom_transform"] == "scale(0.5)"
  assert zoomed["zoom_transform"] == "scale(0.7)"
  assert panned["viewport_scroll_left"] == 40
  assert panned["viewport_scroll_top"] == 40
  assert initial["stage_size"] == {
    "width": 400,
    "height": 200,
    "scaled_width": 400,
    "scaled_height": 200,
  }
  assert initial["viewport_has_overflow"] == {"x": False, "y": False}
  assert zoomed["stage_size"] == {
    "width": 560,
    "height": 280,
    "scaled_width": 560,
    "scaled_height": 280,
  }
  assert zoomed["viewport_has_overflow"] == {"x": True, "y": True}
  assert panned["fetch_counts"] == initial["fetch_counts"]


def test_viewer_reset_view_restores_fit_without_runtime_reset_fetches():
  harness = ViewerBrowserHarness(
    session_payload=_viewer_session_payload(variables={"speed": 3}),
    svg_text=(
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100">'
      '<g id="idle"></g><g id="idle_waiting"></g></svg>'
    ),
    viewport_size={"width": 800, "height": 400},
  )

  initial = harness.render()
  harness.wheel_viewport(delta_y=-1)
  harness.drag_viewport(start_x=180, start_y=120, move_x=130, move_y=70)
  reset = harness.click("reset-view-button")

  assert initial["fit_baseline"] == {
    "zoom_scale": 4,
    "scroll_left": 0,
    "scroll_top": 0,
  }
  assert reset["zoom_transform"] == "scale(4)"
  assert reset["viewport_scroll_left"] == 0
  assert reset["viewport_scroll_top"] == 0
  assert reset["fetch_counts"]["/api/runtime/reset"] == 0
  assert reset["fetch_counts"]["/api/session.json"] == 1


def test_viewer_reset_view_recomputes_fit_after_viewport_resize():
  harness = ViewerBrowserHarness(
    session_payload=_viewer_session_payload(variables={"speed": 3}),
    svg_text=(
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 400">'
      '<g id="idle"></g><g id="idle_waiting"></g></svg>'
    ),
    viewport_size={"width": 400, "height": 200},
  )

  initial = harness.render()
  harness.resize_viewport(width=200, height=200)
  reset = harness.click("reset-view-button")

  assert initial["fit_baseline"] == {
    "zoom_scale": 0.5,
    "scroll_left": 0,
    "scroll_top": 0,
  }
  assert reset["fit_baseline"] == {
    "zoom_scale": 0.25,
    "scroll_left": 0,
    "scroll_top": 0,
  }
  assert reset["zoom_transform"] == "scale(0.25)"
  assert reset["stage_size"] == {
    "width": 200,
    "height": 200,
    "scaled_width": 200,
    "scaled_height": 100,
  }


def test_viewer_reset_view_fits_full_diagram_inside_padded_viewport():
  harness = ViewerBrowserHarness(
    session_payload=_viewer_session_payload(variables={"speed": 3}),
    svg_text=(
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 400">'
      '<g id="idle"></g><g id="idle_waiting"></g></svg>'
    ),
    viewport_size={"width": 400, "height": 200},
    viewport_padding={"x": 12, "y": 12},
  )

  initial = harness.render()
  harness.wheel_viewport(delta_y=-1)
  reset = harness.click("reset-view-button")

  assert initial["fit_baseline"] == {
    "zoom_scale": 0.44,
    "scroll_left": 0,
    "scroll_top": 0,
  }
  assert reset["fit_baseline"] == initial["fit_baseline"]
  assert reset["zoom_transform"] == "scale(0.44)"
  assert reset["stage_size"] == {
    "width": 376,
    "height": 176,
    "scaled_width": 352,
    "scaled_height": 176,
  }
  assert reset["viewport_has_overflow"] == {"x": False, "y": False}


def test_viewer_fit_uses_rendered_svg_size_for_graphviz_point_dimensions():
  harness = ViewerBrowserHarness(
    session_payload=_viewer_session_payload(variables={"speed": 3}),
    svg_text=(
      '<svg xmlns="http://www.w3.org/2000/svg" '
      'width="600pt" height="300pt" viewBox="0 0 600 300">'
      '<g id="idle"></g><g id="idle_waiting"></g></svg>'
    ),
    viewport_size={"width": 400, "height": 200},
  )

  initial = harness.render()
  harness.wheel_viewport(delta_y=-1)
  reset = harness.click("reset-view-button")

  assert initial["fit_baseline"] == {
    "zoom_scale": 0.5,
    "scroll_left": 0,
    "scroll_top": 0,
  }
  assert initial["zoom_transform"] == "scale(0.5)"
  assert reset["fit_baseline"] == initial["fit_baseline"]
  assert reset["zoom_transform"] == "scale(0.5)"
  assert reset["viewport_has_overflow"] == {"x": False, "y": False}


def test_viewer_splitter_drag_changes_sidebar_width_locally_only():
  harness = ViewerBrowserHarness(
    session_payload=_viewer_session_payload(variables={"speed": 3}),
    svg_text=(
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 300">'
      '<g id="idle"></g><g id="idle_waiting"></g></svg>'
    ),
  )

  initial = harness.render()
  resized = harness.drag_splitter(start_x=288, move_x=360)

  assert initial["sidebar_width_px"] == 288
  assert resized["sidebar_width_px"] == 360
  assert resized["zoom_transform"] == initial["zoom_transform"]
  assert resized["fetch_counts"] == initial["fetch_counts"]


def test_viewer_splitter_drag_refits_from_live_viewport_geometry():
  harness = ViewerBrowserHarness(
    session_payload=_viewer_session_payload(variables={"speed": 3}),
    svg_text=(
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 400">'
      '<g id="idle"></g><g id="idle_waiting"></g></svg>'
    ),
    viewport_size={"width": 400, "height": 200},
  )

  initial = harness.render()
  resized = harness.drag_splitter_with_viewport_resize(
    start_x=288,
    move_x=360,
    width=300,
    height=200,
  )

  assert initial["fit_baseline"] == {
    "zoom_scale": 0.5,
    "scroll_left": 0,
    "scroll_top": 0,
  }
  assert resized["sidebar_width_px"] == 360
  assert resized["fit_baseline"] == {
    "zoom_scale": 0.375,
    "scroll_left": 0,
    "scroll_top": 0,
  }
  assert resized["zoom_transform"] == "scale(0.375)"
  assert resized["viewport_size"] == {"width": 300, "height": 200}


def test_viewer_reset_view_refits_after_splitter_and_viewport_changes():
  harness = ViewerBrowserHarness(
    session_payload=_viewer_session_payload(variables={"speed": 3}),
    svg_text=(
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 400">'
      '<g id="idle"></g><g id="idle_waiting"></g></svg>'
    ),
    viewport_size={"width": 400, "height": 200},
  )

  initial = harness.render()
  resized = harness.drag_splitter_with_viewport_resize(
    start_x=288,
    move_x=360,
    width=260,
    height=180,
  )
  harness.wheel_viewport(delta_y=-1)
  harness.drag_viewport(start_x=140, start_y=100, move_x=80, move_y=40)
  reset = harness.click("reset-view-button")

  assert initial["fit_baseline"] == {
    "zoom_scale": 0.5,
    "scroll_left": 0,
    "scroll_top": 0,
  }
  assert resized["fit_baseline"] == {
    "zoom_scale": 0.325,
    "scroll_left": 0,
    "scroll_top": 0,
  }
  assert reset["fit_baseline"] == resized["fit_baseline"]
  assert reset["zoom_transform"] == "scale(0.325)"
  assert reset["viewport_scroll_left"] == 0
  assert reset["viewport_scroll_top"] == 0
  assert reset["viewport_has_overflow"] == {"x": False, "y": False}
  assert reset["stage_size"] == {
    "width": 260,
    "height": 180,
    "scaled_width": 260,
    "scaled_height": 130,
  }


def test_start_viewer_server_rejects_unknown_runtime_mutation_ids(tmp_path):
  session_dir = tmp_path / "session-artifacts"
  session_dir.mkdir()
  (session_dir / "diagram.svg").write_text(
    (
      '<svg xmlns="http://www.w3.org/2000/svg">'
      '<g id="idle"></g><g id="idle_waiting"></g><g id="idle_init"></g>'
      '<g id="waiting_to_open"></g><g id="open_to_idle"></g><g id="open"></g></svg>'
    ),
    encoding="utf-8",
  )
  server = start_viewer_server(
    session_dir,
    runtime_bridge=_build_runtime_bridge(),
    host="127.0.0.1",
    port=0,
  )

  try:
    with pytest.raises(HTTPError) as excinfo:
      urlopen(
        Request(
          f"{server.base_url}/api/runtime/events",
          data=json.dumps({"event_id": "unknown_evt"}).encode("utf-8"),
          headers={"Content-Type": "application/json"},
          method="POST",
        )
      )

    assert excinfo.value.code == 400
    assert "Unknown event_id 'unknown_evt'." in excinfo.value.read().decode("utf-8")
  finally:
    server.close()


def test_start_viewer_server_rejects_declared_svg_ids_missing_from_svg(tmp_path):
  session_dir = tmp_path / "session-artifacts"
  session_dir.mkdir()
  (session_dir / "diagram.svg").write_text(
    '<svg xmlns="http://www.w3.org/2000/svg"><g id="idle"></g></svg>',
    encoding="utf-8",
  )

  with pytest.raises(GraphvizValidationError) as excinfo:
    start_viewer_server(
      session_dir,
      runtime_bridge=ViewerRuntimeBridge(
        runtime_factory=lambda: build_hsm_runtime(_runtime_payload()),
        app_state=ViewerAppState(
          document_id="door_machine",
          svg_url="/artifacts/diagram.svg",
          highlightable_ids=("idle", "idle_waiting"),
        ),
      ),
      host="127.0.0.1",
      port=0,
    )

  assert excinfo.value.code == "rendered_svg.missing_id"
  assert excinfo.value.message == "Rendered SVG is missing expected id 'idle_waiting'."
