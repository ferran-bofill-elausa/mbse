from __future__ import annotations

from pathlib import Path

from mbse.model.hsm.hsm_model import HsmModel
from mbse.runtime.hsm.hsm_runtime import HsmRuntime


FIXTURE_PATH = Path(__file__).with_name("fixtures") / "reference_hsm_model.json"


def _build_runtime(*, mode: str = "rtc") -> HsmRuntime:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)
  runtime = HsmRuntime()
  runtime.init(model, mode=mode)
  return runtime


def test_reference_hsm_reaches_expected_initial_leaf_in_rtc_mode() -> None:
  runtime = _build_runtime(mode="rtc")

  assert runtime.getState() == {"id": "s11111", "label": "S11111"}
  assert runtime.getVariable("trace") == [
    "s1.entry",
    "s1.initial",
    "s11.entry",
    "s11.initial",
    "s111.entry",
    "s111.initial",
    "s1111.entry",
    "s1111.initial",
    "s11111.entry",
  ]


def test_reference_hsm_matches_reference_transition_sequence_in_rtc_mode() -> None:
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
    "s41",
    "s41",
  ]

  for index, expected_state_id in enumerate(expected_states, start=1):
    if index == 9:
      runtime.setVariable("self_transition", True)
    if index == 10:
      runtime.setVariable("self_transition", False)

    runtime.sendEvent("transition")
    assert runtime.getState()["id"] == expected_state_id


def test_reference_hsm_records_representative_transition_trace_sequences() -> None:
  runtime = _build_runtime(mode="rtc")

  runtime.setVariable("trace", [])
  runtime.sendEvent("transition")
  assert runtime.getVariable("trace") == [
    "s11111.exit",
    "s1111.exit",
    "s111.exit",
    "s11.exit",
    "s1.exit",
    "s1.to_s211",
    "s2.entry",
    "s21.entry",
    "s211.entry",
    "s211.initial",
    "s2111.entry",
  ]

  runtime.setVariable("trace", [])
  runtime.sendEvent("transition")
  assert runtime.getVariable("trace") == [
    "s2111.to_s2112",
    "s2112.entry",
  ]

  runtime.setVariable("trace", [])
  runtime.sendEvent("transition")
  runtime.sendEvent("transition")
  runtime.sendEvent("transition")
  runtime.sendEvent("transition")
  runtime.sendEvent("transition")
  runtime.sendEvent("transition")
  assert runtime.getState()["id"] == "s41"

  runtime.setVariable("trace", [])
  runtime.setVariable("self_transition", False)
  runtime.sendEvent("transition")
  assert runtime.getVariable("trace") == [
    "guard.self_transition",
    "s41.exit",
    "guard.false_branch",
    "s4.initial",
    "s41.entry",
  ]


def test_reference_hsm_descendant_to_ancestor_order_matches_c_semantics() -> None:
  runtime = _build_runtime(mode="rtc")

  runtime.sendEvent("transition")
  runtime.sendEvent("transition")
  runtime.setVariable("trace", [])

  runtime.sendEvent("transition")

  assert runtime.getState() == {"id": "s2", "label": "S2"}
  assert runtime.getVariable("trace") == [
    "s2112.exit",
    "s211.exit",
    "s21.exit",
    "s2112.to_s2",
  ]


def test_reference_hsm_ancestor_to_descendant_order_matches_c_semantics() -> None:
  runtime = _build_runtime(mode="rtc")

  runtime.sendEvent("transition")
  runtime.sendEvent("transition")
  runtime.sendEvent("transition")
  runtime.setVariable("trace", [])

  runtime.sendEvent("transition")

  assert runtime.getState() == {"id": "s21", "label": "S21"}
  assert runtime.getVariable("trace") == [
    "s2.to_s21",
    "s21.entry",
  ]


def test_reference_hsm_child_to_parent_order_matches_c_semantics() -> None:
  runtime = _build_runtime(mode="rtc")

  for _ in range(5):
    runtime.sendEvent("transition")
  runtime.setVariable("trace", [])

  runtime.sendEvent("transition")

  assert runtime.getState() == {"id": "s3", "label": "S3"}
  assert runtime.getVariable("trace") == [
    "s31.exit",
    "s31.to_s3",
  ]


def test_reference_hsm_guard_true_branch_is_real_self_transition() -> None:
  runtime = _build_runtime(mode="rtc")

  for _ in range(8):
    runtime.sendEvent("transition")
  runtime.setVariable("trace", [])
  runtime.setVariable("self_transition", True)

  runtime.sendEvent("transition")

  assert runtime.getState() == {"id": "s41", "label": "S41"}
  assert runtime.getVariable("trace") == [
    "guard.self_transition",
    "s41.exit",
    "guard.true_branch",
    "s41.entry",
  ]


def test_reference_hsm_step_mode_reaches_same_initial_and_first_event_states() -> None:
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
