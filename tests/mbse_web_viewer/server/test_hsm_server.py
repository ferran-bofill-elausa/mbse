from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request
from urllib.request import urlopen

from mbse.model.activity.activity_model import ActivityModel
from mbse.model.context.context_model import ContextModel
from mbse.model.hsm.hsm_model import HsmModel
from mbse.model.project.project_registry import ProjectRegistry
from mbse_web_viewer.render.activity.activity_render import ActivityRender
from mbse_web_viewer.render.hsm.hsm_render import HsmRender
from mbse_web_viewer.server.controller import HsmModelViewerController
from mbse_web_viewer.server.controller import ProjectViewerController
from mbse_web_viewer.server.viewer_app import startProjectViewerServerFromProjectPath


FIXTURE_PATH = (
  Path(__file__).resolve().parents[2] / "reference_model" / "hsm" / "reference_hsm_model.json"
)
CONTEXT_PATH = (
  Path(__file__).resolve().parents[2]
  / "reference_model"
  / "context"
  / "reference_context_model.json"
)
REFERENCE_PROJECT_PATH = (
  Path(__file__).resolve().parents[2]
  / "reference_model"
  / "project"
  / "reference_project.json"
)


def _load_context() -> ContextModel:
  return ContextModel.loadAndValidate(CONTEXT_PATH)


def _build_running_controller(model: HsmModel) -> HsmModelViewerController:
  controller = HsmModelViewerController(model, _load_context())
  controller.play()
  return controller


def _post_json(base_url: str, path: str, payload: dict[str, object]) -> dict[str, object]:
  request = Request(
    f"{base_url}{path}",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
  )
  with urlopen(request) as response:
    return json.loads(response.read().decode("utf-8"))


def _get_json(base_url: str, path: str) -> dict[str, object]:
  with urlopen(f"{base_url}{path}") as response:
    return json.loads(response.read().decode("utf-8"))


def _build_reference_project_viewer_at_s41() -> ProjectViewerController:
  controller = ProjectViewerController(ProjectRegistry.load(REFERENCE_PROJECT_PATH))
  controller.play()
  for _ in range(8):
    controller.sendEvent("transition")
  return controller


