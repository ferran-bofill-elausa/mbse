from __future__ import annotations

from mbse.runtime.hsm import build_hsm_runtime
from tests.support.hsm_payloads import hsm_document
from tests.support.hsm_payloads import hsm_external_transition
from tests.support.hsm_payloads import hsm_guard
from tests.support.hsm_payloads import hsm_guard_branch
from tests.support.hsm_payloads import hsm_initial
from tests.support.hsm_payloads import hsm_internal_transition
from tests.support.hsm_payloads import hsm_state


def _callable_ref(name: str) -> dict[str, str]:
  return {
    "module": "tests.support.hsm_callable_fixtures",
    "name": name,
  }


def _runtime_payload() -> dict[str, object]:
  return hsm_document(
    "door_machine",
    variables=[
      {"id": "speed", "default": 0},
      {"id": "mode", "default": "idle"},
    ],
    events=[
      {"id": "open_evt"},
      {"id": "close_evt"},
      {"id": "stop_evt"},
      {"id": "ping_evt"},
    ],
    initial_transition=hsm_initial("machine_init", "idle"),
    states=[
      hsm_state(
        "idle",
        on_entry=[_callable_ref("inert_entry")],
        on_exit=[_callable_ref("inert_exit")],
        states=[
          hsm_state(
            "idle_waiting",
            external_transitions=[
              hsm_external_transition(
                "waiting_to_open",
                target_id="open",
                event_id="open_evt",
              )
            ],
          ),
          hsm_state("idle_ready"),
        ],
        initial_transition=hsm_initial("idle_init", "idle_waiting"),
        external_transitions=[
          hsm_external_transition(
            "idle_to_closed",
            target_id="closed",
            event_id="stop_evt",
          )
        ],
      ),
      hsm_state(
        "open",
        external_transitions=[
          hsm_external_transition(
            "open_to_idle",
            target_id="idle",
            event_id="close_evt",
          )
        ],
      ),
      hsm_state("closed"),
    ],
  )


def _c_reference_payload() -> dict[str, object]:
  return hsm_document(
    "c_reference_machine",
    events=[{"id": "transition_evt"}, {"id": "ping_evt"}],
    initial_transition=hsm_initial("machine_init", "s1"),
    states=[
      hsm_state(
        "s1",
        states=[
          hsm_state(
            "s11",
            states=[
              hsm_state(
                "s111",
                states=[
                  hsm_state(
                    "s1111",
                    states=[hsm_state("s11111")],
                    initial_transition=hsm_initial("s1111_init", "s11111"),
                  )
                ],
                initial_transition=hsm_initial("s111_init", "s1111"),
              )
            ],
            initial_transition=hsm_initial("s11_init", "s111"),
          )
        ],
        initial_transition=hsm_initial("s1_init", "s11"),
        external_transitions=[
          hsm_external_transition(
            "s1_to_s2111",
            target_id="s2111",
            event_id="transition_evt",
          )
        ],
      ),
      hsm_state(
        "s2",
        states=[
          hsm_state(
            "s21",
            states=[
              hsm_state(
                "s211",
                states=[
                  hsm_state(
                    "s2111",
                    external_transitions=[
                      hsm_external_transition(
                        "s2111_to_s2112",
                        target_id="s2112",
                        event_id="transition_evt",
                      )
                    ],
                  ),
                  hsm_state(
                    "s2112",
                    external_transitions=[
                      hsm_external_transition(
                        "s2112_to_s2",
                        target_id="s2",
                        event_id="transition_evt",
                      )
                    ],
                  ),
                ],
                initial_transition=hsm_initial("s211_init", "s2111"),
              )
            ],
            initial_transition=hsm_initial("s21_init", "s211"),
          )
        ],
        initial_transition=hsm_initial("s2_init", "s21"),
      ),
      hsm_state(
        "s3",
        states=[
          hsm_state(
            "s31",
            states=[
              hsm_state(
                "s311",
                external_transitions=[
                  hsm_external_transition(
                    "s311_to_s4",
                    target_id="s4",
                    event_id="transition_evt",
                  )
                ],
              )
            ],
            initial_transition=hsm_initial("s31_init", "s311"),
          )
        ],
        initial_transition=hsm_initial("s3_init", "s31"),
      ),
      hsm_state(
        "s4",
        on_entry=[_callable_ref("inert_entry")],
        on_exit=[_callable_ref("inert_exit")],
        states=[
          hsm_state(
            "s41",
            external_transitions=[
              hsm_external_transition(
                "s41_to_s41",
                target_id="s41",
                event_id="transition_evt",
              )
            ],
          )
        ],
        initial_transition=hsm_initial("s4_init", "s41"),
      ),
    ],
  )


