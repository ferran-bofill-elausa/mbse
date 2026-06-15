from __future__ import annotations

import pytest

from mbse.runtime.hsm import HsmExecutedActivity
from mbse.runtime.hsm import HsmRuntimeMetadata
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


def _init_order_payload() -> dict[str, object]:
  return hsm_document(
    "init_order_machine",
    variables=[{"id": "trace", "default": []}],
    initial_transition=hsm_initial("machine_init", "parent"),
    states=[
      hsm_state(
        "parent",
        on_entry=[_callable_ref("trace_parent_entry")],
        on_initial=[_callable_ref("trace_parent_initial")],
        states=[
          hsm_state(
            "child",
            on_entry=[_callable_ref("trace_child_entry")],
            on_initial=[_callable_ref("trace_child_initial")],
            states=[hsm_state("leaf", on_entry=[_callable_ref("trace_leaf_entry")])],
            initial_transition=hsm_initial("child_init", "leaf"),
          )
        ],
        initial_transition=hsm_initial("parent_init", "child"),
      )
    ],
  )


def _deep_local_initial_payload() -> dict[str, object]:
  return hsm_document(
    "deep_local_initial_machine",
    variables=[{"id": "trace", "default": []}],
    initial_transition=hsm_initial("machine_init", "parent"),
    states=[
      hsm_state(
        "parent",
        on_entry=[_callable_ref("trace_parent_entry")],
        on_initial=[_callable_ref("trace_parent_initial")],
        states=[
          hsm_state(
            "child",
            on_entry=[_callable_ref("trace_child_entry")],
            states=[
              hsm_state(
                "leaf",
                on_entry=[_callable_ref("trace_leaf_entry")],
              )
            ],
          )
        ],
        initial_transition=hsm_initial("parent_init", "leaf"),
      )
    ],
  )


def _guard_bubbling_payload() -> dict[str, object]:
  return hsm_document(
    "guard_bubbling_machine",
    variables=[
      {"id": "trace", "default": []},
      {"id": "guard_flag", "default": False},
    ],
    events=[{"id": "advance_evt"}],
    initial_transition=hsm_initial("machine_init", "parent"),
    states=[
      hsm_state(
        "parent",
        states=[
          hsm_state(
            "leaf",
            on_exit=[_callable_ref("trace_leaf_exit")],
            external_transitions=[
              hsm_external_transition(
                "leaf_guarded",
                event_id="advance_evt",
                guard=hsm_guard(
                  guard_id="leaf_guarded_guard",
                  guard=_callable_ref("guard_from_flag"),
                  true_branch=hsm_guard_branch(
                    "sibling",
                    activities=[_callable_ref("trace_transition_activity")],
                  ),
                  false_branch=hsm_guard_branch(
                    "leaf",
                    activities=[_callable_ref("trace_guard_false_branch")],
                  ),
                ),
              )
            ],
          ),
          hsm_state("sibling", on_entry=[_callable_ref("trace_sibling_entry")]),
        ],
        initial_transition=hsm_initial("parent_init", "leaf"),
        external_transitions=[
          hsm_external_transition(
            "parent_fallback",
            event_id="advance_evt",
            guard=hsm_guard(
              guard_id="parent_fallback_guard",
              guard=_callable_ref("guard_true"),
              true_branch=hsm_guard_branch(
                "sibling",
                activities=[_callable_ref("trace_transition_activity")],
              ),
              false_branch=hsm_guard_branch("parent", activities=[]),
            ),
          )
        ],
      ),
      hsm_state("other"),
    ],
  )