def test_hsm_server_session_exposes_paused_init_preview() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)
  rendered = HsmRender()
  rendered.render(model)

  controller = HsmModelViewerController(model, _load_context())
  session = controller.getSession()

  assert session.active_model_id == "reference_hsm"
  assert session.models == (
    {
      "model_id": "reference_hsm",
      "kind": "hsm",
      "svg_url": "/artifacts/models/reference_hsm/diagram.svg",
      "is_entrypoint": True,
    },
  )
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
    {
      "id": "reset_model",
      "label": "Reset Model",
      "parameters": [
        {
          "name": "full_reset",
          "type": "bool",
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
    {
      "name": "is_ready",
      "type": "bool",
      "default_value": True,
    },
    {
      "name": "output_prepared",
      "type": "bool",
      "default_value": False,
    },
    {
      "name": "full_reset_requested",
      "type": "bool",
      "default_value": False,
    },
  )
  assert session.variable_values == {
    "last_ping_value": 0,
    "current_mode": "normal",
    "is_ready": True,
    "output_prepared": False,
    "full_reset_requested": False,
  }
  assert session.debugger == {
    "is_paused": True,
    "current_event": {"event_id": None, "parameters": {}},
    "queued_events": [],
    "event_history": [],
    "has_pending_execution": True,
    "can_step": True,
  }
  assert session.state == {"id": None, "label": None}
  assert session.highlight.state_ids == (rendered.getRootInitialTransitionSourceId(),)
  assert session.highlight.transition_ids == (rendered.getRootInitialTransitionId(),)
  assert session.highlight.current_transition_ids == ()
  assert set(session.highlight.current_text_ids) == set(
    rendered.getStateHookSectionTextIds("s1", "on_entry")
    + rendered.getStateHookActivityTextIds(
      "s1",
      "on_entry",
      {
        "kind": "action_language",
        "module": "tests.reference_model.hsm.reference_hsm_executables",
        "name": "s1_entry",
      },
    )
  )
  assert rendered.getStateId("s1") in session.focus.state_related_ids
  assert set(rendered.getInitialTransitionOwnedIds(None)).issubset(
    session.focus.state_related_ids
  )
  assert set(session.highlight.transition_ids).issubset(session.focus.trace_related_ids)
  assert set(session.highlight.current_text_ids).issubset(session.focus.trace_related_ids)
  assert session.focus.state_viewport_focus_ids == (rendered.getRootInitialTransitionSourceId(),)
  assert set(session.focus.trace_viewport_focus_ids) == set(session.highlight.current_text_ids)
  assert len(session.execution_log) == 1
  assert session.execution_log[0]["event"]["event_id"] is None
  assert [entry["kind"] for entry in session.execution_log[0]["entries"]] == [
    "initial_transition",
  ]
  assert session.last_trace.event_id is None


def test_hsm_server_root_initial_active_state_change_applies_on_step() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)
  rendered = HsmRender()
  rendered.render(model)

  controller = HsmModelViewerController(model, _load_context())

  for _ in range(20):
    session = controller.getSession()
    next_step = controller._getNextStep()
    if (
      next_step is not None
      and next_step["kind"] == "on_entry"
      and next_step["source_state_id"] == "s11111"
    ):
      break
    controller.stepInto()
  else:
    raise AssertionError("final root on-entry step was not reached")

  assert session.state == {"id": None, "label": None}
  assert session.highlight.state_ids == (rendered.getRootInitialTransitionSourceId(),)
  assert session.highlight.current_transition_ids == ()
  assert set(
    rendered.getStateHookActivityTextIds(
      "s11111",
      "on_entry",
      {
        "kind": "action_language",
        "module": "tests.reference_model.hsm.reference_hsm_executables",
        "name": "s11111_entry",
      },
    )
  ).issubset(session.highlight.current_text_ids)

  committed = controller.stepInto()

  assert committed.state == {"id": "s11111", "label": "S11111"}
  assert committed.debugger["has_pending_execution"] is False
  assert committed.debugger["can_step"] is False
  assert committed.highlight.state_ids == (rendered.getStateId("s11111"),)
  assert committed.highlight.current_transition_ids == ()
  assert committed.highlight.current_text_ids == ()


def test_hsm_server_send_event_updates_session_and_transition_highlights() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)
  rendered = HsmRender()
  rendered.render(model)

  controller = _build_running_controller(model)
  session = controller.sendEvent("transition")

  assert session.state == {"id": "s2111", "label": "S2111"}
  assert session.highlight.state_ids == ("state_s2111",)
  assert "external_transition_s1_transition_to_s211" in session.highlight.transition_ids
  assert "initial_transition_s211_to_s2111" in session.highlight.transition_ids
  assert set(
    rendered.getStateHookActivityTextIds(
      "s11111",
      "on_exit",
      {
        "kind": "action_language",
        "module": "tests.reference_model.hsm.reference_hsm_executables",
        "name": "s11111_exit",
      },
    )
  ).issubset(session.highlight.text_ids)
  assert set(
    rendered.getStateHookActivityTextIds(
      "s2111",
      "on_entry",
      {
        "kind": "action_language",
        "module": "tests.reference_model.hsm.reference_hsm_executables",
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
  controller = _build_running_controller(model)

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
      "kind": "action_language",
      "module": "tests.reference_model.hsm.reference_hsm_executables",
      "name": "guard_true_branch",
    },
  )

  assert set(guard_node_ids).issubset(session.highlight.transition_ids)
  assert set(branch_activity_text_ids).issubset(session.highlight.text_ids)
  assert [entry["kind"] for entry in session.execution_log[-1]["entries"]] == [
    "guarded_transition",
    "guard_condition",
    "guard_branch_transition",
    "on_exit",
    "on_entry",
  ]


def test_hsm_server_set_variable_and_reset_refresh_session() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)

  controller = HsmModelViewerController(model, _load_context())
  controller.setVariable("current_mode", "forced")
  updated = controller.getSession()
  reset = controller.reset()

  assert updated.variable_values["current_mode"] == "forced"
  assert updated.changed_variable_ids == ("current_mode",)
  assert reset.variable_values["current_mode"] == "normal"
  assert reset.changed_variable_ids == ()
  assert reset.state == {"id": None, "label": None}


def test_hsm_server_set_mode_event_refreshes_session_variable_values() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)

  controller = _build_running_controller(model)
  for _ in range(8):
    controller.sendEvent("transition")

  session = controller.sendEvent("set_mode", {"target_mode": "forced"})

  assert session.state == {"id": "s41", "label": "S41"}
  assert session.variable_values["current_mode"] == "forced"
  assert session.changed_variable_ids == ("current_mode",)
  assert session.last_trace.event_id == "set_mode"


def test_hsm_server_reports_changed_variables_for_visible_flow() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)
  controller = _build_running_controller(model)

  changed = controller.sendEvent("ping", {"value": 42})

  assert changed.variable_values["last_ping_value"] == 42
  assert changed.changed_variable_ids == ("last_ping_value",)

  unchanged = controller.sendEvent("ping", {"value": 42})

  assert unchanged.variable_values["last_ping_value"] == 42
  assert unchanged.changed_variable_ids == ()


def test_hsm_server_set_variable_reports_changed_variable() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)
  controller = HsmModelViewerController(model, _load_context())

  changed = controller.setVariable("current_mode", "forced")

  assert changed.variable_values["current_mode"] == "forced"
  assert changed.changed_variable_ids == ("current_mode",)

  unchanged = controller.setVariable("current_mode", "forced")

  assert unchanged.changed_variable_ids == ()


