from __future__ import annotations

from copy import deepcopy
import importlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from mbse.model.activity.activity_model import ActivityModel
from mbse.model.context.context_model import ContextModel
from mbse.runtime.activity.activity_runtime import ActivityRuntime


FIXTURE_PATH = (
  Path(__file__).resolve().parents[3]
  / "reference_model"
  / "activity"
  / "reference_activity_model.json"
)
CONTEXT_PATH = (
  Path(__file__).resolve().parents[3]
  / "reference_model"
  / "context"
  / "reference_context_model.json"
)


def _build_runtime() -> ActivityRuntime:
  model = ActivityModel.loadAndValidate(FIXTURE_PATH)
  context = ContextModel.loadAndValidate(CONTEXT_PATH)
  runtime = ActivityRuntime()
  runtime.setExecutableHandler(_execute_action_language)
  runtime.init(model, context)
  return runtime


def _execute_action_language(
  executable_ref: dict[str, Any],
  runtime: ActivityRuntime,
  _event: dict[str, Any] | None,
) -> Any:
  module = importlib.import_module(executable_ref["module"])
  handler = getattr(module, executable_ref["name"])
  ctx = SimpleNamespace(**runtime.variables)
  ctx.variables = runtime.variables

  result = handler(ctx)

  for name in runtime.variables:
    if hasattr(ctx, name):
      runtime.variables[name] = getattr(ctx, name)

  return result


def _traceKinds(runtime: ActivityRuntime) -> list[str]:
  return [entry["kind"] for entry in runtime.getExecutionLog()[0]["entries"]]


def test_activity_init_starts_paused_with_initial_step_planned() -> None:
  runtime = _build_runtime()

  assert runtime.isPaused() is True
  assert runtime.hasPendingExecution() is True
  assert runtime.getExecutionLog() == [{"entries": []}]
  assert runtime.getNextStep() == {
    "kind": "initial",
    "target_id": "check_full_reset",
    "target_label": "Check Full Reset",
    "target_type": "decision",
  }


def test_activity_play_executes_full_reset_path_to_final() -> None:
  runtime = _build_runtime()
  runtime.setVariable("full_reset_requested", True)
  runtime.setVariable("last_ping_value", 42)
  runtime.setVariable("current_mode", "forced")
  runtime.setVariable("is_ready", False)
  runtime.setVariable("output_prepared", True)

  assert runtime.play() is True

  assert runtime.hasPendingExecution() is False
  assert runtime.getVariable("last_ping_value") == 0
  assert runtime.getVariable("current_mode") == "normal"
  assert runtime.getVariable("is_ready") is True
  assert runtime.getVariable("output_prepared") is False
  assert runtime.getVariable("full_reset_requested") is False
  assert _traceKinds(runtime) == ["initial", "decision", "action", "final"]
  assert runtime.getExecutionLog()[0]["entries"][-1] == {
    "kind": "final",
    "final_id": "reset_done",
    "final_label": "Reset Done",
  }


def test_activity_partial_reset_takes_false_path_to_final() -> None:
  runtime = _build_runtime()

  assert runtime.play() is True

  assert runtime.hasPendingExecution() is False
  assert runtime.getVariable("output_prepared") is False
  assert _traceKinds(runtime) == ["initial", "decision", "final"]
  assert runtime.getExecutionLog()[0]["entries"][1] == {
    "kind": "decision",
    "decision_id": "check_full_reset",
    "decision_label": "Check Full Reset",
    "condition": {
      "kind": "action_language",
      "module": "tests.reference_model.activity.reference_activity_executables",
      "name": "is_full_reset_requested",
    },
    "result": False,
    "target_id": "reset_skipped",
    "target_label": "Reset Skipped",
    "target_type": "final",
  }


def test_activity_action_executable_resets_runtime_variables() -> None:
  runtime = _build_runtime()
  runtime.setVariable("full_reset_requested", True)
  runtime.setVariable("last_ping_value", 42)
  runtime.setVariable("current_mode", "forced")
  runtime.setVariable("is_ready", False)
  runtime.setVariable("output_prepared", True)

  runtime.play()

  assert runtime.getVariable("last_ping_value") == 0
  assert runtime.getVariable("current_mode") == "normal"
  assert runtime.getVariable("is_ready") is True
  assert runtime.getVariable("output_prepared") is False


