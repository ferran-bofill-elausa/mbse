from __future__ import annotations

from pathlib import Path

from mbse.model.hsm.hsm_model import HsmModel
from mbse_web_viewer.render.hsm.hsm_render import HsmRender
from mbse_web_viewer.server.hsm.hsm_server import HsmViewerServerController
from mbse_web_viewer.server.hsm.hsm_server import startHsmViewerServerFromModelPath


FIXTURE_PATH = (
  Path(__file__).resolve().parents[3] / "reference_model" / "hsm" / "reference_hsm_model.json"
)


def test_hsm_server_session_exposes_initialized_runtime_state() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)
  rendered = HsmRender()
  rendered.render(model)

  controller = HsmViewerServerController(model)
  session = controller.getSession()

  assert session.document_id == "reference_hsm"
  assert session.svg_url == "/artifacts/diagram.svg"
  assert session.enums == ({"id": "transition_mode", "values": ["normal", "forced"]},)
  assert session.events == (
    {"id": "transition", "label": "Transition"},
    {
      "id": "ping",
      "label": "Ping",
      "parameters": [
        {
          "name": "value",
          "type": "signed",
          "min": -100,
          "max": 100,
        },
      ],
    },
    {
      "id": "choose_transition",
      "label": "Choose Transition",
      "parameters": [
        {
          "name": "self_transition",
          "type": "bool",
        },
      ],
    },
    {
      "id": "set_mode",
      "label": "Set Mode",
      "parameters": [
        {
          "name": "target_mode",
          "type": "enum",
          "enum_id": "transition_mode",
        },
      ],
    },
  )
  assert session.variables == (
    {
      "name": "last_ping_value",
      "type": "signed",
      "min": -100,
      "max": 100,
      "default_value": 0,
    },
    {
      "name": "current_mode",
      "type": "enum",
      "enum_id": "transition_mode",
      "default_value": "normal",
    },
  )
  assert session.variable_values == {
    "last_ping_value": 0,
    "current_mode": "normal",
  }
  assert session.state == {"id": "s11111", "label": "S11111"}
  assert session.highlight.state_ids == ("state_s11111",)
  assert "state_s11111" in session.focus.related_ids
  assert "state_s1111" in session.focus.related_ids
  assert "root_initial_transition_to_s1" in session.highlight.transition_ids
  assert set(
    rendered.getLifecycleActivityTextIds(
      "s1",
      "on_entry",
      {"module": "tests.reference_model.hsm.reference_hsm_callables", "name": "s1_entry"},
    )
  ).issubset(session.highlight.text_ids)
  assert set(
    rendered.getLifecycleActivityTextIds(
      "s1",
      "on_initial",
      {"module": "tests.reference_model.hsm.reference_hsm_callables", "name": "s1_initial"},
    )
  ).issubset(session.highlight.text_ids)
  assert len(session.execution_log) == 1
  assert session.execution_log[0]["event"]["event_id"] is None
  assert session.last_trace.event_id is None


def test_hsm_server_send_event_updates_session_and_transition_highlights() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)
  rendered = HsmRender()
  rendered.render(model)

  controller = HsmViewerServerController(model)
  session = controller.sendEvent("transition")

  assert session.state == {"id": "s2111", "label": "S2111"}
  assert session.highlight.state_ids == ("state_s2111",)
  assert "external_transition_s1_transition_to_s211" in session.highlight.transition_ids
  assert "initial_transition_s211_to_s2111" in session.highlight.transition_ids
  assert set(
    rendered.getLifecycleActivityTextIds(
      "s11111",
      "on_exit",
      {
        "module": "tests.reference_model.hsm.reference_hsm_callables",
        "name": "s11111_exit",
      },
    )
  ).issubset(session.highlight.text_ids)
  assert set(
    rendered.getLifecycleActivityTextIds(
      "s2111",
      "on_entry",
      {
        "module": "tests.reference_model.hsm.reference_hsm_callables",
        "name": "s2111_entry",
      },
    )
  ).issubset(session.highlight.text_ids)
  assert session.execution_log[-1]["event"]["event_id"] == "transition"
  assert session.execution_log[-1]["entries"] == [dict(entry) for entry in session.last_trace.entries]
  assert session.last_trace.event_id == "transition"

def test_hsm_server_highlights_guard_and_branch_texts_for_choose_transition() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)
  rendered = HsmRender()
  rendered.render(model)
  controller = HsmViewerServerController(model)

  for _ in range(8):
    controller.sendEvent("transition")

  session = controller.sendEvent(
    "choose_transition",
    {
      "self_transition": True,
    },
  )

  guard_node_ids = rendered.getGuardNodeIds("s41", "choose_transition")
  branch_edge_id = rendered.getGuardBranchIds(
    "s41",
    "choose_transition",
    outcome=True,
    target_state_id="s41",
  )[0]
  branch_activity_text_ids = rendered.getExternalTransitionActivityTextIds(
    branch_edge_id,
    {
      "module": "tests.reference_model.hsm.reference_hsm_callables",
      "name": "guard_true_branch",
    },
  )

  assert set(guard_node_ids).issubset(session.highlight.transition_ids)
  assert set(branch_activity_text_ids).issubset(session.highlight.text_ids)
  assert [entry["kind"] for entry in session.execution_log[-1]["entries"]] == [
    "guard_condition",
    "external_transition",
    "activity",
    "on_exit",
    "on_entry",
  ]


def test_hsm_server_set_variable_and_reset_refresh_session() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)

  controller = HsmViewerServerController(model)
  controller.setVariable("current_mode", "forced")
  updated = controller.getSession()
  reset = controller.reset()

  assert updated.variable_values["current_mode"] == "forced"
  assert reset.variable_values["current_mode"] == "normal"
  assert reset.state == {"id": "s11111", "label": "S11111"}


def test_hsm_server_set_mode_event_refreshes_session_variable_values() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)

  controller = HsmViewerServerController(model)
  for _ in range(8):
    controller.sendEvent("transition")

  session = controller.sendEvent("set_mode", {"target_mode": "forced"})

  assert session.state == {"id": "s41", "label": "S41"}
  assert session.variable_values["current_mode"] == "forced"
  assert session.last_trace.event_id == "set_mode"


def test_hsm_server_can_start_from_model_path() -> None:
  server = startHsmViewerServerFromModelPath(FIXTURE_PATH)

  try:
    assert server.base_url.startswith("http://127.0.0.1:")
  finally:
    server.close()
