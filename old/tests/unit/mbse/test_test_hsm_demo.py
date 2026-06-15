from __future__ import annotations

import json
from pathlib import Path

from mbse.runtime.hsm import build_hsm_runtime
from test_hsm import run_demo


def _load_payload() -> dict[str, object]:
  path = Path(__file__).resolve().parents[3] / "test_hsm" / "hsm.json"
  return json.loads(path.read_text(encoding="utf-8"))


def test_test_hsm_example_mutates_business_variables_across_steps() -> None:
  runtime = build_hsm_runtime(_load_payload())

  runtime.init()
  assert runtime.get_snapshot().variables == {
    "active_entries": 0,
    "active_exits": 0,
    "completed_jobs": 0,
    "health_checks": 0,
    "idle_entries": 1,
    "idle_exits": 0,
    "job_queue": 0,
    "last_action": "idle.ready",
    "refresh_count": 0,
    "selected_job": None,
    "session_phase": "idle",
    "session_status": "open",
    "shutdown_reason": None,
    "trace": [
      "session.entry",
      "session.initial",
      "session.initial.activity",
      "idle.entry",
    ],
  }

  runtime.send_event("ping_evt")
  assert runtime.get_snapshot().variables == {
    "active_entries": 0,
    "active_exits": 0,
    "completed_jobs": 0,
    "health_checks": 1,
    "idle_entries": 1,
    "idle_exits": 0,
    "job_queue": 0,
    "last_action": "idle.health_check",
    "refresh_count": 0,
    "selected_job": None,
    "session_phase": "idle",
    "session_status": "open",
    "shutdown_reason": None,
    "trace": [
      "session.entry",
      "session.initial",
      "session.initial.activity",
      "idle.entry",
      "internal.ping",
    ],
  }

  runtime.send_event("start_evt")
  assert runtime.get_snapshot().variables == {
    "active_entries": 0,
    "active_exits": 0,
    "completed_jobs": 0,
    "health_checks": 1,
    "idle_entries": 1,
    "idle_exits": 0,
    "job_queue": 0,
    "last_action": "guard.false_branch",
    "refresh_count": 0,
    "selected_job": None,
    "session_phase": "idle",
    "session_status": "open",
    "shutdown_reason": None,
    "trace": [
      "session.entry",
      "session.initial",
      "session.initial.activity",
      "idle.entry",
      "internal.ping",
      "guard.can_start_processing",
      "guard.false_branch",
    ],
  }

  runtime.set_variable("job_queue", 1)
  runtime.send_event("start_evt")
  assert runtime.get_snapshot().variables == {
    "active_entries": 1,
    "active_exits": 0,
    "completed_jobs": 0,
    "health_checks": 1,
    "idle_entries": 1,
    "idle_exits": 1,
    "job_queue": 0,
    "last_action": "active.processing",
    "refresh_count": 0,
    "selected_job": "ORD-001",
    "session_phase": "active",
    "session_status": "open",
    "shutdown_reason": None,
    "trace": [
      "session.entry",
      "session.initial",
      "session.initial.activity",
      "idle.entry",
      "internal.ping",
      "guard.can_start_processing",
      "guard.false_branch",
      "guard.can_start_processing",
      "idle.exit",
      "transition.start",
      "active.entry",
    ],
  }

  runtime.send_event("refresh_evt")
  assert runtime.get_snapshot().variables == {
    "active_entries": 2,
    "active_exits": 1,
    "completed_jobs": 0,
    "health_checks": 1,
    "idle_entries": 1,
    "idle_exits": 1,
    "job_queue": 0,
    "last_action": "active.processing",
    "refresh_count": 1,
    "selected_job": "ORD-001",
    "session_phase": "active",
    "session_status": "open",
    "shutdown_reason": None,
    "trace": [
      "session.entry",
      "session.initial",
      "session.initial.activity",
      "idle.entry",
      "internal.ping",
      "guard.can_start_processing",
      "guard.false_branch",
      "guard.can_start_processing",
      "idle.exit",
      "transition.start",
      "active.entry",
      "active.exit",
      "transition.refresh",
      "active.entry",
    ],
  }

  runtime.send_event("stop_evt")
  assert runtime.get_snapshot().variables == {
    "active_entries": 2,
    "active_exits": 2,
    "completed_jobs": 1,
    "health_checks": 1,
    "idle_entries": 2,
    "idle_exits": 1,
    "job_queue": 0,
    "last_action": "idle.ready",
    "refresh_count": 1,
    "selected_job": None,
    "session_phase": "idle",
    "session_status": "open",
    "shutdown_reason": None,
    "trace": [
      "session.entry",
      "session.initial",
      "session.initial.activity",
      "idle.entry",
      "internal.ping",
      "guard.can_start_processing",
      "guard.false_branch",
      "guard.can_start_processing",
      "idle.exit",
      "transition.start",
      "active.entry",
      "active.exit",
      "transition.refresh",
      "active.entry",
      "active.exit",
      "transition.stop",
      "idle.entry",
    ],
  }

  runtime.send_event("shutdown_evt")
  assert runtime.get_snapshot().variables == {
    "active_entries": 2,
    "active_exits": 2,
    "completed_jobs": 1,
    "health_checks": 1,
    "idle_entries": 2,
    "idle_exits": 2,
    "job_queue": 0,
    "last_action": "shutdown.archived",
    "refresh_count": 1,
    "selected_job": None,
    "session_phase": "shutdown",
    "session_status": "closed",
    "shutdown_reason": "operator_request",
    "trace": [
      "session.entry",
      "session.initial",
      "session.initial.activity",
      "idle.entry",
      "internal.ping",
      "guard.can_start_processing",
      "guard.false_branch",
      "guard.can_start_processing",
      "idle.exit",
      "transition.start",
      "active.entry",
      "active.exit",
      "transition.refresh",
      "active.entry",
      "active.exit",
      "transition.stop",
      "idle.entry",
      "idle.exit",
      "session.exit",
      "transition.shutdown",
      "shutdown.entry",
    ],
  }