def test_hsm_server_paused_step_flow_exposes_debug_state() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)
  rendered = HsmRender()
  rendered.render(model)

  controller = _build_running_controller(model)
  controller.pause()
  session = controller.sendEvent("transition")

  assert session.state == {"id": "s11111", "label": "S11111"}
  assert session.debugger == {
    "is_paused": True,
    "current_event": {"event_id": "transition", "parameters": {}},
    "queued_events": [],
    "event_history": [],
    "has_pending_execution": True,
    "can_step": True,
  }
  assert session.highlight.transition_ids == ()
  assert session.focus.state_viewport_focus_ids == ("state_s11111",)
  transition_id = rendered.getExternalTransitionIds("s1", "transition", "s211")[0]
  current_text_ids = rendered.getExternalTransitionActivityTextIds(
    transition_id,
    {
      "kind": "action_language",
      "module": "tests.reference_model.hsm.reference_hsm_executables",
      "name": "s1_to_s211",
    },
  )
  current_label_ids = rendered.getExternalTransitionLabelTextIds(transition_id)
  assert transition_id in session.highlight.current_transition_ids
  assert set(current_label_ids).issubset(session.highlight.current_text_ids)
  assert set(current_text_ids).issubset(session.highlight.current_text_ids)
  assert set(session.focus.trace_viewport_focus_ids) == set(session.highlight.current_transition_ids)

  session = controller.stepInto()

  current_text_ids = rendered.getStateHookActivityTextIds(
    "s11111",
    "on_exit",
    {
      "kind": "action_language",
      "module": "tests.reference_model.hsm.reference_hsm_executables",
      "name": "s11111_exit",
    },
  )
  current_label_ids = rendered.getStateHookSectionTextIds("s11111", "on_exit")
  assert set(current_text_ids).issubset(session.highlight.current_text_ids)
  assert set(current_label_ids).issubset(session.highlight.current_text_ids)
  assert set(session.focus.trace_viewport_focus_ids) == set(session.highlight.current_text_ids)
  assert session.state == {"id": "s11111", "label": "S11111"}


def test_hsm_server_step_highlights_guard_branch_immediately_after_guard() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)
  rendered = HsmRender()
  rendered.render(model)

  controller = _build_running_controller(model)
  for _ in range(8):
    controller.sendEvent("transition")

  controller.pause()
  planned = controller.sendEvent("choose_transition", {"self_transition": True})

  assert rendered.getGuardedTransitionIds(
    "s41",
    "choose_transition",
  )[0] in planned.highlight.transition_ids
  assert planned.highlight.current_transition_ids == rendered.getGuardNodeIds(
    "s41",
    "choose_transition",
  )

  session = controller.stepInto()

  branch_edge_id = rendered.getGuardBranchIds(
    "s41",
    "choose_transition",
    outcome=True,
    target_state_id="s41",
  )[0]
  assert controller._getNextStep()["kind"] == "guard_branch_transition"
  assert session.highlight.current_transition_ids == (branch_edge_id,)
  assert set(
    rendered.getExternalTransitionActivityTextIds(
      branch_edge_id,
      {
        "kind": "action_language",
        "module": "tests.reference_model.hsm.reference_hsm_executables",
        "name": "guard_true_branch",
      },
    )
  ).issubset(session.highlight.current_text_ids)


def test_hsm_server_play_drains_pending_work_and_queue() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)
  controller = _build_running_controller(model)

  controller.pause()
  controller.sendEvent("transition")
  queued = controller.sendEvent("transition")

  assert queued.debugger["queued_events"] == [
    {"event_id": "transition", "parameters": {}},
  ]
  assert queued.debugger["current_event"] == {"event_id": "transition", "parameters": {}}

  session = controller.play()

  assert session.debugger == {
    "is_paused": False,
    "current_event": None,
    "queued_events": [],
    "event_history": [
      {"event_id": "transition", "parameters": {}},
      {"event_id": "transition", "parameters": {}},
    ],
    "has_pending_execution": False,
    "can_step": False,
  }
  assert session.state == {"id": "s2112", "label": "S2112"}


def test_hsm_server_pause_preserves_queued_work_until_play() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)
  controller = _build_running_controller(model)

  controller.pause()
  controller.sendEvent("transition")

  session = controller.getSession()

  assert session.debugger == {
    "is_paused": True,
    "current_event": {"event_id": "transition", "parameters": {}},
    "queued_events": [],
    "event_history": [],
    "has_pending_execution": True,
    "can_step": True,
  }
  assert session.state == {"id": "s11111", "label": "S11111"}


def test_hsm_server_step_highlights_hook_section_and_activity_together() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)
  rendered = HsmRender()
  rendered.render(model)

  controller = _build_running_controller(model)
  controller.pause()
  controller.sendEvent("transition")

  while True:
    session = controller.stepInto()
    current_ids = set(session.highlight.current_text_ids)
    if not current_ids:
      continue
    section_ids = set(rendered.getStateHookSectionTextIds("s11111", "on_exit"))
    activity_ids = set(
      rendered.getStateHookActivityTextIds(
        "s11111",
        "on_exit",
        {
          "kind": "action_language",
          "module": "tests.reference_model.hsm.reference_hsm_executables",
          "name": "s11111_exit",
        },
      )
    )
    if activity_ids.issubset(current_ids):
      assert section_ids.issubset(current_ids)
      break


