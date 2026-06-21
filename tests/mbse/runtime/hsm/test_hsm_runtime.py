from __future__ import annotations

from pathlib import Path

from mbse.model.hsm.hsm_model import HsmModel
from mbse.runtime.hsm.hsm_runtime import HsmRuntime


FIXTURE_PATH = (
  Path(__file__).resolve().parents[3] / "reference_model" / "hsm" / "reference_hsm_model.json"
)


def _build_runtime(*, mode: str = "rtc") -> HsmRuntime:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)
  runtime = HsmRuntime()
  runtime.init(model, mode=mode)
  return runtime


def _traceCallableNames(runtime: HsmRuntime, trace_index: int = -1) -> list[str]:
  trace = runtime.getExecutionLog()[trace_index]
  names: list[str] = []

  for entry in trace["entries"]:
    if entry["kind"] == "guard_condition":
      names.append(entry["guard_activity"]["name"])
      continue
    if entry["kind"] in {"activity", "on_entry", "on_initial", "on_exit"}:
      names.append(entry["activity"]["name"])

  return names


def test_hsm_reaches_expected_initial_leaf_in_rtc_mode() -> None:
  runtime = _build_runtime(mode="rtc")

  assert runtime.getState() == {"id": "s11111", "label": "S11111"}
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


def test_hsm_matches_expected_transition_sequence_in_rtc_mode() -> None:
  runtime = _build_runtime(mode="rtc")

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
    runtime.sendEvent("transition")
    assert runtime.getState()["id"] == expected_state_id