def _internal_transition_payload() -> dict[str, object]:
  payload = hsm_document(
    "internal_transition_machine",
    variables=[{"id": "trace", "default": []}],
    events=[{"id": "ping_evt"}],
    initial_transition=hsm_initial("machine_init", "parent"),
    states=[
      hsm_state(
        "parent",
        states=[hsm_state("leaf")],
        initial_transition=hsm_initial("parent_init", "leaf"),
        external_transitions=[
          hsm_external_transition(
            "parent_ping_transition",
            target_id="other",
            event_id="ping_evt",
            activities=[_callable_ref("trace_transition_activity")],
          )
        ],
        internal_transitions=[
          hsm_internal_transition(
            "parent_ping_internal",
            event_id="ping_evt",
            activities=[_callable_ref("trace_internal_activity")],
          )
        ],
      ),
      hsm_state("other"),
    ],
  )
  parent_state = payload["states"][0]
  assert isinstance(parent_state, dict)
  parent_state_base = {
    key: value
    for key, value in parent_state.items()
    if key not in {"external_transitions", "internal_transitions"}
  }
  payload["states"][0] = {
    **parent_state_base,
    "internal_transitions": parent_state["internal_transitions"],
    "external_transitions": parent_state["external_transitions"],
  }
  return payload


def _guard_node_payload() -> dict[str, object]:
  return hsm_document(
    "guard_node_machine",
    variables=[
      {"id": "trace", "default": []},
      {"id": "job_queue", "default": 0},
    ],
    events=[{"id": "advance_evt"}],
    initial_transition=hsm_initial("machine_init", "idle"),
    states=[
      hsm_state(
        "idle",
        on_exit=[_callable_ref("trace_leaf_exit")],
        external_transitions=[
          hsm_external_transition(
            "idle_to_job_check",
            event_id="advance_evt",
            guard=hsm_guard(
              guard_id="job_check",
              guard=_callable_ref("guard_job_available"),
              true_branch=hsm_guard_branch(
                "processing",
                activities=[_callable_ref("trace_guard_true_branch")],
              ),
              false_branch=hsm_guard_branch(
                "blocked",
                activities=[_callable_ref("trace_guard_false_branch")],
              ),
            ),
          )
        ],
      ),
      hsm_state("processing", on_entry=[_callable_ref("trace_sibling_entry")]),
      hsm_state("blocked", on_entry=[_callable_ref("trace_desc_entry")]),
    ],
  )


def _self_transition_payload() -> dict[str, object]:
  return hsm_document(
    "self_transition_machine",
    variables=[{"id": "trace", "default": []}],
    events=[{"id": "loop_evt"}],
    initial_transition=hsm_initial("machine_init", "self_state"),
    states=[
      hsm_state(
        "self_state",
        on_entry=[_callable_ref("trace_self_entry")],
        on_exit=[_callable_ref("trace_self_exit")],
        external_transitions=[
          hsm_external_transition(
            "self_loop",
            target_id="self_state",
            event_id="loop_evt",
            activities=[_callable_ref("trace_transition_activity")],
          )
        ],
      )
    ],
  )


def _ancestor_descendant_payload() -> dict[str, object]:
  return hsm_document(
    "ancestor_descendant_machine",
    variables=[{"id": "trace", "default": []}],
    events=[{"id": "up_evt"}, {"id": "down_evt"}],
    initial_transition=hsm_initial("machine_init", "parent"),
    states=[
      hsm_state(
        "parent",
        states=[
          hsm_state(
            "leaf",
            on_exit=[_callable_ref("trace_leaf_exit")],
            external_transitions=[
              hsm_external_transition(
                "leaf_to_parent",
                target_id="parent",
                event_id="up_evt",
                activities=[_callable_ref("trace_transition_activity")],
              )
            ],
          ),
          hsm_state(
            "desc",
            on_entry=[_callable_ref("trace_desc_entry")],
            on_initial=[_callable_ref("trace_desc_initial")],
            states=[
              hsm_state("desc_leaf", on_entry=[_callable_ref("trace_desc_leaf_entry")])
            ],
            initial_transition=hsm_initial("desc_init", "desc_leaf"),
          ),
        ],
        initial_transition=hsm_initial("parent_init", "leaf"),
        external_transitions=[
          hsm_external_transition(
            "parent_to_desc",
            target_id="desc",
            event_id="down_evt",
            activities=[_callable_ref("trace_transition_activity")],
          )
        ],
      )
    ],
  )