def test_hsm_server_trace_focus_keeps_full_owner_state_for_pending_hook() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)
  rendered = HsmRender()
  rendered.render(model)

  controller = _build_running_controller(model)
  controller.pause()
  controller.sendEvent("transition")

  while True:
    session = controller.stepInto()
    current_ids = set(session.highlight.current_text_ids)
    current_activity_ids = set(
      rendered.getStateHookActivityTextIds(
        "s1111",
        "on_exit",
        {
          "kind": "action_language",
          "module": "tests.reference_model.hsm.reference_hsm_executables",
          "name": "s1111_exit",
        },
      )
    )
    if not current_activity_ids.issubset(current_ids):
      continue

    owner_ids = {
      rendered.getStateId("s1111"),
      *rendered.getStateHookSectionTextIds("s1111", "on_entry"),
      *rendered.getStateHookSectionTextIds("s1111", "on_exit"),
      *rendered.getStateHookActivityTextIds(
        "s1111",
        "on_entry",
        {
          "kind": "action_language",
          "module": "tests.reference_model.hsm.reference_hsm_executables",
          "name": "s1111_entry",
        },
      ),
      *rendered.getStateHookActivityTextIds(
        "s1111",
        "on_exit",
        {
          "kind": "action_language",
          "module": "tests.reference_model.hsm.reference_hsm_executables",
          "name": "s1111_exit",
        },
      ),
    }
    assert owner_ids.issubset(session.focus.trace_related_ids)
    break


def test_hsm_server_state_focus_keeps_full_owner_state_for_pending_hook() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)
  rendered = HsmRender()
  rendered.render(model)

  controller = _build_running_controller(model)
  controller.pause()
  controller.sendEvent("transition")

  while True:
    session = controller.stepInto()
    current_ids = set(session.highlight.current_text_ids)
    current_activity_ids = set(
      rendered.getStateHookActivityTextIds(
        "s2111",
        "on_entry",
        {
          "kind": "action_language",
          "module": "tests.reference_model.hsm.reference_hsm_executables",
          "name": "s2111_entry",
        },
      )
    )
    if not current_activity_ids.issubset(current_ids):
      continue

    owner_ids = {
      rendered.getStateId("s2111"),
      *rendered.getStateLabelTextIds("s2111"),
      *rendered.getStateHookSectionTextIds("s2111", "on_entry"),
      *rendered.getStateHookActivityTextIds(
        "s2111",
        "on_entry",
        {
          "kind": "action_language",
          "module": "tests.reference_model.hsm.reference_hsm_executables",
          "name": "s2111_entry",
        },
      ),
    }
    assert owner_ids.issubset(session.focus.state_related_ids)
    break


def test_hsm_server_enqueue_while_paused_keeps_current_step_highlight() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)

  controller = _build_running_controller(model)
  controller.pause()
  controller.sendEvent("transition")

  current_step_session = None
  while True:
    session = controller.stepInto()
    if session.highlight.current_text_ids:
      current_step_session = session
      break

  queued_session = controller.sendEvent("transition")

  assert current_step_session is not None
  assert queued_session.highlight.current_transition_ids == current_step_session.highlight.current_transition_ids
  assert queued_session.highlight.current_text_ids == current_step_session.highlight.current_text_ids
  assert queued_session.debugger["queued_events"] == [{"event_id": "transition", "parameters": {}}]


def test_hsm_server_paused_queue_exposes_boundary_then_next_event_step() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)
  rendered = HsmRender()
  rendered.render(model)

  controller = _build_running_controller(model)
  controller.pause()
  controller.sendEvent("transition")
  controller.sendEvent("transition")

  while True:
    session = controller.getSession()
    next_step = controller._getNextStep()
    if (
      next_step is not None
      and next_step["kind"] == "on_entry"
      and next_step["source_state_id"] == "s2111"
    ):
      break
    controller.stepInto()

  assert session.state == {"id": "s11111", "label": "S11111"}
  assert session.highlight.state_ids == (rendered.getStateId("s11111"),)
  assert session.highlight.current_transition_ids == ()
  assert set(
    rendered.getStateHookActivityTextIds(
      "s2111",
      "on_entry",
      {
        "kind": "action_language",
        "module": "tests.reference_model.hsm.reference_hsm_executables",
        "name": "s2111_entry",
      },
    )
  ).issubset(session.highlight.current_text_ids)

  committed = controller.stepInto()

  assert committed.state == {"id": "s2111", "label": "S2111"}
  assert committed.debugger["has_pending_execution"] is False
  assert committed.debugger["queued_events"] == [{"event_id": "transition", "parameters": {}}]
  assert committed.highlight.state_ids == (rendered.getStateId("s2111"),)
  assert committed.highlight.current_transition_ids == ()
  assert committed.highlight.current_text_ids == ()

  planned = controller.stepInto()

  assert planned.state == {"id": "s2111", "label": "S2111"}
  assert planned.debugger["has_pending_execution"] is True
  assert planned.debugger["queued_events"] == []
  next_transition_id = rendered.getExternalTransitionIds("s2111", "transition", "s2112")[0]
  assert planned.highlight.current_transition_ids == (next_transition_id,)
  assert set(rendered.getExternalTransitionLabelTextIds(next_transition_id)).issubset(
    planned.highlight.current_text_ids
  )
  assert set(
    rendered.getExternalTransitionActivityTextIds(
      next_transition_id,
      {
        "kind": "action_language",
        "module": "tests.reference_model.hsm.reference_hsm_executables",
        "name": "s2111_to_s2112",
      },
    )
  ).issubset(planned.highlight.current_text_ids)


