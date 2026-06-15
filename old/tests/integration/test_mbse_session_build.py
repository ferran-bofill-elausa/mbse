from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

from mbse_web_viewer.app.session import build_viewer_session
from mbse_web_viewer.app.viewer_state_types import RuntimeViewerTextTargets
from mbse_web_viewer.app.viewer_state_types import ViewerAppState
from mbse_web_viewer.svg_render.graphviz.exceptions import GraphvizValidationError
from tests.support.hsm_payloads import hsm_document
from tests.support.hsm_payloads import hsm_external_transition
from tests.support.hsm_payloads import hsm_guard
from tests.support.hsm_payloads import hsm_guard_branch
from tests.support.hsm_payloads import hsm_initial
from tests.support.hsm_payloads import hsm_state


def test_build_viewer_session_writes_svg_and_render_artifacts_only(tmp_path):
  prepared_path = tmp_path / "prepared-document.json"
  output_dir = tmp_path / "session-artifacts"
  prepared_path.write_text(
    json.dumps(
      {
        "document_id": "demo-machine",
        "dot_source": (
          'digraph G { idle [id="state_idle", label="Idle"]; '
          'ready [id="state_ready", label="Ready"]; '
          'idle -> ready [id="edge_start", label="start"]; }'
        ),
        "highlightable_ids": ["state_idle", "state_ready", "edge_start"],
      }
    ),
    encoding="utf-8",
  )

  session = build_viewer_session(prepared_path, output_dir)

  assert session == ViewerAppState(
    document_id="demo-machine",
    svg_url="/artifacts/diagram.svg",
    highlightable_ids=("state_idle", "state_ready", "edge_start"),
    text_targets=RuntimeViewerTextTargets(),
  )
  assert (output_dir / "diagram.svg").exists() is True
  assert 'id="state_idle"' in (output_dir / "diagram.svg").read_text(
    encoding="utf-8"
  )
  assert 'id="edge_start"' in (output_dir / "diagram.svg").read_text(
    encoding="utf-8"
  )
  assert 'id="state_ready"' in (output_dir / "diagram.svg").read_text(
    encoding="utf-8"
  )
  assert (output_dir / "workbench-session.json").exists() is False
  assert (output_dir / "prepared-document.json").read_text(
    encoding="utf-8"
  ) == prepared_path.read_text(encoding="utf-8")


def test_build_viewer_session_rejects_missing_rendered_id(tmp_path):
  prepared_path = tmp_path / "prepared-document.json"
  output_dir = tmp_path / "session-artifacts"
  prepared_path.write_text(
    json.dumps(
      {
        "document_id": "demo-machine",
        "dot_source": (
          'digraph G { idle [id="state_idle", label="Idle"]; '
          'ready [id="state_ready", label="Ready"]; '
          'idle -> ready [id="edge_start", label="start"]; }'
        ),
        "highlightable_ids": ["state_idle", "state_ready", "edge_start"],
      }
    ),
    encoding="utf-8",
  )
  fake_svg = (
    '<svg xmlns="http://www.w3.org/2000/svg">'
    '<g id="state_idle"></g>'
    '<g id="state_ready"></g>'
    '</svg>'
  )

  with pytest.raises(GraphvizValidationError) as excinfo:
    build_viewer_session(
      prepared_path,
      output_dir,
      graphviz_command=(sys.executable, "-c", f"import sys; sys.stdout.write({fake_svg!r})"),
    )

  assert excinfo.value.code == "rendered_svg.missing_id"
  assert excinfo.value.message == "Rendered SVG is missing expected id 'edge_start'."
  assert (output_dir / "diagram.svg").exists() is False