def test_hsm_runtime_init_executes_entry_and_initial_order():
  runtime = build_hsm_runtime(_init_order_payload())

  runtime.init()

  snapshot = runtime.get_snapshot()

  assert runtime.get_state() == "leaf"
  assert snapshot.state_id == "leaf"
  assert snapshot.active_path == ("parent", "child", "leaf")
  assert snapshot.last_event.event_id is None
  assert snapshot.last_event.handled is True
  assert snapshot.last_event.handler_kind == "init"
  assert snapshot.last_event.handler_id is None
  assert snapshot.last_event.transition_path_ids == (
    "machine_init",
    "parent_init",
    "child_init",
  )
  assert snapshot.last_event.executed_activities == (
    HsmExecutedActivity(
      activity_id="trace_parent_entry",
      owner_kind="state_on_entry",
      owner_id="parent",
    ),
    HsmExecutedActivity(
      activity_id="trace_parent_initial",
      owner_kind="state_on_initial",
      owner_id="parent",
    ),
    HsmExecutedActivity(
      activity_id="trace_child_entry",
      owner_kind="state_on_entry",
      owner_id="child",
    ),
    HsmExecutedActivity(
      activity_id="trace_child_initial",
      owner_kind="state_on_initial",
      owner_id="child",
    ),
    HsmExecutedActivity(
      activity_id="trace_leaf_entry",
      owner_kind="state_on_entry",
      owner_id="leaf",
    ),
  )
  assert snapshot.variables == {
    "trace": [
      "parent.entry",
      "parent.initial",
      "child.entry",
      "child.initial",
      "leaf.entry",
    ]
  }


def test_hsm_runtime_init_enters_full_descendant_path_for_deep_local_initial_target():
  runtime = build_hsm_runtime(_deep_local_initial_payload())

  runtime.init()
  snapshot = runtime.get_snapshot()

  assert snapshot.state_id == "leaf"
  assert snapshot.active_path == ("parent", "child", "leaf")
  assert snapshot.last_event.transition_path_ids == ("machine_init", "parent_init")
  assert snapshot.variables == {
    "trace": [
      "parent.entry",
      "parent.initial",
      "child.entry",
      "leaf.entry",
    ]
  }


def test_hsm_runtime_exposes_canonical_event_and_variable_metadata():
  runtime = build_hsm_runtime(_guard_node_payload())

  assert runtime.get_metadata() == HsmRuntimeMetadata(
    event_ids=("advance_evt",),
    variable_ids=("trace", "job_queue"),
  )


def test_hsm_runtime_metadata_preserves_declared_order_and_empty_collections():
  runtime = build_hsm_runtime(
    hsm_document(
      "metadata_machine",
      events=[{"id": "first_evt"}, {"id": "second_evt"}],
      initial_transition=hsm_initial("machine_init", "idle"),
      states=[hsm_state("idle")],
    )
  )

  assert runtime.get_metadata() == HsmRuntimeMetadata(
    event_ids=("first_evt", "second_evt"),
    variable_ids=(),
  )


def test_hsm_runtime_guard_false_branch_handles_event_without_bubbling_to_parent():
  runtime = build_hsm_runtime(_guard_bubbling_payload())

  runtime.init()
  runtime.set_variable("guard_flag", False)

  assert runtime.send_event("advance_evt") is True
  snapshot = runtime.get_snapshot()

  assert runtime.get_state() == "leaf"
  assert snapshot.variables == {
    "trace": [
      "guard.flag",
      "guard.false_branch",
    ],
    "guard_flag": False,
  }
  assert snapshot.last_event.event_id == "advance_evt"
  assert snapshot.last_event.handled is True
  assert snapshot.last_event.handler_kind == "guard_transition"
  assert snapshot.last_event.handler_id == "leaf_guarded"
  assert snapshot.last_event.transition_path_ids == (
    "leaf_guarded",
    "leaf_guarded_guard_false",
  )