def test_hsm_server_focus_related_ids_include_current_highlights() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)
  controller = _build_running_controller(model)

  play_session = controller.sendEvent("transition")
  assert _highlightIds(play_session).issubset(play_session.focus.state_related_ids)
  assert _highlightIds(play_session).issubset(play_session.focus.trace_related_ids)

  controller = _build_running_controller(model)
  controller.pause()
  controller.sendEvent("transition")
  while True:
    step_session = controller.stepInto()
    assert _highlightIds(step_session).issubset(step_session.focus.state_related_ids)
    assert _highlightIds(step_session).issubset(step_session.focus.trace_related_ids)
    if not step_session.debugger["has_pending_execution"] and not step_session.debugger["queued_events"]:
      break


def test_hsm_server_state_focus_includes_state_label_and_current_state_context() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)
  rendered = HsmRender()
  rendered.render(model)
  controller = _build_running_controller(model)

  session = controller.sendEvent("transition")

  assert session.state == {"id": "s2111", "label": "S2111"}
  assert set(rendered.getStateLabelTextIds("s2111")).issubset(
    session.focus.state_related_ids
  )
  assert set(rendered.getStateLabelTextIds("s211")).issubset(
    session.focus.state_related_ids
  )
  assert set(rendered.getStateLabelTextIds("s2")).issubset(
    session.focus.state_related_ids
  )
  next_transition_id = rendered.getExternalTransitionIds(
    "s2111",
    "transition",
    "s2112",
  )[0]
  assert next_transition_id in session.focus.state_related_ids
  assert next_transition_id not in session.focus.trace_related_ids


def test_hsm_server_exposes_and_toggles_breakpoint_targets() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)
  controller = HsmModelViewerController(model, _load_context())
  breakpoint_id = (
    "on_entry|s2111|tests.reference_model.hsm.reference_hsm_executables.s2111_entry"
  )

  session = controller.getSession()

  assert any(
    target.id == breakpoint_id and target.is_set is False and target.enabled is False
    for target in session.breakpoints
  )

  toggled = controller.toggleBreakpoint(breakpoint_id)

  assert any(
    target.id == breakpoint_id and target.is_set is True and target.enabled is True
    for target in toggled.breakpoints
  )


def test_hsm_server_play_stops_before_active_breakpoint() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)
  rendered = HsmRender()
  rendered.render(model)
  controller = _build_running_controller(model)
  breakpoint_id = (
    "on_entry|s2111|tests.reference_model.hsm.reference_hsm_executables.s2111_entry"
  )
  controller.toggleBreakpoint(breakpoint_id)

  stopped = controller.sendEvent("transition")

  assert stopped.debugger["is_paused"] is True
  assert stopped.debugger["has_pending_execution"] is True
  assert stopped.state == {"id": "s11111", "label": "S11111"}
  assert set(
    rendered.getStateHookActivityTextIds(
      "s2111",
      "on_entry",
      {
        "kind": "action_language",
        "module": "tests.reference_model.hsm.reference_hsm_executables",
        "name": "s2111_entry",
      },
    )
  ).issubset(stopped.highlight.current_text_ids)

  continued = controller.play()

  assert continued.debugger["is_paused"] is False
  assert continued.debugger["has_pending_execution"] is False
  assert continued.state == {"id": "s2111", "label": "S2111"}


def test_hsm_server_disabled_breakpoint_does_not_stop_play() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)
  controller = _build_running_controller(model)
  breakpoint_id = (
    "on_entry|s2111|tests.reference_model.hsm.reference_hsm_executables.s2111_entry"
  )
  controller.toggleBreakpoint(breakpoint_id)
  disabled = controller.setBreakpointEnabled(breakpoint_id, False)

  assert any(
    target.id == breakpoint_id and target.is_set is True and target.enabled is False
    for target in disabled.breakpoints
  )

  session = controller.sendEvent("transition")

  assert session.debugger["is_paused"] is False
  assert session.debugger["has_pending_execution"] is False
  assert session.state == {"id": "s2111", "label": "S2111"}