def _parity_trace_payload() -> dict[str, object]:
  return hsm_document(
    "parity_trace_machine",
    variables=[{"id": "trace", "default": []}],
    events=[{"id": "ping_evt"}, {"id": "open_evt"}],
    initial_transition=hsm_initial("machine_init", "idle"),
    states=[
      hsm_state(
        "idle",
        on_entry=[_callable_ref("trace_parent_entry")],
        on_initial=[_callable_ref("trace_parent_initial")],
        states=[
          hsm_state(
            "idle_waiting",
            on_entry=[_callable_ref("trace_child_entry")],
            on_exit=[_callable_ref("trace_leaf_exit")],
          ),
          hsm_state("open", on_entry=[_callable_ref("trace_sibling_entry")]),
        ],
        initial_transition=hsm_initial("idle_init", "idle_waiting"),
        external_transitions=[
          hsm_external_transition(
            "idle_open",
            event_id="open_evt",
            guard=hsm_guard(
              guard_id="idle_open_guard",
              guard=_callable_ref("guard_true"),
              true_branch=hsm_guard_branch(
                "open",
                activities=[_callable_ref("trace_transition_activity")],
              ),
              false_branch=hsm_guard_branch("idle_waiting", activities=[]),
            ),
          )
        ],
        internal_transitions=[
          hsm_internal_transition(
            "idle_ping_internal",
            event_id="ping_evt",
            activities=[_callable_ref("trace_internal_activity")],
          )
        ],
      )
    ],
  )


def test_build_hsm_runtime_exposes_public_json_to_runtime_flow_only():
  runtime = build_hsm_runtime(_runtime_payload())

  runtime.init()
  runtime.set_variable("speed", 3)

  assert runtime.get_state() == "idle_waiting"
  assert runtime.send_event("open_evt") is True
  assert runtime.get_snapshot().state_id == "open"
  assert runtime.get_snapshot().active_path == ("open",)
  assert runtime.get_snapshot().variables == {"speed": 3, "mode": "idle"}


def test_build_hsm_runtime_replays_same_sequence_deterministically():
  first = build_hsm_runtime(_runtime_payload())
  second = build_hsm_runtime(_runtime_payload())

  for runtime in (first, second):
    runtime.init()
    runtime.set_variable("speed", 3)
    runtime.set_variable("mode", "auto")
    assert runtime.send_event("ping_evt") is False
    assert runtime.send_event("stop_evt") is True

  assert first.get_snapshot() == second.get_snapshot()