def test_hsm_runtime_guard_true_takes_leaf_transition_with_ctx_attribute_access():
  runtime = build_hsm_runtime(_guard_bubbling_payload())

  runtime.init()
  runtime.set_variable("guard_flag", True)

  assert runtime.send_event("advance_evt") is True
  snapshot = runtime.get_snapshot()

  assert runtime.get_state() == "sibling"
  assert snapshot.variables == {
    "trace": [
      "guard.flag",
      "leaf.exit",
      "transition.activity",
      "sibling.entry",
    ],
    "guard_flag": True,
  }
  assert snapshot.last_event.handler_id == "leaf_guarded"
  assert snapshot.last_event.transition_path_ids == (
    "leaf_guarded",
    "leaf_guarded_guard_true",
  )


def test_hsm_runtime_guard_requires_bool_return_value():
  payload = _guard_bubbling_payload()
  parent_state = payload["states"][0]
  assert isinstance(parent_state, dict)
  leaf_state = parent_state["states"][0]
  assert isinstance(leaf_state, dict)
  leaf_state["external_transitions"] = [
    hsm_external_transition(
      "leaf_guarded",
      event_id="advance_evt",
      guard=hsm_guard(
        guard_id="leaf_guarded_guard",
        guard=_callable_ref("bad_guard_truthy"),
        true_branch=hsm_guard_branch(
          "sibling",
          activities=[_callable_ref("trace_transition_activity")],
        ),
        false_branch=hsm_guard_branch(
          "leaf",
          activities=[_callable_ref("trace_guard_false_branch")],
        ),
      ),
    )
  ]

  runtime = build_hsm_runtime(payload)
  runtime.init()

  with pytest.raises(
    TypeError,
    match=(
      r"Guard callable 'tests\.support\.hsm_callable_fixtures\.bad_guard_truthy' "
      r"must return bool, got int\."
    ),
  ):
    runtime.send_event("advance_evt")


def test_hsm_runtime_guard_node_true_branch_executes_branch_activities_and_path():
  runtime = build_hsm_runtime(_guard_node_payload())
  runtime.init()
  runtime.set_variable("job_queue", 2)

  assert runtime.send_event("advance_evt") is True
  snapshot = runtime.get_snapshot()

  assert runtime.get_state() == "processing"
  assert snapshot.variables == {
    "trace": [
      "guard.job_available",
      "leaf.exit",
      "guard.true_branch",
      "sibling.entry",
    ],
    "job_queue": 2,
  }
  assert snapshot.last_event.event_id == "advance_evt"
  assert snapshot.last_event.handled is True
  assert snapshot.last_event.handler_kind == "guard_transition"
  assert snapshot.last_event.handler_id == "idle_to_job_check"
  assert snapshot.last_event.guard_node_id == "job_check"
  assert snapshot.last_event.guard_branch_id == "job_check_true"
  assert snapshot.last_event.transition_path_ids == (
    "idle_to_job_check",
    "job_check_true",
  )
  assert snapshot.last_event.executed_activities == (
    HsmExecutedActivity(
      activity_id="trace_leaf_exit",
      owner_kind="state_on_exit",
      owner_id="idle",
    ),
    HsmExecutedActivity(
      activity_id="trace_guard_true_branch",
      owner_kind="guard_branch",
      owner_id="job_check_true",
    ),
    HsmExecutedActivity(
      activity_id="trace_sibling_entry",
      owner_kind="state_on_entry",
      owner_id="processing",
    ),
  )


def test_hsm_runtime_guard_node_false_branch_executes_branch_activities_and_path():
  runtime = build_hsm_runtime(_guard_node_payload())
  runtime.init()

  assert runtime.send_event("advance_evt") is True
  snapshot = runtime.get_snapshot()

  assert runtime.get_state() == "blocked"
  assert snapshot.variables == {
    "trace": [
      "guard.job_available",
      "leaf.exit",
      "guard.false_branch",
      "desc.entry",
    ],
    "job_queue": 0,
  }
  assert snapshot.last_event.handler_kind == "guard_transition"
  assert snapshot.last_event.handler_id == "idle_to_job_check"
  assert snapshot.last_event.guard_node_id == "job_check"
  assert snapshot.last_event.guard_branch_id == "job_check_false"
  assert snapshot.last_event.transition_path_ids == (
    "idle_to_job_check",
    "job_check_false",
  )