def test_hsm_server_persists_custom_breakpoint_order() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)
  controller = HsmModelViewerController(model, _load_context())
  breakpoint_ids = [
    "on_entry|s2111|tests.reference_model.hsm.reference_hsm_executables.s2111_entry",
    "on_exit|s11111|tests.reference_model.hsm.reference_hsm_executables.s11111_exit",
    "change_active_state|s41",
  ]

  for breakpoint_id in breakpoint_ids:
    controller.toggleBreakpoint(breakpoint_id)

  reordered_ids = [breakpoint_ids[2], breakpoint_ids[0], breakpoint_ids[1]]
  reordered = controller.reorderBreakpoints(reordered_ids)

  assert [
    target.id
    for target in reordered.breakpoints
    if target.is_set
  ] == reordered_ids

  reset = controller.reset()

  assert [
    target.id
    for target in reset.breakpoints
    if target.is_set
  ] == reordered_ids

  appended = controller.toggleBreakpoint(
    "on_entry|s1|tests.reference_model.hsm.reference_hsm_executables.s1_entry"
  )

  assert [
    target.id
    for target in appended.breakpoints
    if target.is_set
  ] == [
    *reordered_ids,
    "on_entry|s1|tests.reference_model.hsm.reference_hsm_executables.s1_entry",
  ]


def test_hsm_server_step_and_play_match_final_trace_focus() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)

  play_controller = _build_running_controller(model)
  play_session = play_controller.sendEvent("transition")

  step_controller = _build_running_controller(model)
  step_controller.pause()
  step_session = step_controller.sendEvent("transition")
  while step_session.debugger["has_pending_execution"] or step_session.debugger["queued_events"]:
    step_session = step_controller.stepInto()

  assert play_session.state == step_session.state
  assert play_session.highlight.state_ids == step_session.highlight.state_ids
  assert play_session.highlight.transition_ids == step_session.highlight.transition_ids
  assert play_session.highlight.text_ids == step_session.highlight.text_ids
  assert play_session.focus.trace_related_ids == step_session.focus.trace_related_ids


def test_hsm_project_server_executes_reference_reset_activity_and_serves_model_svgs() -> None:
  controller = _build_reference_project_viewer_at_s41()

  assert "id=\"state_s41\"" in controller.getModelSvgText("reference_hsm")
  assert "id=\"action_reset_context_variables\"" in controller.getModelSvgText("reference_activity")

  controller.setVariable("last_ping_value", 42)
  controller.setVariable("current_mode", "forced")
  controller.setVariable("is_ready", False)
  controller.setVariable("output_prepared", True)
  session = controller.sendEvent("reset_model", {"full_reset": True})

  assert session.active_model_id == "reference_hsm"
  assert session.models == (
    {
      "model_id": "reference_activity",
      "kind": "activity",
      "svg_url": "/artifacts/models/reference_activity/diagram.svg",
      "is_entrypoint": False,
    },
    {
      "model_id": "reference_hsm",
      "kind": "hsm",
      "svg_url": "/artifacts/models/reference_hsm/diagram.svg",
      "is_entrypoint": True,
    },
  )
  assert session.variable_values["last_ping_value"] == 0
  assert session.variable_values["current_mode"] == "normal"
  assert session.variable_values["is_ready"] is True
  assert session.variable_values["output_prepared"] is False
  assert session.variable_values["full_reset_requested"] is False
  assert session.state == {"id": "s11111", "label": "S11111"}
  assert all("event" in trace for trace in session.execution_log)


def test_hsm_project_server_step_into_and_out_switch_active_model() -> None:
  controller = _build_reference_project_viewer_at_s41()
  rendered = HsmRender()
  rendered.render(HsmModel.loadAndValidate(FIXTURE_PATH))
  activity_rendered = ActivityRender()
  activity_rendered.render(
    ActivityModel.loadAndValidate(
      Path(__file__).resolve().parents[2]
      / "reference_model"
      / "activity"
      / "reference_activity_model.json"
    )
  )

  controller.pause()
  controller.sendEvent("reset_model", {"full_reset": True})
  controller.stepInto()

  stepped_in = controller.stepInto()
  assert stepped_in.active_model_id == "reference_activity"
  assert set(
    rendered.getExternalTransitionActivityTextIds(
      rendered.getExternalTransitionIds("s41", "reset_model", "s1")[0],
      {"kind": "model", "model_id": "reference_activity"},
    )
  ).issubset(stepped_in.highlight.current_text_ids)
  assert set(
    (
      activity_rendered.getInitialTransitionId(),
      activity_rendered.getInitialTransitionSourceId(),
    )
  ).issubset(stepped_in.highlights_by_model["reference_activity"].current_transition_ids)

  activity_step = controller.stepInto()
  assert set(
    activity_rendered.getDecisionLabelTextIds("check_full_reset")
    + activity_rendered.getDecisionConditionTextIds(
      "check_full_reset",
      {
        "kind": "action_language",
        "module": "tests.reference_model.activity.reference_activity_executables",
        "name": "is_full_reset_requested",
      },
    )
  ).issubset(activity_step.highlights_by_model["reference_activity"].current_text_ids)

  stepped_out = controller.stepOut()
  assert stepped_out.active_model_id == "reference_hsm"
  assert stepped_out.variable_values["full_reset_requested"] is False