def test_build_viewer_session_preserves_private_text_targets_separately_from_public_ids(
  tmp_path,
):
  hsm_path = tmp_path / "activity-machine.json"
  output_dir = tmp_path / "session-artifacts"
  hsm_path.write_text(
    json.dumps(
      {
        **hsm_document(
          "activity_machine",
          events=[{"id": "open_evt"}],
          initial_transition=hsm_initial("machine_init", "closed"),
          states=[
            hsm_state(
              "closed",
              on_entry=[
                {
                  "module": "tests.support.hsm_callable_fixtures",
                  "name": "count_increment",
                }
              ],
              external_transitions=[
                hsm_external_transition(
                  "closed_to_open",
                  target_id="open",
                  event_id="open_evt",
                  activities=[
                    {
                      "module": "tests.support.hsm_callable_fixtures",
                      "name": "trace_transition_activity",
                    }
                  ],
                )
              ],
            ),
            hsm_state("open"),
          ],
        ),
      }
    ),
    encoding="utf-8",
  )
  fake_graphviz_script = (
    "import html, re, sys; "
    "dot = sys.stdin.read(); "
    "ids = re.findall(r'id=\\\"([^\\\"]+)\\\"', dot); "
    "public_body = ''.join(f'<g id=\\\"{item}\\\"></g>' for item in ids); "
    "targets = re.findall(r'TOOLTIP=\\\"([^\\\"]+)\\\">([^<]+)</TD>', dot); "
    "target_body = ''.join(f'<g><a xmlns:xlink=\\\"http://www.w3.org/1999/xlink\\\" xlink:title=\\\"{html.escape(payload)}\\\"><text>{html.escape(text)}</text></a></g>' for payload, text in targets); "
    "sys.stdout.write(f'<svg xmlns=\\\"http://www.w3.org/2000/svg\\\">{public_body}{target_body}</svg>')"
  )

  session = build_viewer_session(
    hsm_path,
    output_dir,
    graphviz_command=(
      sys.executable,
      "-c",
      fake_graphviz_script,
    ),
  )

  assert session.highlightable_ids == (
    "closed",
    "open",
    "machine_init",
    "closed_to_open",
  )
  assert session.text_targets.lifecycle_section_ids == {
    "closed": {"on_entry": ("__mbse_text_fragment__0001",)}
  }
  assert session.text_targets.lifecycle_activity_ids == {
    "closed": {
      "on_entry": {"count_increment": ("__mbse_text_fragment__0002",)}
    }
  }
  assert session.text_targets.external_transition_label_ids == {
    "closed_to_open": ("__mbse_text_fragment__0003",)
  }
  assert session.text_targets.external_transition_activity_ids == {
    "closed_to_open": {
      "trace_transition_activity": ("__mbse_text_fragment__0004",)
    }
  }


def test_build_viewer_session_keeps_guard_node_public_ids_and_branch_text_targets(
  tmp_path,
):
  hsm_path = tmp_path / "guard-machine.json"
  output_dir = tmp_path / "session-artifacts"
  hsm_path.write_text(
    json.dumps(
      {
        **hsm_document(
          "guard_machine",
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
                    true_branch=hsm_guard_branch(
                      "processing",
                      activities=[
                        {
                          "module": "tests.support.hsm_callable_fixtures",
                          "name": "trace_guard_true_branch",
                        }
                      ],
                    ),
                    false_branch=hsm_guard_branch(
                      "blocked",
                      activities=[
                        {
                          "module": "tests.support.hsm_callable_fixtures",
                          "name": "trace_guard_false_branch",
                        }
                      ],
                    ),
                  ),
                )
              ],
            ),
            hsm_state("processing"),
            hsm_state("blocked"),
          ],
        ),
      }
    ),
    encoding="utf-8",
  )
  fake_graphviz_script = (
    "import html, re, sys; "
    "dot = sys.stdin.read(); "
    "ids = re.findall(r'id=\\\"([^\\\"]+)\\\"', dot); "
    "public_body = ''.join(f'<g id=\\\"{item}\\\"></g>' for item in ids); "
    "targets = re.findall(r'TOOLTIP=\\\"([^\\\"]+)\\\">([^<]+)</TD>', dot); "
    "target_body = ''.join(f'<g><a xmlns:xlink=\\\"http://www.w3.org/1999/xlink\\\" xlink:title=\\\"{html.escape(payload)}\\\"><text>{html.escape(text)}</text></a></g>' for payload, text in targets); "
    "sys.stdout.write(f'<svg xmlns=\\\"http://www.w3.org/2000/svg\\\">{public_body}{target_body}</svg>')"
  )

  session = build_viewer_session(
    hsm_path,
    output_dir,
    graphviz_command=(sys.executable, "-c", fake_graphviz_script),
  )

  assert session.highlightable_ids == (
    "idle",
    "processing",
    "blocked",
    "job_check",
    "machine_init",
    "idle_to_job_check",
    "job_check_true",
    "job_check_false",
  )
  assert session.text_targets.external_transition_label_ids == {
    "idle_to_job_check": ("__mbse_text_fragment__0001",),
    "job_check_true": ("__mbse_text_fragment__0002",),
    "job_check_false": ("__mbse_text_fragment__0004",),
  }
  assert session.text_targets.external_transition_activity_ids == {
    "job_check_true": {
      "trace_guard_true_branch": ("__mbse_text_fragment__0003",)
    },
    "job_check_false": {
      "trace_guard_false_branch": ("__mbse_text_fragment__0005",)
    },
  }