def test_hsm_records_representative_transition_trace_sequences() -> None:
  runtime = _build_runtime(mode="rtc")

  runtime.sendEvent("transition")
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

  runtime.sendEvent("transition")
  assert _traceCallableNames(runtime) == [
    "s2111_to_s2112",
    "s2112_entry",
  ]

  runtime.sendEvent("transition")
  runtime.sendEvent("transition")
  runtime.sendEvent("transition")
  runtime.sendEvent("transition")
  runtime.sendEvent("transition")
  runtime.sendEvent("transition")
  assert runtime.getState()["id"] == "s41"

  runtime.sendEvent(
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
  runtime = _build_runtime(mode="rtc")

  runtime.sendEvent("transition")
  runtime.sendEvent("transition")

  runtime.sendEvent("transition")

  assert runtime.getState() == {"id": "s2", "label": "S2"}
  assert _traceCallableNames(runtime) == [
    "s2112_to_s2",
    "s2112_exit",
    "s211_exit",
    "s21_exit",
  ]


def test_hsm_ancestor_to_descendant_transition_order() -> None:
  runtime = _build_runtime(mode="rtc")

  runtime.sendEvent("transition")
  runtime.sendEvent("transition")
  runtime.sendEvent("transition")

  runtime.sendEvent("transition")

  assert runtime.getState() == {"id": "s21", "label": "S21"}
  assert _traceCallableNames(runtime) == [
    "s2_to_s21",
    "s21_entry",
  ]


def test_hsm_child_to_parent_transition_order() -> None:
  runtime = _build_runtime(mode="rtc")

  for _ in range(5):
    runtime.sendEvent("transition")

  runtime.sendEvent("transition")

  assert runtime.getState() == {"id": "s3", "label": "S3"}
  assert _traceCallableNames(runtime) == [
    "s31_to_s3",
    "s31_exit",
  ]


def test_hsm_guard_true_branch_is_real_self_transition() -> None:
  runtime = _build_runtime(mode="rtc")

  for _ in range(8):
    runtime.sendEvent("transition")

  runtime.sendEvent(
    "choose_transition",
    {
      "self_transition": True,
    },
  )

  assert runtime.getState() == {"id": "s41", "label": "S41"}
  assert _traceCallableNames(runtime) == [
    "guard_choose_transition",
    "guard_true_branch",
    "s41_exit",
    "s41_entry",
  ]


def test_hsm_step_mode_reaches_same_initial_and_first_event_states() -> None:
  runtime = _build_runtime(mode="step")

  assert runtime.getState() == {"id": None, "label": None}
  assert runtime.getExecutionLog() == [{"event": {"event_id": None, "parameters": {}}, "entries": []}]

  while runtime.step():
    pass

  assert runtime.getState() == {"id": "s11111", "label": "S11111"}

  runtime.sendEvent("transition")
  assert runtime.getState() == {"id": "s11111", "label": "S11111"}
  assert runtime.getExecutionLog()[-1]["event"]["event_id"] == "transition"

  while runtime.step():
    pass

  assert runtime.getState() == {"id": "s2111", "label": "S2111"}


def test_hsm_internal_transition_keeps_active_state_and_receives_parameters(
) -> None:
  runtime = _build_runtime(mode="rtc")

  for _ in range(8):
    runtime.sendEvent("transition")

  runtime.sendEvent("ping", {"value": 7})

  assert runtime.getState() == {"id": "s41", "label": "S41"}
  assert runtime.getVariable("last_ping_value") == 7
  assert runtime.getExecutionLog()[-1] == {
    "event": {"event_id": "ping", "parameters": {"value": 7}},
    "entries": [
      {
        "kind": "internal_transition",
        "source_state_id": "s41",
        "source_state_label": "S41",
      },
      {
        "kind": "activity",
        "source_state_id": "s41",
        "source_state_label": "S41",
        "activity_owner": "internal_transition",
        "activity": {
          "module": "tests.reference_model.hsm.reference_hsm_callables",
          "name": "trace_ping_value",
        },
      },
    ],
  }


def test_hsm_ping_can_bubble_to_s1_from_initial_leaf() -> None:
  runtime = _build_runtime(mode="rtc")

  runtime.sendEvent("ping", {"value": 3})

  assert runtime.getState() == {"id": "s11111", "label": "S11111"}
  assert runtime.getVariable("last_ping_value") == 3
  assert runtime.getExecutionLog()[-1]["entries"][0] == {
    "kind": "internal_transition",
    "source_state_id": "s1",
    "source_state_label": "S1",
  }
  assert _traceCallableNames(runtime) == ["trace_ping_value"]


def test_hsm_set_mode_internal_transition_updates_current_mode() -> None:
  runtime = _build_runtime(mode="rtc")

  for _ in range(8):
    runtime.sendEvent("transition")

  runtime.sendEvent("set_mode", {"target_mode": "forced"})

  assert runtime.getState() == {"id": "s41", "label": "S41"}
  assert runtime.getVariable("current_mode") == "forced"
  assert _traceCallableNames(runtime) == ["apply_target_mode"]


def test_hsm_ping_can_execute_directly_in_s2() -> None:
  runtime = _build_runtime(mode="rtc")

  runtime.sendEvent("transition")
  runtime.sendEvent("transition")
  runtime.sendEvent("transition")

  assert runtime.getState() == {"id": "s2", "label": "S2"}

  runtime.sendEvent("ping", {"value": 5})

  assert runtime.getState() == {"id": "s2", "label": "S2"}
  assert runtime.getVariable("last_ping_value") == 5
  assert runtime.getExecutionLog()[-1]["entries"][0] == {
    "kind": "internal_transition",
    "source_state_id": "s2",
    "source_state_label": "S2",
  }
  assert _traceCallableNames(runtime) == ["trace_ping_value"]


def test_hsm_ping_can_bubble_to_ancestor_and_enqueue_followup_transition() -> None:
  runtime = _build_runtime(mode="rtc")

  runtime.sendEvent("transition")
  runtime.sendEvent("ping", {"value": 7})

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
  }
  assert _traceCallableNames(runtime, -2) == ["trace_ping_value"]


def test_hsm_ping_can_execute_directly_in_s3() -> None:
  runtime = _build_runtime(mode="rtc")

  for _ in range(6):
    runtime.sendEvent("transition")

  assert runtime.getState() == {"id": "s3", "label": "S3"}

  runtime.sendEvent("ping", {"value": 9})

  assert runtime.getState() == {"id": "s3", "label": "S3"}
  assert runtime.getVariable("last_ping_value") == 9
  assert runtime.getExecutionLog()[-1]["entries"][0] == {
    "kind": "internal_transition",
    "source_state_id": "s3",
    "source_state_label": "S3",
  }
  assert _traceCallableNames(runtime) == ["trace_ping_value"]