def test_hsm_project_server_step_over_keeps_parent_active_model() -> None:
  controller = _build_reference_project_viewer_at_s41()

  controller.pause()
  controller.sendEvent("reset_model", {"full_reset": True})
  controller.stepInto()

  session = controller.stepOver()

  assert session.active_model_id == "reference_hsm"
  assert session.variable_values["full_reset_requested"] is False


def test_hsm_project_server_activity_breakpoints_are_executable_targets_only() -> None:
  controller = _build_reference_project_viewer_at_s41()

  session = controller.getSession()
  activity_targets = {
    target.id: target
    for target in session.breakpoints
    if target.model_id == "reference_activity"
  }

  assert set(activity_targets) == {
    (
      "activity_decision|reference_activity|check_full_reset|"
      "tests.reference_model.activity.reference_activity_executables.is_full_reset_requested"
    ),
    (
      "activity_action|reference_activity|reset_context_variables|"
      "tests.reference_model.activity.reference_activity_executables.reset_context_variables"
    ),
    "activity_final|reference_activity|reset_done",
    "activity_final|reference_activity|reset_skipped",
  }
  assert all(target.model_id == "reference_activity" for target in activity_targets.values())


def test_hsm_project_server_activity_breakpoint_stops_at_decision_condition() -> None:
  controller = _build_reference_project_viewer_at_s41()
  controller.toggleBreakpoint(
    "activity_decision|reference_activity|check_full_reset|"
    "tests.reference_model.activity.reference_activity_executables.is_full_reset_requested"
  )

  session = controller.sendEvent("reset_model", {"full_reset": True})

  assert session.active_model_id == "reference_activity"
  assert set(session.highlights_by_model["reference_activity"].current_text_ids)


def test_hsm_project_server_running_event_stops_at_first_reset_breakpoint() -> None:
  controller = _build_reference_project_viewer_at_s41()
  rendered = HsmRender()
  rendered.render(HsmModel.loadAndValidate(FIXTURE_PATH))
  first_breakpoint_id = (
    "external_transition|s41|reset_model|s1|"
    "tests.reference_model.hsm.reference_hsm_executables.capture_reset_request"
  )
  second_breakpoint_id = "external_transition|s41|reset_model|s1|reference_activity"
  controller.toggleBreakpoint(first_breakpoint_id)
  controller.toggleBreakpoint(second_breakpoint_id)

  session = controller.sendEvent("reset_model", {"full_reset": True})

  assert set(
    rendered.getExternalTransitionActivityTextIds(
      rendered.getExternalTransitionIds("s41", "reset_model", "s1")[0],
      {
        "kind": "action_language",
        "module": "tests.reference_model.hsm.reference_hsm_executables",
        "name": "capture_reset_request",
      },
    )
  ).issubset(session.highlight.current_text_ids)
  assert session.execution_log[-1]["entries"] == []


def test_hsm_project_server_http_step_endpoints_follow_child_frames() -> None:
  server = startProjectViewerServerFromProjectPath(REFERENCE_PROJECT_PATH)

  try:
    _post_json(server.base_url, "/api/runtime/play", {})
    for _ in range(8):
      _post_json(server.base_url, "/api/runtime/events", {"event_id": "transition"})
    _post_json(server.base_url, "/api/runtime/pause", {})
    _post_json(server.base_url, "/api/runtime/events", {"event_id": "reset_model", "parameters": {"full_reset": True}})
    _post_json(server.base_url, "/api/runtime/step-into", {})

    stepped_in = _post_json(server.base_url, "/api/runtime/step-into", {})
    assert stepped_in["active_model_id"] == "reference_activity"

    stepped_out = _post_json(server.base_url, "/api/runtime/step-out", {})
    assert stepped_out["active_model_id"] == "reference_hsm"
    assert stepped_out["variable_values"]["full_reset_requested"] is False

    reset = _post_json(server.base_url, "/api/runtime/reset", {})
    assert reset["active_model_id"] == "reference_hsm"

    _post_json(server.base_url, "/api/runtime/play", {})
    for _ in range(8):
      _post_json(server.base_url, "/api/runtime/events", {"event_id": "transition"})
    _post_json(server.base_url, "/api/runtime/pause", {})
    _post_json(server.base_url, "/api/runtime/events", {"event_id": "reset_model", "parameters": {"full_reset": True}})
    _post_json(server.base_url, "/api/runtime/step-into", {})

    stepped_over = _post_json(server.base_url, "/api/runtime/step-over", {})
    assert stepped_over["active_model_id"] == "reference_hsm"
    assert stepped_over["variable_values"]["full_reset_requested"] is False

  finally:
    server.close()


def test_hsm_project_server_rejects_ambiguous_step_endpoint() -> None:
  server = startProjectViewerServerFromProjectPath(REFERENCE_PROJECT_PATH)

  try:
    try:
      _post_json(server.base_url, "/api/runtime/step", {})
    except HTTPError as error:
      assert error.code == 404
    else:
      raise AssertionError("/api/runtime/step must not be served")
  finally:
    server.close()