def test_build_hsm_runtime_replays_reference_parity_sequence_deterministically():
  snapshots_by_run: list[
    list[tuple[str, tuple[str, ...], str | None, bool, tuple[str, ...]]]
  ] = []

  for _ in range(2):
    runtime = build_hsm_runtime(_c_reference_payload())
    snapshots: list[
      tuple[str, tuple[str, ...], str | None, bool, tuple[str, ...]]
    ] = []
    runtime.init()
    snapshots.append(
      (
        runtime.get_snapshot().state_id,
        runtime.get_snapshot().active_path,
        runtime.get_snapshot().last_event.event_id,
        runtime.get_snapshot().last_event.handled,
        runtime.get_snapshot().last_event.transition_path_ids,
      )
    )
    assert runtime.send_event("transition_evt") is True
    snapshots.append(
        (
          runtime.get_snapshot().state_id,
          runtime.get_snapshot().active_path,
          runtime.get_snapshot().last_event.event_id,
          runtime.get_snapshot().last_event.handled,
          runtime.get_snapshot().last_event.transition_path_ids,
        )
      )
    assert runtime.send_event("transition_evt") is True
    snapshots.append(
        (
          runtime.get_snapshot().state_id,
          runtime.get_snapshot().active_path,
          runtime.get_snapshot().last_event.event_id,
          runtime.get_snapshot().last_event.handled,
          runtime.get_snapshot().last_event.transition_path_ids,
        )
      )
    assert runtime.send_event("transition_evt") is True
    snapshots.append(
        (
          runtime.get_snapshot().state_id,
          runtime.get_snapshot().active_path,
          runtime.get_snapshot().last_event.event_id,
          runtime.get_snapshot().last_event.handled,
          runtime.get_snapshot().last_event.transition_path_ids,
        )
      )
    assert runtime.send_event("ping_evt") is False
    snapshots.append(
      (
        runtime.get_snapshot().state_id,
        runtime.get_snapshot().active_path,
        runtime.get_snapshot().last_event.event_id,
        runtime.get_snapshot().last_event.handled,
        runtime.get_snapshot().last_event.transition_path_ids,
      )
    )
    runtime.set_state("s311")
    assert runtime.send_event("transition_evt") is True
    snapshots.append(
        (
          runtime.get_snapshot().state_id,
          runtime.get_snapshot().active_path,
          runtime.get_snapshot().last_event.event_id,
          runtime.get_snapshot().last_event.handled,
          runtime.get_snapshot().last_event.transition_path_ids,
        )
      )
    assert runtime.send_event("transition_evt") is True
    snapshots.append(
        (
          runtime.get_snapshot().state_id,
          runtime.get_snapshot().active_path,
          runtime.get_snapshot().last_event.event_id,
          runtime.get_snapshot().last_event.handled,
          runtime.get_snapshot().last_event.transition_path_ids,
        )
      )
    snapshots_by_run.append(snapshots)

  assert snapshots_by_run == [
    [
      (
        "s11111",
        ("s1", "s11", "s111", "s1111", "s11111"),
        None,
        True,
        ("machine_init", "s1_init", "s11_init", "s111_init", "s1111_init"),
      ),
      ("s2111", ("s2", "s21", "s211", "s2111"), "transition_evt", True, ("s1_to_s2111",)),
      ("s2112", ("s2", "s21", "s211", "s2112"), "transition_evt", True, ("s2111_to_s2112",)),
      ("s2", ("s2",), "transition_evt", True, ("s2112_to_s2",)),
      ("s2", ("s2",), "ping_evt", False, ()),
      ("s41", ("s4", "s41"), "transition_evt", True, ("s311_to_s4", "s4_init")),
      ("s41", ("s4", "s41"), "transition_evt", True, ("s41_to_s41",)),
    ],
    [
      (
        "s11111",
        ("s1", "s11", "s111", "s1111", "s11111"),
        None,
        True,
        ("machine_init", "s1_init", "s11_init", "s111_init", "s1111_init"),
      ),
      ("s2111", ("s2", "s21", "s211", "s2111"), "transition_evt", True, ("s1_to_s2111",)),
      ("s2112", ("s2", "s21", "s211", "s2112"), "transition_evt", True, ("s2111_to_s2112",)),
      ("s2", ("s2",), "transition_evt", True, ("s2112_to_s2",)),
      ("s2", ("s2",), "ping_evt", False, ()),
      ("s41", ("s4", "s41"), "transition_evt", True, ("s311_to_s4", "s4_init")),
      ("s41", ("s4", "s41"), "transition_evt", True, ("s41_to_s41",)),
    ],
  ]


def test_build_hsm_runtime_replays_executable_parity_trace_deterministically():
  traces_by_run: list[list[str]] = []
  snapshots_by_run = []

  for _ in range(2):
    runtime = build_hsm_runtime(_parity_trace_payload())

    runtime.init()
    assert runtime.send_event("ping_evt") is True
    assert runtime.send_event("open_evt") is True

    traces_by_run.append(runtime.get_snapshot().variables["trace"])
    snapshots_by_run.append(runtime.get_snapshot())

  assert traces_by_run == [
    [
      "parent.entry",
      "parent.initial",
      "child.entry",
      "internal.activity",
      "guard.true",
      "leaf.exit",
      "transition.activity",
      "sibling.entry",
    ],
    [
      "parent.entry",
      "parent.initial",
      "child.entry",
      "internal.activity",
      "guard.true",
      "leaf.exit",
      "transition.activity",
      "sibling.entry",
    ],
  ]
  assert snapshots_by_run[0] == snapshots_by_run[1]
  assert snapshots_by_run[0].last_event.event_id == "open_evt"
  assert snapshots_by_run[0].last_event.handled is True
  assert snapshots_by_run[0].last_event.transition_path_ids == (
    "idle_open",
    "idle_open_guard_true",
  )
  assert [
    (
      activity.activity_id,
      activity.owner_kind,
      activity.owner_id,
    )
    for activity in snapshots_by_run[0].last_event.executed_activities
  ] == [
    ("trace_leaf_exit", "state_on_exit", "idle_waiting"),
    (
      "trace_transition_activity",
      "guard_branch",
      "idle_open_guard_true",
    ),
    ("trace_sibling_entry", "state_on_entry", "open"),
  ]
