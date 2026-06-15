from __future__ import annotations

import pytest

from mbse.runtime.hsm import build_hsm_runtime
from mbse_web_viewer.app.runtime_bridge import ViewerRuntimeBridge
from mbse_web_viewer.app.viewer_state_types import RuntimeViewerTextTargets
from mbse_web_viewer.app.viewer_state_types import ViewerAppState
from tests.support.hsm_payloads import hsm_document
from tests.support.hsm_payloads import hsm_external_transition
from tests.support.hsm_payloads import hsm_guard
from tests.support.hsm_payloads import hsm_guard_branch
from tests.support.hsm_payloads import hsm_initial
from tests.support.hsm_payloads import hsm_state


def _runtime_payload() -> dict[str, object]:
  return hsm_document(
    "door_machine",
    variables=[
      {"id": "speed", "default": 0},
      {"id": "mode", "default": "idle"},
    ],
    events=[{"id": "open_evt"}, {"id": "close_evt"}, {"id": "stop_evt"}],
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
          ),
          hsm_state("idle_ready"),
        ],
        initial_transition=hsm_initial("idle_init", "idle_waiting"),
        external_transitions=[
          hsm_external_transition(
            "idle_to_closed",
            target_id="closed",
            event_id="stop_evt",
          )
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
      hsm_state("closed"),
    ],
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


def _app_state() -> ViewerAppState:
  return ViewerAppState(
    document_id="door_machine",
    svg_url="/artifacts/diagram.svg",
    highlightable_ids=(
      "idle",
      "idle_waiting",
      "open",
      "closed",
      "machine_init",
      "idle_init",
      "waiting_to_open",
      "open_to_idle",
      "idle_to_closed",
    ),
    text_targets=RuntimeViewerTextTargets(),
  )


def _build_bridge() -> ViewerRuntimeBridge:
  return ViewerRuntimeBridge(
    runtime_factory=lambda: build_hsm_runtime(_runtime_payload()),
    app_state=_app_state(),
  )


def test_viewer_runtime_bridge_serializes_snapshot_with_exact_active_ids():
  bridge = _build_bridge()

  session = bridge.get_session()

  assert session.document_id == "door_machine"
  assert session.svg_url == "/artifacts/diagram.svg"
  assert session.event_ids == ("open_evt", "close_evt", "stop_evt")
  assert session.variable_ids == ("speed", "mode")
  assert session.snapshot["state_id"] == "idle_waiting"
  assert session.snapshot["active_path"] == ("idle", "idle_waiting")
  assert session.snapshot["active_ids"] == ("idle_waiting",)
  assert "last_transition_id" not in session.snapshot
  assert session.snapshot["last_event"]["event_id"] is None
  assert session.snapshot["last_event"]["handled"] is True
  assert session.snapshot["last_event"]["handler_kind"] == "init"
  assert session.snapshot["last_event"]["handler_id"] is None
  assert session.snapshot["last_event"]["transition_path_ids"] == (
    "machine_init",
    "idle_init",
  )
  assert session.snapshot["last_event"]["executed_activities"] == ()
  assert session.snapshot["variables"] == {"speed": 0, "mode": "idle"}


def test_viewer_runtime_bridge_filters_active_ids_to_declared_svg_ids_only():
  bridge = ViewerRuntimeBridge(
    runtime_factory=lambda: build_hsm_runtime(_runtime_payload()),
    app_state=ViewerAppState(
      document_id="door_machine",
      svg_url="/artifacts/diagram.svg",
      highlightable_ids=("idle_waiting", "closed"),
      text_targets=RuntimeViewerTextTargets(),
    ),
  )

  session = bridge.get_session()

  assert session.snapshot["active_path"] == ("idle", "idle_waiting")
  assert session.snapshot["active_ids"] == ("idle_waiting",)
  assert session.snapshot["last_event"]["transition_path_ids"] == ()


def test_viewer_runtime_bridge_rejects_unknown_declared_ids():
  bridge = _build_bridge()

  with pytest.raises(ValueError, match="Unknown event_id 'missing_evt'\\."):
    bridge.send_event("missing_evt")

  with pytest.raises(ValueError, match="Unknown variable_id 'missing_var'\\."):
    bridge.set_variable("missing_var", 3)


