from __future__ import annotations

from pathlib import Path

from mbse.model.hsm.hsm_model import HsmModel
from mbse.runtime.hsm.hsm_runtime import HsmRuntime


FIXTURE_PATH = (
  Path(__file__).resolve().parents[3] / "reference_model" / "hsm" / "reference_hsm_model.json"
)


def _build_runtime() -> HsmRuntime:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)
  runtime = HsmRuntime()
  runtime.init(model)
  return runtime


def _traceCallableNames(runtime: HsmRuntime, trace_index: int = -1) -> list[str]:
  trace = runtime.getExecutionLog()[trace_index]
  names: list[str] = []

  for entry in trace["entries"]:
    if entry["kind"] == "guard_condition":
      names.append(entry["guard_activity"]["name"])
      continue
    if entry.get("activity") is not None:
      names.append(entry["activity"]["name"])

  return names


def _play(runtime: HsmRuntime) -> None:
  assert runtime.play() is True


def _process_event(
  runtime: HsmRuntime,
  event_id: str,
  parameters: dict[str, object] | None = None,
) -> None:
  was_paused = runtime.isPaused()
  runtime.sendEvent(event_id, parameters)
  if was_paused:
    _play(runtime)


def test_hsm_init_starts_paused_with_root_initial_trace_planned() -> None:
  runtime = _build_runtime()

  assert runtime.isPaused() is True
  assert runtime.hasPendingExecution() is True
  assert runtime.getEventQueue() == []
  assert runtime.getState() == {"id": None, "label": None}
  assert runtime.getExecutionLog() == [{"event": {"event_id": None, "parameters": {}}, "entries": []}]
  assert runtime.getNextStep() == {
    "kind": "initial_transition",
    "source_state_id": None,
    "source_state_label": None,
    "target_state_id": "s1",
    "target_state_label": "S1",
    "activity": None,
  }


def test_hsm_play_executes_initialization_to_expected_leaf() -> None:
  runtime = _build_runtime()

  _play(runtime)

  assert runtime.getState() == {"id": "s11111", "label": "S11111"}
  assert runtime.getExecutionLog()[0]["entries"][-1] == {
    "kind": "change_active_state",
    "target_state_id": "s11111",
    "target_state_label": "S11111",
  }
  assert _traceCallableNames(runtime, 0) == [
    "s1_entry",
    "s1_initial",
    "s11_entry",
    "s11_initial",
    "s111_entry",
    "s111_initial",
    "s1111_entry",
    "s1111_initial",
    "s11111_entry",
  ]


def test_hsm_matches_expected_transition_sequence_in_running_mode() -> None:
  runtime = _build_runtime()

  expected_states = [
    "s2111",
    "s2112",
    "s2",
    "s21",
    "s31",
    "s3",
    "s311",
    "s41",
  ]

  for expected_state_id in expected_states:
    _process_event(runtime, "transition")
    assert runtime.getState()["id"] == expected_state_id


def test_hsm_records_representative_transition_trace_sequences() -> None:
  runtime = _build_runtime()

  _process_event(runtime, "transition")
  assert _traceCallableNames(runtime) == [
    "s1_to_s211",
    "s11111_exit",
    "s1111_exit",
    "s111_exit",
    "s11_exit",
    "s1_exit",
    "s2_entry",
    "s21_entry",
    "s211_entry",
    "s211_initial",
    "s2111_entry",
  ]

  _process_event(runtime, "transition")
  assert _traceCallableNames(runtime) == [
    "s2111_to_s2112",
    "s2112_entry",
  ]

  _process_event(runtime, "transition")
  _process_event(runtime, "transition")
  _process_event(runtime, "transition")
  _process_event(runtime, "transition")
  _process_event(runtime, "transition")
  _process_event(runtime, "transition")
  assert runtime.getState()["id"] == "s41"

  _process_event(
    runtime,
    "choose_transition",
    {
      "self_transition": False,
    },
  )
  assert _traceCallableNames(runtime) == [
    "guard_choose_transition",
    "guard_false_branch",
    "s41_exit",
    "s4_initial",
    "s41_entry",
  ]


