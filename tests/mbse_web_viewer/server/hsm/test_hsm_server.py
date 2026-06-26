from __future__ import annotations

from pathlib import Path

from mbse.model.hsm.hsm_model import HsmModel
from mbse_web_viewer.render.hsm.hsm_render import HsmRender
from mbse_web_viewer.server.hsm.hsm_server import HsmViewerServerController
from mbse_web_viewer.server.hsm.hsm_server import startHsmViewerServerFromModelPath


FIXTURE_PATH = (
  Path(__file__).resolve().parents[3] / "reference_model" / "hsm" / "reference_hsm_model.json"
)


def _build_running_controller(model: HsmModel) -> HsmViewerServerController:
  controller = HsmViewerServerController(model)
  controller.play()
  return controller


def test_hsm_server_session_exposes_paused_init_preview() -> None:
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
        "module": "tests.reference_model.hsm.reference_hsm_callables",
        "name": "s1_entry",
      },
    )
  )
  assert rendered.getStateId("s1") in session.focus.state_related_ids
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

  controller = HsmViewerServerController(model)

  for _ in range(20):
    session = controller.getSession()
    next_step = controller._runtime.getNextStep()
    if (
      next_step is not None
      and next_step["kind"] == "on_entry"
      and next_step["source_state_id"] == "s11111"
    ):
      break
    controller.stepExecution()
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
        "module": "tests.reference_model.hsm.reference_hsm_callables",
        "name": "s11111_entry",
      },
    )
  ).issubset(session.highlight.current_text_ids)

  committed = controller.stepExecution()

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
        "module": "tests.reference_model.hsm.reference_hsm_callables",
        "name": "s11111_exit",
      },
    )
  ).issubset(session.highlight.text_ids)
  assert set(
    rendered.getStateHookActivityTextIds(
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
      "module": "tests.reference_model.hsm.reference_hsm_callables",
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

  controller = HsmViewerServerController(model)
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
  controller = HsmViewerServerController(model)

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
      "module": "tests.reference_model.hsm.reference_hsm_callables",
      "name": "s1_to_s211",
    },
  )
  current_label_ids = rendered.getExternalTransitionLabelTextIds(transition_id)
  assert transition_id in session.highlight.current_transition_ids
  assert set(current_label_ids).issubset(session.highlight.current_text_ids)
  assert set(current_text_ids).issubset(session.highlight.current_text_ids)
  assert set(session.focus.trace_viewport_focus_ids) == set(session.highlight.current_transition_ids)

  session = controller.stepExecution()

  current_text_ids = rendered.getStateHookActivityTextIds(
    "s11111",
    "on_exit",
    {
      "module": "tests.reference_model.hsm.reference_hsm_callables",
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

  session = controller.stepExecution()

  branch_edge_id = rendered.getGuardBranchIds(
    "s41",
    "choose_transition",
    outcome=True,
    target_state_id="s41",
  )[0]
  assert controller._runtime.getNextStep()["kind"] == "guard_branch_transition"
  assert session.highlight.current_transition_ids == (branch_edge_id,)
  assert set(
    rendered.getExternalTransitionActivityTextIds(
      branch_edge_id,
      {
        "module": "tests.reference_model.hsm.reference_hsm_callables",
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
    session = controller.stepExecution()
    current_ids = set(session.highlight.current_text_ids)
    if not current_ids:
      continue
    section_ids = set(rendered.getStateHookSectionTextIds("s11111", "on_exit"))
    activity_ids = set(
      rendered.getStateHookActivityTextIds(
        "s11111",
        "on_exit",
        {
          "module": "tests.reference_model.hsm.reference_hsm_callables",
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
    session = controller.stepExecution()
    current_ids = set(session.highlight.current_text_ids)
    current_activity_ids = set(
      rendered.getStateHookActivityTextIds(
        "s1111",
        "on_exit",
        {
          "module": "tests.reference_model.hsm.reference_hsm_callables",
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
          "module": "tests.reference_model.hsm.reference_hsm_callables",
          "name": "s1111_entry",
        },
      ),
      *rendered.getStateHookActivityTextIds(
        "s1111",
        "on_exit",
        {
          "module": "tests.reference_model.hsm.reference_hsm_callables",
          "name": "s1111_exit",
        },
      ),
    }
    assert owner_ids.issubset(session.focus.trace_related_ids)
    break


def test_hsm_server_enqueue_while_paused_keeps_current_step_highlight() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)

  controller = _build_running_controller(model)
  controller.pause()
  controller.sendEvent("transition")

  current_step_session = None
  while True:
    session = controller.stepExecution()
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
    next_step = controller._runtime.getNextStep()
    if (
      next_step is not None
      and next_step["kind"] == "on_entry"
      and next_step["source_state_id"] == "s2111"
    ):
      break
    controller.stepExecution()

  assert session.state == {"id": "s11111", "label": "S11111"}
  assert session.highlight.state_ids == (rendered.getStateId("s11111"),)
  assert session.highlight.current_transition_ids == ()
  assert set(
    rendered.getStateHookActivityTextIds(
      "s2111",
      "on_entry",
      {
        "module": "tests.reference_model.hsm.reference_hsm_callables",
        "name": "s2111_entry",
      },
    )
  ).issubset(session.highlight.current_text_ids)

  committed = controller.stepExecution()

  assert committed.state == {"id": "s2111", "label": "S2111"}
  assert committed.debugger["has_pending_execution"] is False
  assert committed.debugger["queued_events"] == [{"event_id": "transition", "parameters": {}}]
  assert committed.highlight.state_ids == (rendered.getStateId("s2111"),)
  assert committed.highlight.current_transition_ids == ()
  assert committed.highlight.current_text_ids == ()

  planned = controller.stepExecution()

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
        "module": "tests.reference_model.hsm.reference_hsm_callables",
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
    step_session = controller.stepExecution()
    assert _highlightIds(step_session).issubset(step_session.focus.state_related_ids)
    assert _highlightIds(step_session).issubset(step_session.focus.trace_related_ids)
    if not step_session.debugger["has_pending_execution"] and not step_session.debugger["queued_events"]:
      break


def test_hsm_server_exposes_and_toggles_breakpoint_targets() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)
  controller = HsmViewerServerController(model)
  breakpoint_id = (
    "on_entry|s2111|tests.reference_model.hsm.reference_hsm_callables.s2111_entry"
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
    "on_entry|s2111|tests.reference_model.hsm.reference_hsm_callables.s2111_entry"
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
        "module": "tests.reference_model.hsm.reference_hsm_callables",
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
    "on_entry|s2111|tests.reference_model.hsm.reference_hsm_callables.s2111_entry"
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
  controller = HsmViewerServerController(model)
  breakpoint_ids = [
    "on_entry|s2111|tests.reference_model.hsm.reference_hsm_callables.s2111_entry",
    "on_exit|s11111|tests.reference_model.hsm.reference_hsm_callables.s11111_exit",
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
    "on_entry|s1|tests.reference_model.hsm.reference_hsm_callables.s1_entry"
  )

  assert [
    target.id
    for target in appended.breakpoints
    if target.is_set
  ] == [
    *reordered_ids,
    "on_entry|s1|tests.reference_model.hsm.reference_hsm_callables.s1_entry",
  ]


def test_hsm_server_step_and_play_match_final_trace_focus() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)

  play_controller = _build_running_controller(model)
  play_session = play_controller.sendEvent("transition")

  step_controller = _build_running_controller(model)
  step_controller.pause()
  step_session = step_controller.sendEvent("transition")
  while step_session.debugger["has_pending_execution"] or step_session.debugger["queued_events"]:
    step_session = step_controller.stepExecution()

  assert play_session.state == step_session.state
  assert play_session.highlight.state_ids == step_session.highlight.state_ids
  assert play_session.highlight.transition_ids == step_session.highlight.transition_ids
  assert play_session.highlight.text_ids == step_session.highlight.text_ids
  assert play_session.focus.trace_related_ids == step_session.focus.trace_related_ids


def _highlightIds(session) -> set[str]:
  return (
    set(session.highlight.state_ids)
    | set(session.highlight.transition_ids)
    | set(session.highlight.text_ids)
    | set(session.highlight.current_transition_ids)
    | set(session.highlight.current_text_ids)
  )


def test_hsm_server_can_start_from_model_path() -> None:
  server = startHsmViewerServerFromModelPath(FIXTURE_PATH)

  try:
    assert server.base_url.startswith("http://127.0.0.1:")
  finally:
    server.close()