def test_viewer_runtime_bridge_resets_to_a_fresh_initial_snapshot():
  bridge = _build_bridge()

  updated_session = bridge.set_variable("speed", 3)
  assert updated_session.snapshot["variables"] == {"speed": 3, "mode": "idle"}
  assert updated_session.snapshot["last_event"]["event_id"] is None
  moved_session = bridge.send_event("open_evt")
  assert moved_session.snapshot["state_id"] == "open"
  assert moved_session.snapshot["active_ids"] == ("open",)
  assert moved_session.snapshot["last_event"]["event_id"] == "open_evt"
  assert moved_session.snapshot["last_event"]["handled"] is True
  assert moved_session.snapshot["last_event"]["handler_kind"] == "external_transition"
  assert moved_session.snapshot["last_event"]["handler_id"] == "waiting_to_open"
  assert moved_session.snapshot["last_event"]["transition_path_ids"] == (
    "waiting_to_open",
  )

  reset_session = bridge.reset()

  assert reset_session.snapshot["state_id"] == "idle_waiting"
  assert reset_session.snapshot["active_path"] == ("idle", "idle_waiting")
  assert reset_session.snapshot["active_ids"] == ("idle_waiting",)
  assert reset_session.snapshot["last_event"]["event_id"] is None
  assert reset_session.snapshot["last_event"]["handled"] is True
  assert reset_session.snapshot["last_event"]["handler_kind"] == "init"
  assert reset_session.snapshot["last_event"]["transition_path_ids"] == (
    "machine_init",
    "idle_init",
  )
  assert reset_session.snapshot["variables"] == {"speed": 0, "mode": "idle"}


def test_viewer_runtime_bridge_filters_transition_paths_member_by_member():
  bridge = ViewerRuntimeBridge(
    runtime_factory=lambda: build_hsm_runtime(_runtime_payload()),
    app_state=ViewerAppState(
      document_id="door_machine",
      svg_url="/artifacts/diagram.svg",
      highlightable_ids=("idle_waiting", "idle_init"),
      text_targets=RuntimeViewerTextTargets(),
    ),
  )

  session = bridge.get_session()

  assert session.snapshot["last_event"]["transition_path_ids"] == (
    "idle_init",
  )


def test_viewer_runtime_bridge_serializes_static_text_targets_without_touching_runtime_contracts():
  bridge = ViewerRuntimeBridge(
    runtime_factory=lambda: build_hsm_runtime(_runtime_payload()),
    app_state=ViewerAppState(
      document_id="door_machine",
      svg_url="/artifacts/diagram.svg",
      highlightable_ids=("idle_waiting", "waiting_to_open"),
      text_targets=RuntimeViewerTextTargets(
        external_transition_label_ids={"waiting_to_open": ("__mbse_text_fragment__0001",)},
        lifecycle_section_ids={
          "idle": {"on_entry": ("__mbse_text_fragment__0002",)}
        },
      ),
    ),
  )

  session = bridge.get_session()

  assert session.snapshot["active_ids"] == ("idle_waiting",)
  assert session.snapshot["last_event"]["transition_path_ids"] == ()
  assert session.text_targets == RuntimeViewerTextTargets(
    external_transition_label_ids={"waiting_to_open": ("__mbse_text_fragment__0001",)},
    lifecycle_section_ids={
      "idle": {"on_entry": ("__mbse_text_fragment__0002",)}
    },
  )


def test_viewer_runtime_bridge_serializes_guard_node_and_branch_ids_when_declared():
  bridge = ViewerRuntimeBridge(
    runtime_factory=lambda: build_hsm_runtime(_guard_runtime_payload()),
    app_state=ViewerAppState(
      document_id="guard_machine",
      svg_url="/artifacts/diagram.svg",
      highlightable_ids=(
        "idle",
        "processing",
        "blocked",
        "machine_init",
        "idle_to_job_check",
        "job_check",
        "job_check_true",
        "job_check_false",
      ),
      text_targets=RuntimeViewerTextTargets(),
    ),
  )

  bridge.set_variable("job_queue", 1)
  session = bridge.send_event("advance_evt")

  assert session.snapshot["state_id"] == "processing"
  assert session.snapshot["active_ids"] == ("processing",)
  assert session.snapshot["last_event"]["handler_kind"] == "guard_transition"
  assert session.snapshot["last_event"]["guard_node_id"] == "job_check"
  assert session.snapshot["last_event"]["guard_branch_id"] == "job_check_true"
  assert session.snapshot["last_event"]["transition_path_ids"] == (
    "idle_to_job_check",
    "job_check_true",
  )


def test_viewer_runtime_bridge_filters_guard_node_and_branch_ids_to_declared_svg_ids_only():
  bridge = ViewerRuntimeBridge(
    runtime_factory=lambda: build_hsm_runtime(_guard_runtime_payload()),
    app_state=ViewerAppState(
      document_id="guard_machine",
      svg_url="/artifacts/diagram.svg",
      highlightable_ids=("processing", "idle_to_job_check"),
      text_targets=RuntimeViewerTextTargets(),
    ),
  )

  bridge.set_variable("job_queue", 1)
  session = bridge.send_event("advance_evt")

  assert session.snapshot["last_event"]["guard_node_id"] is None
  assert session.snapshot["last_event"]["guard_branch_id"] is None
  assert session.snapshot["last_event"]["transition_path_ids"] == (
    "idle_to_job_check",
  )