def test_activity_decision_requires_bool_result() -> None:
  model = ActivityModel.loadAndValidate(FIXTURE_PATH)
  bad_document = deepcopy(model.document)
  bad_document["decisions"][0]["condition"] = {
    "kind": "action_language",
    "module": "tests.reference_model.activity.reference_activity_executables",
    "name": "return_not_bool",
  }
  context = ContextModel.loadAndValidate(CONTEXT_PATH)
  runtime = ActivityRuntime()
  runtime.setExecutableHandler(_execute_action_language)
  runtime.init(ActivityModel(bad_document), context)

  assert runtime.step() is True
  with pytest.raises(TypeError, match="Decision condition executable must return a bool"):
    runtime.step()


def test_activity_step_advances_step_by_step() -> None:
  runtime = _build_runtime()

  assert runtime.step() is True
  assert _traceKinds(runtime) == ["initial"]
  assert runtime.getNextStep() == {
    "kind": "pending_decision",
    "decision_id": "check_full_reset",
    "decision_label": "Check Full Reset",
    "condition": {
      "kind": "action_language",
      "module": "tests.reference_model.activity.reference_activity_executables",
      "name": "is_full_reset_requested",
    },
    "true_target_id": "reset_context_variables",
    "true_target_label": "Reset Context Variables",
    "true_target_type": "action",
    "false_target_id": "reset_skipped",
    "false_target_label": "Reset Skipped",
    "false_target_type": "final",
    "true_branch": [
      {
        "kind": "action",
        "action_id": "reset_context_variables",
        "action_label": "Reset Context Variables",
        "executable": {
          "kind": "action_language",
          "module": "tests.reference_model.activity.reference_activity_executables",
          "name": "reset_context_variables",
        },
        "target_id": "reset_done",
        "target_label": "Reset Done",
        "target_type": "final",
      },
      {
        "kind": "final",
        "final_id": "reset_done",
        "final_label": "Reset Done",
      },
    ],
    "false_branch": [
      {
        "kind": "final",
        "final_id": "reset_skipped",
        "final_label": "Reset Skipped",
      }
    ],
  }

  assert runtime.step() is True
  assert _traceKinds(runtime) == ["initial", "decision"]
  assert runtime.getNextStep()["kind"] == "final"
  assert runtime.getVariable("output_prepared") is False

  assert runtime.step() is True
  assert _traceKinds(runtime) == ["initial", "decision", "final"]
  assert runtime.hasPendingExecution() is False

  assert runtime.step() is False


def test_activity_execution_log_contains_expected_sequence() -> None:
  runtime = _build_runtime()
  runtime.setVariable("full_reset_requested", True)

  runtime.play()

  assert runtime.getExecutionLog() == [
    {
      "entries": [
        {
          "kind": "initial",
          "target_id": "check_full_reset",
          "target_label": "Check Full Reset",
          "target_type": "decision",
        },
        {
          "kind": "decision",
          "decision_id": "check_full_reset",
          "decision_label": "Check Full Reset",
          "condition": {
            "kind": "action_language",
            "module": "tests.reference_model.activity.reference_activity_executables",
            "name": "is_full_reset_requested",
          },
          "result": True,
          "target_id": "reset_context_variables",
          "target_label": "Reset Context Variables",
          "target_type": "action",
        },
        {
          "kind": "action",
          "action_id": "reset_context_variables",
          "action_label": "Reset Context Variables",
          "executable": {
            "kind": "action_language",
            "module": "tests.reference_model.activity.reference_activity_executables",
            "name": "reset_context_variables",
          },
          "target_id": "reset_done",
          "target_label": "Reset Done",
          "target_type": "final",
        },
        {
          "kind": "final",
          "final_id": "reset_done",
          "final_label": "Reset Done",
        },
      ]
    }
  ]