def _highlightIds(session) -> set[str]:
  return (
    set(session.highlight.state_ids)
    | set(session.highlight.transition_ids)
    | set(session.highlight.text_ids)
    | set(session.highlight.current_transition_ids)
    | set(session.highlight.current_text_ids)
  )


def test_hsm_server_can_start_from_project_path() -> None:
  server = startProjectViewerServerFromProjectPath(REFERENCE_PROJECT_PATH)

  try:
    session = _get_json(server.base_url, "/api/session.json")

    assert session["active_model_id"] == "reference_hsm"
    models_by_id = {model["model_id"]: model for model in session["models"]}
    assert models_by_id == {
      "reference_hsm": {
        "model_id": "reference_hsm",
        "kind": "hsm",
        "svg_url": "/artifacts/models/reference_hsm/diagram.svg",
        "is_entrypoint": True,
      },
      "reference_activity": {
        "model_id": "reference_activity",
        "kind": "activity",
        "svg_url": "/artifacts/models/reference_activity/diagram.svg",
        "is_entrypoint": False,
      },
    }
  finally:
    server.close()


def test_hsm_server_serves_static_module_assets() -> None:
  server = startProjectViewerServerFromProjectPath(REFERENCE_PROJECT_PATH)

  try:
    with urlopen(f"{server.base_url}/") as response:
      index_text = response.read().decode("utf-8")
    with urlopen(f"{server.base_url}/viewer.js") as response:
      viewer_text = response.read().decode("utf-8")
    with urlopen(f"{server.base_url}/viewer_api.js") as response:
      api_text = response.read().decode("utf-8")
    with urlopen(f"{server.base_url}/viewer_viewport.js") as response:
      viewport_text = response.read().decode("utf-8")
    with urlopen(f"{server.base_url}/viewer_models.js") as response:
      models_text = response.read().decode("utf-8")
    with urlopen(f"{server.base_url}/viewer_highlights.js") as response:
      highlights_text = response.read().decode("utf-8")
    with urlopen(f"{server.base_url}/viewer_breakpoints.js") as response:
      breakpoints_text = response.read().decode("utf-8")
    with urlopen(f"{server.base_url}/viewer_debugger.js") as response:
      debugger_text = response.read().decode("utf-8")

    assert 'type="module" src="/viewer.js"' in index_text
    assert 'id="model-select"' in index_text
    assert 'id="debugger-step-into-button"' in index_text
    assert 'id="debugger-step-over-button"' in index_text
    assert 'id="debugger-step-out-button"' in index_text
    assert 'src="/assets/debugger-step-into.svg"' in index_text
    assert 'src="/assets/debugger-step.svg"' in index_text
    assert 'src="/assets/debugger-step-out.svg"' in index_text
    assert 'from "./viewer_api.js"' in viewer_text
    assert 'from "./viewer_viewport.js"' in viewer_text
    assert 'from "./viewer_models.js"' in viewer_text
    assert 'from "./viewer_highlights.js"' in viewer_text
    assert 'from "./viewer_breakpoints.js"' in viewer_text
    assert 'from "./viewer_debugger.js"' in viewer_text
    assert '"/api/runtime/step-into"' in viewer_text
    assert '"/api/runtime/step-over"' in viewer_text
    assert '"/api/runtime/step-out"' in viewer_text
    assert "viewerState.highlightsByModel = session.highlights_by_model" in viewer_text
    assert "export function applyDisplayedHighlight" in highlights_text
    assert "relatedIds: viewerState.focusTraceRelatedIds" in highlights_text
    assert "relatedIds: viewerState.focusStateRelatedIds" in highlights_text
    assert "function switchDisplayedModel" in viewer_text
    assert "export function saveDisplayedModelViewState" in models_text
    assert "getDisplayedModelKind() !== \"hsm\"" in highlights_text
    assert "getDisplayedModelBreakpointTargets" in breakpoints_text
    assert "renderBreakpointMarkers(viewerState.breakpointTargets)" in viewer_text
    assert "HSM mode" in index_text
    assert "export function renderModelOptions" in models_text
    assert "export function renderDebugger" in debugger_text
    assert "export async function fetchJson" in api_text
    assert "export function captureViewportState" in viewport_text
    assert "export function restoreViewportState" in viewport_text
    assert "export function applyZoom" in viewport_text
  finally:
    server.close()


def test_hsm_project_server_serves_model_svg_artifacts() -> None:
  server = startProjectViewerServerFromProjectPath(REFERENCE_PROJECT_PATH)

  try:
    with urlopen(f"{server.base_url}/artifacts/models/reference_hsm/diagram.svg") as response:
      hsm_svg = response.read().decode("utf-8")
    with urlopen(f"{server.base_url}/artifacts/models/reference_activity/diagram.svg") as response:
      activity_svg = response.read().decode("utf-8")

    assert "id=\"state_s41\"" in hsm_svg
    assert "id=\"action_reset_context_variables\"" in activity_svg
  finally:
    server.close()