def test_hsm_runtime_guard_same_state_branch_does_not_reenter_source_state():
  payload = hsm_document(
    "guard_same_state_machine",
    variables=[
      {"id": "trace", "default": []},
      {"id": "guard_flag", "default": False},
    ],
    events=[{"id": "loop_evt"}],
    initial_transition=hsm_initial("machine_init", "idle"),
    states=[
      hsm_state(
        "idle",
        on_entry=[_callable_ref("trace_self_entry")],
        on_exit=[_callable_ref("trace_self_exit")],
        external_transitions=[
          hsm_external_transition(
            "idle_decide",
            event_id="loop_evt",
            guard=hsm_guard(
              guard_id="idle_decide_guard",
              guard=_callable_ref("guard_from_flag"),
              true_branch=hsm_guard_branch(
                "processing",
                activities=[_callable_ref("trace_guard_true_branch")],
              ),
              false_branch=hsm_guard_branch(
                "idle",
                activities=[_callable_ref("trace_guard_false_branch")],
              ),
            ),
          )
        ],
      ),
      hsm_state("processing", on_entry=[_callable_ref("trace_sibling_entry")]),
    ],
  )

  runtime = build_hsm_runtime(payload)
  runtime.init()

  assert runtime.get_snapshot().variables == {
    "trace": ["self.entry"],
    "guard_flag": False,
  }
  assert runtime.send_event("loop_evt") is True

  snapshot = runtime.get_snapshot()

  assert snapshot.state_id == "idle"
  assert snapshot.active_path == ("idle",)
  assert snapshot.variables == {
    "trace": [
      "self.entry",
      "guard.flag",
      "guard.false_branch",
    ],
    "guard_flag": False,
  }
  assert snapshot.last_event.handler_kind == "guard_transition"
  assert snapshot.last_event.handler_id == "idle_decide"
  assert snapshot.last_event.guard_node_id == "idle_decide_guard"
  assert snapshot.last_event.guard_branch_id == "idle_decide_guard_false"
  assert snapshot.last_event.transition_path_ids == (
    "idle_decide",
    "idle_decide_guard_false",
  )
  assert snapshot.last_event.executed_activities == (
    HsmExecutedActivity(
      activity_id="trace_guard_false_branch",
      owner_kind="guard_branch",
      owner_id="idle_decide_guard_false",
    ),
  )


def test_hsm_runtime_internal_transition_handles_event_without_state_change():
  runtime = build_hsm_runtime(_internal_transition_payload())
  runtime.init()
  baseline = runtime.get_snapshot()

  assert runtime.send_event("ping_evt") is True
  snapshot = runtime.get_snapshot()

  assert snapshot.state_id == baseline.state_id
  assert snapshot.active_path == baseline.active_path
  assert snapshot.last_event.event_id == "ping_evt"
  assert snapshot.last_event.handled is True
  assert snapshot.last_event.handler_kind == "internal_transition"
  assert snapshot.last_event.handler_id == "parent_ping_internal"
  assert snapshot.last_event.transition_path_ids == ()
  assert snapshot.last_event.executed_activities == (
    HsmExecutedActivity(
      activity_id="trace_internal_activity",
      owner_kind="internal_transition",
      owner_id="parent_ping_internal",
    ),
  )
  assert snapshot.variables == {
    "trace": ["internal.activity"]
  }


