from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from mbse.model.activity.activity_model import ActivityModel
from mbse_web_viewer.render.activity.activity_render import ActivityRender


FIXTURE_PATH = (
  Path(__file__).resolve().parents[3]
  / "reference_model"
  / "activity"
  / "reference_activity_model.json"
)


def test_activity_svg_renders_reference_model_with_expected_highlight_ids() -> None:
  model = ActivityModel.loadAndValidate(FIXTURE_PATH)

  rendered = ActivityRender()
  rendered.render(model)

  assert (
    rendered.getSvgText().lstrip().startswith("<?xml")
    or "<svg" in rendered.getSvgText()
  )
  assert rendered.getInitialTransitionSourceId() == "initial_source"
  assert rendered.getInitialTransitionId() == "initial_transition_to_check_full_reset"
  assert rendered.getActionId("reset_context_variables") == "action_reset_context_variables"
  assert rendered.getDecisionId("check_full_reset") == "decision_check_full_reset"
  assert rendered.getFinalId("reset_done") == "final_reset_done"
  assert rendered.getActionTransitionId("reset_context_variables") == (
    "action_transition_reset_context_variables_to_reset_done"
  )
  assert rendered.getDecisionTransitionId("check_full_reset", outcome=True) == (
    "decision_transition_check_full_reset_true_to_reset_context_variables"
  )
  assert rendered.getDecisionTransitionId("check_full_reset", outcome=False) == (
    "decision_transition_check_full_reset_false_to_reset_skipped"
  )
  assert "id=\"action_reset_context_variables\"" in rendered.getSvgText()
  assert "id=\"decision_check_full_reset\"" in rendered.getSvgText()
  assert "actions:" in rendered.getSvgText()


def test_activity_svg_exposes_text_targets() -> None:
  model = ActivityModel.loadAndValidate(FIXTURE_PATH)

  rendered = ActivityRender()
  rendered.render(model)

  assert rendered.getActionLabelTextIds("reset_context_variables")
  assert rendered.getActionExecutableTextIds(
    "reset_context_variables",
    {
      "kind": "action_language",
      "module": "tests.reference_model.activity.reference_activity_executables",
      "name": "reset_context_variables",
    },
  )
  assert rendered.getDecisionLabelTextIds("check_full_reset")
  assert rendered.getDecisionConditionTextIds(
    "check_full_reset",
    {
      "kind": "action_language",
      "module": "tests.reference_model.activity.reference_activity_executables",
      "name": "is_full_reset_requested",
    },
  )
  assert rendered.getFinalLabelTextIds("reset_done")
  assert rendered.getTransitionLabelTextIds(
    "decision_transition_check_full_reset_true_to_reset_context_variables"
  )


def test_activity_svg_exposes_model_executable_text_targets() -> None:
  model = ActivityModel.loadAndValidate(FIXTURE_PATH)
  document = deepcopy(model.document)
  document["actions"][0]["executable"] = {
    "kind": "model",
    "model_id": "child_activity",
  }
  model = ActivityModel(document)

  rendered = ActivityRender()
  rendered.render(model)

  assert rendered.getActionExecutableTextIds(
    "reset_context_variables",
    {"kind": "model", "model_id": "child_activity"},
  )


def test_activity_svg_exposes_complete_visual_ownership_ids() -> None:
  model = ActivityModel.loadAndValidate(FIXTURE_PATH)

  rendered = ActivityRender()
  rendered.render(model)

  initial_owned_ids = set(rendered.getInitialTransitionOwnedIds())
  assert rendered.getInitialTransitionId() in initial_owned_ids
  assert rendered.getInitialTransitionSourceId() in initial_owned_ids
  assert initial_owned_ids.issubset(
    rendered.getOwnedIdsForHighlightId(rendered.getInitialTransitionSourceId())
  )

  action_owned_ids = set(rendered.getActionOwnedIds("reset_context_variables"))
  action_executable_ids = set(rendered.getActionExecutableTextIds(
    "reset_context_variables",
    {
      "kind": "action_language",
      "module": "tests.reference_model.activity.reference_activity_executables",
      "name": "reset_context_variables",
    },
  ))
  assert rendered.getActionId("reset_context_variables") in action_owned_ids
  assert set(rendered.getActionLabelTextIds("reset_context_variables")).issubset(
    action_owned_ids
  )
  assert action_executable_ids.issubset(action_owned_ids)
  for executable_id in action_executable_ids:
    assert action_owned_ids.issubset(rendered.getOwnedIdsForHighlightId(executable_id))

  decision_owned_ids = set(rendered.getDecisionOwnedIds("check_full_reset"))
  decision_condition_ids = set(rendered.getDecisionConditionTextIds(
    "check_full_reset",
    {
      "kind": "action_language",
      "module": "tests.reference_model.activity.reference_activity_executables",
      "name": "is_full_reset_requested",
    },
  ))
  assert rendered.getDecisionId("check_full_reset") in decision_owned_ids
  assert set(rendered.getDecisionLabelTextIds("check_full_reset")).issubset(
    decision_owned_ids
  )
  assert decision_condition_ids.issubset(decision_owned_ids)

  final_owned_ids = set(rendered.getFinalOwnedIds("reset_done"))
  assert rendered.getFinalId("reset_done") in final_owned_ids
  assert set(rendered.getFinalLabelTextIds("reset_done")).issubset(final_owned_ids)

  transition_id = rendered.getDecisionTransitionId(
    "check_full_reset",
    outcome=True,
  )
  transition_owned_ids = set(rendered.getTransitionOwnedIds(transition_id))
  assert transition_id in transition_owned_ids
  assert set(rendered.getTransitionLabelTextIds(transition_id)).issubset(
    transition_owned_ids
  )
