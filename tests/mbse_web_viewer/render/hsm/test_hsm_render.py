from __future__ import annotations

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


def test_hsm_svg_exposes_lifecycle_and_transition_text_targets() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)

  rendered = HsmRender()
  rendered.render(model)

  assert rendered.getLifecycleSectionTextIds("s4", "on_initial")
  assert rendered.getLifecycleActivityTextIds(
    "s4",
    "on_initial",
    {"module": "tests.reference_model.hsm.reference_hsm_callables", "name": "s4_initial"},
  )
  assert rendered.getExternalTransitionLabelTextIds(
    "external_transition_s1_transition_to_s211"
  )
  assert rendered.getExternalTransitionActivityTextIds(
    "external_transition_s1_transition_to_s211",
    {"module": "tests.reference_model.hsm.reference_hsm_callables", "name": "s1_to_s211"},
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
    {"module": "tests.reference_model.hsm.reference_hsm_callables", "name": "trace_ping_value"},
  )
