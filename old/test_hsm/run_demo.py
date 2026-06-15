from __future__ import annotations

import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"
for path in (REPO_ROOT, SRC_ROOT):
  if str(path) not in sys.path:
    sys.path.insert(0, str(path))

from mbse.runtime.hsm import build_hsm_runtime


def _load_payload() -> dict[str, object]:
  path = Path(__file__).resolve().parent / "hsm.json"
  return json.loads(path.read_text(encoding="utf-8"))


def _print_snapshot(step: str, runtime) -> None:
  snapshot = runtime.get_snapshot()
  print(f"== {step} ==")
  print(f"state: {snapshot.state_id}")
  print(f"active_path: {list(snapshot.active_path)}")
  print(
    "last_event: "
    + json.dumps(
      {
        "event_id": snapshot.last_event.event_id,
        "guard_branch_id": snapshot.last_event.guard_branch_id,
        "guard_node_id": snapshot.last_event.guard_node_id,
        "handled": snapshot.last_event.handled,
        "handler_kind": snapshot.last_event.handler_kind,
        "handler_id": snapshot.last_event.handler_id,
        "transition_path_ids": list(snapshot.last_event.transition_path_ids),
      },
      sort_keys=True,
    )
  )
  print("variables:")
  print(json.dumps(snapshot.variables, indent=2, sort_keys=True))
  print()


def _assert_snapshot(
  runtime,
  *,
  state_id: str,
  event_id: str | None,
  handled: bool,
  transition_path_ids: tuple[str, ...],
  variables: dict[str, object],
) -> None:
  snapshot = runtime.get_snapshot()
  assert snapshot.state_id == state_id
  assert snapshot.last_event.event_id == event_id
  assert snapshot.last_event.handled is handled
  assert snapshot.last_event.transition_path_ids == transition_path_ids
  assert snapshot.variables == variables


def main() -> int:
  runtime = build_hsm_runtime(_load_payload())

  runtime.init()
  _assert_snapshot(
    runtime,
    state_id="idle",
    event_id=None,
    handled=True,
    transition_path_ids=("machine_init", "session_init"),
    variables={
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
    },
  )
  _print_snapshot("init", runtime)

  runtime.send_event("ping_evt")
  _assert_snapshot(
    runtime,
    state_id="idle",
    event_id="ping_evt",
    handled=True,
    transition_path_ids=(),
    variables={
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
    },
  )
  _print_snapshot("internal transition", runtime)

  runtime.send_event("start_evt")
  _assert_snapshot(
    runtime,
    state_id="idle",
    event_id="start_evt",
    handled=True,
    transition_path_ids=("idle_to_job_check", "job_check_false"),
    variables={
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
    },
  )
  _print_snapshot("guard false branch", runtime)

  runtime.set_variable("job_queue", 1)
  _print_snapshot("manual variable set", runtime)

  runtime.send_event("start_evt")
  _assert_snapshot(
    runtime,
    state_id="active",
    event_id="start_evt",
    handled=True,
    transition_path_ids=("idle_to_job_check", "job_check_true"),
    variables={
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
    },
  )
  _print_snapshot("guard true branch", runtime)

  runtime.send_event("refresh_evt")
  _assert_snapshot(
    runtime,
    state_id="active",
    event_id="refresh_evt",
    handled=True,
    transition_path_ids=("active_refresh",),
    variables={
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
    },
  )
  _print_snapshot("self transition", runtime)

  runtime.send_event("stop_evt")
  _assert_snapshot(
    runtime,
    state_id="idle",
    event_id="stop_evt",
    handled=True,
    transition_path_ids=("active_to_idle",),
    variables={
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
    },
  )
  _print_snapshot("return transition", runtime)

  runtime.send_event("shutdown_evt")
  _assert_snapshot(
    runtime,
    state_id="shutdown",
    event_id="shutdown_evt",
    handled=True,
    transition_path_ids=("session_to_shutdown",),
    variables={
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
    },
  )
  _print_snapshot("ancestor transition with parent exit", runtime)

  return 0


if __name__ == "__main__":
  raise SystemExit(main())