def test_hsm_descendant_to_ancestor_transition_order() -> None:
  runtime = _build_runtime()

  _process_event(runtime, "transition")
  _process_event(runtime, "transition")

  _process_event(runtime, "transition")

  assert runtime.getState() == {"id": "s2", "label": "S2"}
  assert _traceCallableNames(runtime) == [
    "s2112_to_s2",
    "s2112_exit",
    "s211_exit",
    "s21_exit",
  ]


def test_hsm_ancestor_to_descendant_transition_order() -> None:
  runtime = _build_runtime()

  _process_event(runtime, "transition")
  _process_event(runtime, "transition")
  _process_event(runtime, "transition")

  _process_event(runtime, "transition")

  assert runtime.getState() == {"id": "s21", "label": "S21"}
  assert _traceCallableNames(runtime) == [
    "s2_to_s21",
    "s21_entry",
  ]


def test_hsm_child_to_parent_transition_order() -> None:
  runtime = _build_runtime()

  for _ in range(5):
    _process_event(runtime, "transition")

  _process_event(runtime, "transition")

  assert runtime.getState() == {"id": "s3", "label": "S3"}
  assert _traceCallableNames(runtime) == [
    "s31_to_s3",
    "s31_exit",
  ]


def test_hsm_guard_true_branch_is_real_self_transition() -> None:
  runtime = _build_runtime()

  for _ in range(8):
    _process_event(runtime, "transition")

  _process_event(
    runtime,
    "choose_transition",
    {
      "self_transition": True,
    },
  )

  assert runtime.getState() == {"id": "s41", "label": "S41"}
  assert [entry["kind"] for entry in runtime.getExecutionLog()[-1]["entries"]] == [
    "guarded_transition",
    "guard_condition",
    "guard_branch_transition",
    "on_exit",
    "on_entry",
  ]
  assert _traceCallableNames(runtime) == [
    "guard_choose_transition",
    "guard_true_branch",
    "s41_exit",
    "s41_entry",
  ]


def test_hsm_step_can_walk_init_and_first_event_from_paused_state() -> None:
  runtime = _build_runtime()

  while runtime.step():
    pass

  assert runtime.isPaused() is True
  assert runtime.hasPendingExecution() is False
  assert runtime.getState() == {"id": "s11111", "label": "S11111"}

  runtime.sendEvent("transition")
  assert runtime.hasPendingExecution() is True
  assert runtime.getEventQueue() == []
  assert runtime.getState() == {"id": "s11111", "label": "S11111"}

  while runtime.step():
    pass

  assert runtime.getState() == {"id": "s2111", "label": "S2111"}


def test_hsm_send_event_only_enqueues_while_paused() -> None:
  runtime = _build_runtime()

  runtime.sendEvent("transition")

  assert runtime.isPaused() is True
  assert runtime.hasPendingExecution() is True
  assert runtime.getEventQueue() == [{"event_id": "transition", "parameters": {}}]

  _play(runtime)

  assert runtime.getState() == {"id": "s2111", "label": "S2111"}


def test_hsm_internal_transition_keeps_active_state_and_receives_parameters(
) -> None:
  runtime = _build_runtime()

  for _ in range(8):
    _process_event(runtime, "transition")

  _process_event(runtime, "ping", {"value": 7})

  assert runtime.getState() == {"id": "s41", "label": "S41"}
  assert runtime.getVariable("last_ping_value") == 7
  assert runtime.getExecutionLog()[-1] == {
    "event": {"event_id": "ping", "parameters": {"value": 7}},
    "entries": [
      {
        "kind": "internal_transition",
        "source_state_id": "s41",
        "source_state_label": "S41",
        "activity": {
          "module": "tests.reference_model.hsm.reference_hsm_callables",
          "name": "trace_ping_value",
        },
      },
    ],
  }


