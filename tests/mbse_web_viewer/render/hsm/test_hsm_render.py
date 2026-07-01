from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from mbse.model.hsm.hsm_model import HsmModel
from mbse_web_viewer.render.hsm.hsm_render import HsmRender


FIXTURE_PATH = (
  Path(__file__).resolve().parents[3] / "reference_model" / "hsm" / "reference_hsm_model.json"
)


def test_hsm_svg_renders_reference_model_with_expected_highlight_ids() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)

  rendered = HsmRender()
  rendered.render(model)

  assert (
    rendered.getSvgText().lstrip().startswith("<?xml")
    or "<svg" in rendered.getSvgText()
  )
  assert rendered.getStateId("s41") == "state_s41"
  assert rendered.getRootInitialTransitionId() == "root_initial_transition_to_s1"
  assert rendered.getInitialTransitionId("s4") == "initial_transition_s4_to_s41"
  assert rendered.getExternalTransitionIds("s1", "transition", "s211") == (
    "external_transition_s1_transition_to_s211",
  )
  assert rendered.getGuardedTransitionIds("s41", "choose_transition") == (
    "guarded_transition_s41_choose_transition",
  )
  assert rendered.getGuardNodeIds("s41", "choose_transition") == (
    "guard_node_s41_choose_transition",
  )
  assert rendered.getGuardBranchIds(
    "s41",
    "choose_transition",
    outcome=False,
    target_state_id="s4",
  ) == ("guard_branch_s41_choose_transition_false_to_s4",)
  assert "id=\"state_s41\"" in rendered.getSvgText()
  assert "id=\"external_transition_s1_transition_to_s211\"" in rendered.getSvgText()


def test_hsm_svg_exposes_state_hook_and_transition_text_targets() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)

  rendered = HsmRender()
  rendered.render(model)

  assert rendered.getInitialTransitionLabelTextIds(
    rendered.getInitialTransitionId("s4")
  )
  assert rendered.getInitialTransitionActivityTextIds(
    rendered.getInitialTransitionId("s4"),
    { "kind": "action_language", "module": "tests.reference_model.hsm.reference_hsm_executables", "name": "s4_initial"},
  )
  assert rendered.getExternalTransitionLabelTextIds(
    "external_transition_s1_transition_to_s211"
  )
  assert rendered.getExternalTransitionActivityTextIds(
    "external_transition_s1_transition_to_s211",
    { "kind": "action_language", "module": "tests.reference_model.hsm.reference_hsm_executables", "name": "s1_to_s211"},
  )


def test_hsm_svg_exposes_internal_transition_highlight_mapping() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)

  rendered = HsmRender()
  rendered.render(model)

  assert rendered.getInternalTransitionIds("s1", "ping") == (
    "internal_transition_s1_ping",
  )
  assert rendered.getInternalTransitionIds("s2", "ping") == (
    "internal_transition_s2_ping",
  )
  assert rendered.getInternalTransitionIds("s3", "ping") == (
    "internal_transition_s3_ping",
  )
  assert rendered.getInternalTransitionIds("s41", "ping") == (
    "internal_transition_s41_ping",
  )
  assert rendered.getInternalTransitionIds("s211", "ping") == (
    "internal_transition_s211_ping",
  )
  assert rendered.getInternalTransitionSectionTextIds("s41", "ping")
  assert rendered.getInternalTransitionEventTextIds(
    "internal_transition_s41_ping"
  )
  assert rendered.getInternalTransitionActivityTextIds(
    "internal_transition_s41_ping",
    { "kind": "action_language", "module": "tests.reference_model.hsm.reference_hsm_executables", "name": "trace_ping_value"},
  )


def test_hsm_svg_exposes_model_executable_text_targets() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)
  document = deepcopy(model.document)
  document["states"][0]["initial_transition"]["activities"] = [
    {"kind": "model", "model_id": "child_activity"}
  ]
  model = HsmModel(document)

  rendered = HsmRender()
  rendered.render(model)

  assert rendered.getInitialTransitionActivityTextIds(
    rendered.getInitialTransitionId("s1"),
    {"kind": "model", "model_id": "child_activity"},
  )


def test_hsm_svg_exposes_complete_visual_ownership_ids() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)

  rendered = HsmRender()
  rendered.render(model)

  initial_id = rendered.getInitialTransitionId("s4")
  initial_owned_ids = set(rendered.getInitialTransitionOwnedIds("s4"))
  initial_activity_ids = set(rendered.getInitialTransitionActivityTextIds(
    initial_id,
    {
      "kind": "action_language",
      "module": "tests.reference_model.hsm.reference_hsm_executables",
      "name": "s4_initial",
    },
  ))
  assert initial_id in initial_owned_ids
  assert rendered.getInitialTransitionSourceId("s4") in initial_owned_ids
  assert set(rendered.getInitialTransitionLabelTextIds(initial_id)).issubset(
    initial_owned_ids
  )
  assert initial_activity_ids.issubset(initial_owned_ids)
  for activity_id in initial_activity_ids:
    assert initial_owned_ids.issubset(rendered.getOwnedIdsForHighlightId(activity_id))

  state_owned_ids = set(rendered.getStateOwnedIds("s41"))
  assert rendered.getStateId("s41") in state_owned_ids
  assert set(rendered.getStateLabelTextIds("s41")).issubset(state_owned_ids)
  assert set(rendered.getInternalTransitionIds("s41", "ping")).issubset(state_owned_ids)
  assert set(rendered.getInternalTransitionSectionTextIds("s41", "ping")).issubset(
    state_owned_ids
  )
  assert set(rendered.getInternalTransitionEventTextIds(
    "internal_transition_s41_ping"
  )).issubset(state_owned_ids)

  transition_id = rendered.getExternalTransitionIds("s1", "transition", "s211")[0]
  transition_owned_ids = set(rendered.getExternalTransitionOwnedIds(transition_id))
  assert transition_id in transition_owned_ids
  assert set(rendered.getExternalTransitionLabelTextIds(transition_id)).issubset(
    transition_owned_ids
  )
  assert set(rendered.getExternalTransitionActivityTextIds(
    transition_id,
    {
      "kind": "action_language",
      "module": "tests.reference_model.hsm.reference_hsm_executables",
      "name": "s1_to_s211",
    },
  )).issubset(transition_owned_ids)