def test_test_hsm_demo_runner_prints_viewer_friendly_variables(capsys) -> None:
  assert run_demo.main() == 0

  output = capsys.readouterr().out

  assert (
    'last_event: {"event_id": null, "guard_branch_id": null,'
    ' "guard_node_id": null, "handled": true'
  ) in output
  assert (
    'last_event: {"event_id": "start_evt", "guard_branch_id": "job_check_false",'
    ' "guard_node_id": "job_check", "handled": true,'
    ' "handler_id": "idle_to_job_check", "handler_kind": "guard_transition",'
    ' "transition_path_ids": ["idle_to_job_check", "job_check_false"]}'
  ) in output
  assert (
    'last_event: {"event_id": "shutdown_evt", "guard_branch_id": null,'
    ' "guard_node_id": null, "handled": true,'
    ' "handler_id": "session_to_shutdown", "handler_kind": "external_transition",'
    ' "transition_path_ids": ["session_to_shutdown"]}'
  ) in output
  assert "variables:" in output
  assert '"session_phase": "shutdown"' in output
  assert '"session_status": "closed"' in output
  assert '"completed_jobs": 1' in output
  assert '"health_checks": 1' in output
  assert '"refresh_count": 1' in output


def test_test_hsm_example_guard_node_reenters_idle_when_queue_is_empty() -> None:
  runtime = build_hsm_runtime(_load_payload())

  runtime.init()
  assert runtime.get_snapshot().variables["job_queue"] == 0
  assert runtime.send_event("start_evt") is True

  snapshot = runtime.get_snapshot()
  assert snapshot.state_id == "idle"
  assert snapshot.last_event.event_id == "start_evt"
  assert snapshot.last_event.handled is True
  assert snapshot.last_event.handler_kind == "guard_transition"
  assert snapshot.last_event.handler_id == "idle_to_job_check"
  assert snapshot.last_event.guard_node_id == "job_check"
  assert snapshot.last_event.guard_branch_id == "job_check_false"
  assert snapshot.last_event.transition_path_ids == (
    "idle_to_job_check",
    "job_check_false",
  )
  assert snapshot.variables["trace"][-2:] == [
    "guard.can_start_processing",
    "guard.false_branch",
  ]