def test_hsm_ping_can_bubble_to_s1_from_initial_leaf() -> None:
  runtime = _build_runtime()

  _process_event(runtime, "ping", {"value": 3})

  assert runtime.getState() == {"id": "s11111", "label": "S11111"}
  assert runtime.getVariable("last_ping_value") == 3
  assert runtime.getExecutionLog()[-1]["entries"][0] == {
    "kind": "internal_transition",
    "source_state_id": "s1",
    "source_state_label": "S1",
    "activity": {
      "module": "tests.reference_model.hsm.reference_hsm_callables",
      "name": "trace_ping_value",
    },
  }
  assert _traceCallableNames(runtime) == ["trace_ping_value"]


def test_hsm_set_mode_internal_transition_updates_current_mode() -> None:
  runtime = _build_runtime()

  for _ in range(8):
    _process_event(runtime, "transition")

  _process_event(runtime, "set_mode", {"target_mode": "forced"})

  assert runtime.getState() == {"id": "s41", "label": "S41"}
  assert runtime.getVariable("current_mode") == "forced"
  assert _traceCallableNames(runtime) == ["apply_target_mode"]


def test_hsm_ping_can_execute_directly_in_s2() -> None:
  runtime = _build_runtime()

  _process_event(runtime, "transition")
  _process_event(runtime, "transition")
  _process_event(runtime, "transition")

  assert runtime.getState() == {"id": "s2", "label": "S2"}

  _process_event(runtime, "ping", {"value": 5})

  assert runtime.getState() == {"id": "s2", "label": "S2"}
  assert runtime.getVariable("last_ping_value") == 5
  assert runtime.getExecutionLog()[-1]["entries"][0] == {
    "kind": "internal_transition",
    "source_state_id": "s2",
    "source_state_label": "S2",
    "activity": {
      "module": "tests.reference_model.hsm.reference_hsm_callables",
      "name": "trace_ping_value",
    },
  }
  assert _traceCallableNames(runtime) == ["trace_ping_value"]


def test_hsm_ping_can_bubble_to_ancestor_and_enqueue_followup_transition() -> None:
  runtime = _build_runtime()

  _process_event(runtime, "transition")
  _process_event(runtime, "ping", {"value": 7})

  assert runtime.getState() == {"id": "s2112", "label": "S2112"}
  assert runtime.getVariable("last_ping_value") == 7
  assert [trace["event"]["event_id"] for trace in runtime.getExecutionLog()] == [
    None,
    "transition",
    "ping",
    "transition",
  ]
  assert runtime.getExecutionLog()[-2]["entries"][0] == {
    "kind": "internal_transition",
    "source_state_id": "s211",
    "source_state_label": "S211",
    "activity": {
      "module": "tests.reference_model.hsm.reference_hsm_callables",
      "name": "trace_ping_value",
    },
  }
  assert runtime.getExecutionLog()[-2]["entries"][-1] == {
    "kind": "internal_transition",
    "source_state_id": "s211",
    "source_state_label": "S211",
    "activity": {
      "module": "tests.reference_model.hsm.reference_hsm_callables",
      "name": "enqueue_transition",
    },
  }
  assert runtime.getExecutionLog()[-1]["entries"][0] == {
    "kind": "external_transition",
    "source_state_id": "s2111",
    "source_state_label": "S2111",
    "target_state_id": "s2112",
    "target_state_label": "S2112",
    "activity": {
      "module": "tests.reference_model.hsm.reference_hsm_callables",
      "name": "s2111_to_s2112",
    },
  }
  assert _traceCallableNames(runtime, -2) == ["trace_ping_value", "enqueue_transition"]
  assert runtime.getEventQueue() == []


def test_hsm_ping_can_execute_directly_in_s3() -> None:
  runtime = _build_runtime()

  for _ in range(6):
    _process_event(runtime, "transition")

  assert runtime.getState() == {"id": "s3", "label": "S3"}

  _process_event(runtime, "ping", {"value": 9})

  assert runtime.getState() == {"id": "s3", "label": "S3"}
  assert runtime.getVariable("last_ping_value") == 9
  assert runtime.getExecutionLog()[-1]["entries"][0] == {
    "kind": "internal_transition",
    "source_state_id": "s3",
    "source_state_label": "S3",
    "activity": {
      "module": "tests.reference_model.hsm.reference_hsm_callables",
      "name": "trace_ping_value",
    },
  }
  assert _traceCallableNames(runtime) == ["trace_ping_value"]