def test_hsm_runtime_unhandled_event_resets_last_event_execution_details():
  runtime = build_hsm_runtime(_ancestor_descendant_payload())
  runtime.init()

  assert runtime.send_event("missing_evt") is False
  snapshot = runtime.get_snapshot()

  assert snapshot.state_id == "leaf"
  assert snapshot.active_path == ("parent", "leaf")
  assert snapshot.last_event.event_id == "missing_evt"
  assert snapshot.last_event.handled is False
  assert snapshot.last_event.handler_kind is None
  assert snapshot.last_event.handler_id is None
  assert snapshot.last_event.transition_path_ids == ()
  assert snapshot.last_event.executed_activities == ()


def test_hsm_runtime_self_transition_reenters_source_in_order():
  runtime = build_hsm_runtime(_self_transition_payload())
  runtime.init()

  assert runtime.get_snapshot().variables == {"trace": ["self.entry"]}
  assert runtime.send_event("loop_evt") is True
  snapshot = runtime.get_snapshot()

  assert runtime.get_state() == "self_state"
  assert snapshot.active_path == ("self_state",)
  assert snapshot.variables == {
    "trace": [
      "self.entry",
      "self.exit",
      "transition.activity",
      "self.entry",
    ]
  }
  assert snapshot.last_event.transition_path_ids == ("self_loop",)


def test_hsm_runtime_preserves_ancestor_and_descendant_transition_ordering():
  runtime = build_hsm_runtime(_ancestor_descendant_payload())

  runtime.init()

  assert runtime.send_event("up_evt") is True
  up_snapshot = runtime.get_snapshot()

  assert runtime.get_state() == "parent"
  assert up_snapshot.active_path == ("parent",)
  assert up_snapshot.variables == {
    "trace": ["leaf.exit", "transition.activity"]
  }

  runtime.get_variable("trace").clear()

  assert runtime.send_event("down_evt") is True
  snapshot = runtime.get_snapshot()

  assert runtime.get_state() == "desc_leaf"
  assert snapshot.active_path == ("parent", "desc", "desc_leaf")
  assert snapshot.last_event.event_id == "down_evt"
  assert snapshot.last_event.handled is True
  assert snapshot.last_event.handler_kind == "external_transition"
  assert snapshot.last_event.handler_id == "parent_to_desc"
  assert snapshot.last_event.transition_path_ids == (
    "parent_to_desc",
    "desc_init",
  )
  assert snapshot.last_event.executed_activities == (
    HsmExecutedActivity(
      activity_id="trace_transition_activity",
      owner_kind="external_transition",
      owner_id="parent_to_desc",
    ),
    HsmExecutedActivity(
      activity_id="trace_desc_entry",
      owner_kind="state_on_entry",
      owner_id="desc",
    ),
    HsmExecutedActivity(
      activity_id="trace_desc_initial",
      owner_kind="state_on_initial",
      owner_id="desc",
    ),
    HsmExecutedActivity(
      activity_id="trace_desc_leaf_entry",
      owner_kind="state_on_entry",
      owner_id="desc_leaf",
    ),
  )
  assert snapshot.variables == {
    "trace": [
      "transition.activity",
      "desc.entry",
      "desc.initial",
      "desc.leaf.entry",
    ]
  }


def test_hsm_runtime_rejects_undeclared_variable_access() -> None:
  runtime = build_hsm_runtime(_init_order_payload())

  runtime.init()

  with pytest.raises(
    ValueError,
    match=r"Unknown HSM variable 'missing_var'\. Declare it in the HSM 'variables' list first\.",
  ):
    runtime.set_variable("missing_var", 1)

  with pytest.raises(
    ValueError,
    match=r"Unknown HSM variable 'missing_var'\. Declare it in the HSM 'variables' list first\.",
  ):
    runtime.get_variable("missing_var")


def test_hsm_runtime_set_state_keeps_leaf_only_validation():
  runtime = build_hsm_runtime(_ancestor_descendant_payload())
  runtime.init()

  runtime.set_state("desc_leaf")
  assert runtime.get_state() == "desc_leaf"
  assert runtime.get_snapshot().last_event.event_id is None
  assert runtime.get_snapshot().last_event.transition_path_ids == ()

  with pytest.raises(ValueError, match="leaf state"):
    runtime.set_state("parent")