def test_hsm_pause_plans_the_next_event_without_executing_it() -> None:
  runtime = _build_runtime()

  _play(runtime)
  runtime.pause()

  runtime.sendEvent("transition")

  assert runtime.isPaused() is True
  assert runtime.hasPendingExecution() is True
  assert runtime.getEventQueue() == []
  assert runtime.getState() == {"id": "s11111", "label": "S11111"}
  assert runtime.getNextStep() == {
    "kind": "external_transition",
    "source_state_id": "s1",
    "source_state_label": "S1",
    "target_state_id": "s211",
    "target_state_label": "S211",
    "activity": {
      "module": "tests.reference_model.hsm.reference_hsm_callables",
      "name": "s1_to_s211",
    },
  }


def test_hsm_paused_step_keeps_active_state_change_as_explicit_runtime_step() -> None:
  runtime = _build_runtime()

  _play(runtime)
  runtime.pause()
  runtime.sendEvent("transition")
  runtime.sendEvent("transition")

  next_step = None
  while runtime.hasPendingExecution():
    next_step = runtime.getNextStep()
    assert next_step is not None
    if next_step["kind"] == "on_entry" and next_step["source_state_id"] == "s2111":
      break
    runtime.step()

  assert next_step == {
    "kind": "on_entry",
    "source_state_id": "s2111",
    "source_state_label": "S2111",
    "activity": {
      "module": "tests.reference_model.hsm.reference_hsm_callables",
      "name": "s2111_entry",
    },
  }
  assert runtime.step() is True

  assert runtime.getState() == {"id": "s11111", "label": "S11111"}
  assert runtime.hasPendingExecution() is True
  assert runtime.getEventQueue() == [{"event_id": "transition", "parameters": {}}]
  assert runtime.getNextStep() == {
    "kind": "change_active_state",
    "target_state_id": "s2111",
    "target_state_label": "S2111",
  }

  assert runtime.step() is True

  assert runtime.getState() == {"id": "s2111", "label": "S2111"}
  assert runtime.hasPendingExecution() is False
  assert runtime.getEventQueue() == [{"event_id": "transition", "parameters": {}}]
  assert runtime.getExecutionLog()[-1]["entries"][-1] == {
    "kind": "change_active_state",
    "target_state_id": "s2111",
    "target_state_label": "S2111",
  }

  assert runtime.step() is False

  assert runtime.hasPendingExecution() is True
  assert runtime.getEventQueue() == []
  assert runtime.getExecutionLog()[-1] == {
    "event": {"event_id": "transition", "parameters": {}},
    "entries": [],
  }
  assert runtime.getNextStep() == {
    "kind": "external_transition",
    "source_state_id": "s2111",
    "source_state_label": "S2111",
    "target_state_id": "s2112",
    "target_state_label": "S2112",
    "activity": {
      "module": "tests.reference_model.hsm.reference_hsm_callables",
      "name": "s2111_to_s2112",
    },
  }


def test_hsm_send_event_auto_executes_while_running() -> None:
  runtime = _build_runtime()

  _play(runtime)
  assert runtime.isPaused() is False

  runtime.sendEvent("transition")

  assert runtime.isPaused() is False
  assert runtime.hasPendingExecution() is False
  assert runtime.getEventQueue() == []
  assert runtime.getState() == {"id": "s2111", "label": "S2111"}


def test_hsm_set_state_forces_state_and_clears_pending_work() -> None:
  runtime = _build_runtime()

  runtime.sendEvent("transition")
  runtime.setVariable("last_ping_value", 23)
  runtime.setState("s41")

  assert runtime.getState() == {"id": "s41", "label": "S41"}
  assert runtime.getVariable("last_ping_value") == 23
  assert runtime.hasPendingExecution() is False
  assert runtime.getEventQueue() == []
  assert runtime.getExecutionLog()[-1] == {
    "event": {"event_id": None, "parameters": {}},
    "entries": [
      {
        "kind": "forced_state",
        "target_state_id": "s41",
        "target_state_label": "S41",
      }
    ],
  }
