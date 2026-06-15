from __future__ import annotations

from mbse.model.hsm import load_hsm_document
from mbse.runtime.hsm.runtime_model.runtime_model_builder import derive_event_handler_slot_order
from mbse.runtime.hsm.runtime_model.runtime_model_builder import prepare_hsm_generated_runtime_view
from mbse.runtime.hsm.runtime_model.runtime_model_types import HsmGeneratedRuntimeView
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
    variables=[{"id": "speed", "default": 0}],
    events=[{"id": "open_evt"}, {"id": "close_evt"}, {"id": "stop_evt"}],
    initial_transition=hsm_initial("machine_init", "idle"),
    states=[
      hsm_state(
        "idle",
        states=[hsm_state("idle_waiting"), hsm_state("idle_ready")],
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
          hsm_external_transition("open_to_idle", target_id="idle")
        ],
      ),
      hsm_state("closed"),
    ],
  ) | {
    "states": [
      hsm_state(
        "idle",
        states=[
          hsm_state(
            "idle_waiting",
            external_transitions=[
              hsm_external_transition(
                "waiting_to_open",
                target_id="open",
                event_id="open_evt",
              ),
              hsm_external_transition(
                "waiting_to_closed",
                target_id="closed",
                event_id="close_evt",
              ),
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
          hsm_external_transition("open_to_idle", target_id="idle")
        ],
      ),
      hsm_state("closed"),
    ]
  }


def _c_reference_payload() -> dict[str, object]:
  return hsm_document(
    "c_reference_machine",
    events=[{"id": "transition_evt"}],
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


def _behavioral_payload(
  *,
  internal_before_transitions: bool,
) -> dict[str, object]:
  payload: dict[str, object] = {
    **hsm_document(
      "behavioral_machine",
      events=[{"id": "ping_evt"}, {"id": "open_evt"}],
      initial_transition=hsm_initial("machine_init", "idle"),
      states=[
        hsm_state(
          "idle",
          on_initial=[_callable_ref("record_activity")],
          on_entry=[_callable_ref("inert_entry")],
          on_exit=[_callable_ref("inert_exit")],
          states=[hsm_state("idle_waiting")],
          initial_transition=hsm_initial("idle_init", "idle_waiting"),
        ),
        hsm_state("open"),
      ],
    ),
  }
  original_idle_state = payload["states"][0]
  assert isinstance(original_idle_state, dict)
  idle_state_base = {
    key: value
    for key, value in original_idle_state.items()
    if key not in {"external_transitions", "internal_transitions"}
  }
  if internal_before_transitions:
    payload["states"][0] = {
      **idle_state_base,
      "internal_transitions": [
        hsm_internal_transition(
          "idle_ping_internal",
          event_id="ping_evt",
          activities=[_callable_ref("record_activity")],
        )
      ],
      "external_transitions": [
        hsm_external_transition(
          "idle_ping_open",
          event_id="ping_evt",
          guard=hsm_guard(
            guard_id="idle_ping_open_guard",
            guard=_callable_ref("allow_guard"),
            true_branch=hsm_guard_branch(
              "open",
              activities=[_callable_ref("count_increment")],
            ),
            false_branch=hsm_guard_branch("idle_waiting", activities=[]),
          ),
        )
      ],
    }
  else:
    payload["states"][0] = {
      **idle_state_base,
      "external_transitions": [
        hsm_external_transition(
          "idle_ping_open",
          event_id="ping_evt",
          guard=hsm_guard(
            guard_id="idle_ping_open_guard",
            guard=_callable_ref("allow_guard"),
            true_branch=hsm_guard_branch(
              "open",
              activities=[_callable_ref("count_increment")],
            ),
            false_branch=hsm_guard_branch("idle_waiting", activities=[]),
          ),
        )
      ],
      "internal_transitions": [
        hsm_internal_transition(
          "idle_ping_internal",
          event_id="ping_evt",
          activities=[_callable_ref("record_activity")],
        )
      ],
    }
  return payload


def _guard_node_payload() -> dict[str, object]:
  return hsm_document(
    "guard_node_machine",
    variables=[{"id": "trace", "default": []}, {"id": "job_queue", "default": 0}],
    events=[{"id": "advance_evt"}],
    initial_transition=hsm_initial("machine_init", "idle"),
    states=[
      hsm_state(
        "idle",
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
      hsm_state("processing"),
      hsm_state("blocked"),
    ],
  )


def test_prepare_hsm_generated_runtime_view_preserves_depth_first_indexes_and_initials():
  document = load_hsm_document(_runtime_payload())

  view = prepare_hsm_generated_runtime_view(document)

  assert view.document_id == "door_machine"
  assert view.state_ids == (
    "idle",
    "idle_waiting",
    "idle_ready",
    "open",
    "closed",
  )
  assert view.parent_ids == {
    "idle": None,
    "idle_waiting": "idle",
    "idle_ready": "idle",
    "open": None,
    "closed": None,
  }
  assert view.initial_target_ids == {
    None: "idle",
    "idle": "idle_waiting",
  }
  assert view.initial_transition_ids == {
    None: "machine_init",
    "idle": "idle_init",
  }


def test_prepare_hsm_generated_runtime_view_tracks_ancestry_and_initial_maps_for_c_topology():
  document = load_hsm_document(_c_reference_payload())

  view = prepare_hsm_generated_runtime_view(document)

  assert view.ancestry_by_state_id == {
    "s1": ("s1",),
    "s11": ("s1", "s11"),
    "s111": ("s1", "s11", "s111"),
    "s1111": ("s1", "s11", "s111", "s1111"),
    "s11111": ("s1", "s11", "s111", "s1111", "s11111"),
    "s2": ("s2",),
    "s21": ("s2", "s21"),
    "s211": ("s2", "s21", "s211"),
    "s2111": ("s2", "s21", "s211", "s2111"),
    "s2112": ("s2", "s21", "s211", "s2112"),
    "s3": ("s3",),
    "s31": ("s3", "s31"),
    "s311": ("s3", "s31", "s311"),
    "s4": ("s4",),
    "s41": ("s4", "s41"),
  }
  assert view.initial_transition_ids == {
    None: "machine_init",
    "s1": "s1_init",
    "s11": "s11_init",
    "s111": "s111_init",
    "s1111": "s1111_init",
    "s2": "s2_init",
    "s21": "s21_init",
    "s211": "s211_init",
    "s3": "s3_init",
    "s31": "s31_init",
    "s4": "s4_init",
  }


def test_prepare_hsm_generated_runtime_view_collects_leaf_ids_and_event_buckets_only():
  document = load_hsm_document(_runtime_payload())

  view = prepare_hsm_generated_runtime_view(document)

  assert view.leaf_state_ids == (
    "idle_waiting",
    "idle_ready",
    "open",
    "closed",
  )
  assert "external_transition_rows_by_state_id" not in HsmGeneratedRuntimeView.__dataclass_fields__
  assert tuple(
    (row.transition_id, row.event_id, row.source_id, row.target_id)
    for row in view.external_transition_rows_by_state_id["idle_waiting"]
  ) == (
    ("waiting_to_open", "open_evt", "idle_waiting", "open"),
    ("waiting_to_closed", "close_evt", "idle_waiting", "closed"),
  )
  assert tuple(
    (row.transition_id, row.event_id, row.source_id, row.target_id)
    for row in view.external_transition_rows_by_state_id["idle"]
  ) == (("idle_to_closed", "stop_evt", "idle", "closed"),)
  assert view.external_transition_rows_by_state_id["open"] == ()
  assert "open_to_idle" not in {
    row.transition_id
    for rows in view.external_transition_rows_by_state_id.values()
    for row in rows
  }


def test_prepare_hsm_generated_runtime_view_preserves_mixed_candidate_order_from_authored_collections():
  internal_first_payload = _behavioral_payload(internal_before_transitions=True)
  transition_first_payload = _behavioral_payload(internal_before_transitions=False)
  internal_first = prepare_hsm_generated_runtime_view(
    load_hsm_document(internal_first_payload),
    event_handler_slot_order=derive_event_handler_slot_order(internal_first_payload),
  )
  transition_first = prepare_hsm_generated_runtime_view(
    load_hsm_document(transition_first_payload),
    event_handler_slot_order=derive_event_handler_slot_order(transition_first_payload),
  )

  assert tuple(
    row.candidate_id for row in internal_first.event_candidate_rows_by_state_id["idle"]
  ) == ("idle_ping_internal", "idle_ping_open")
  assert tuple(
    row.kind for row in internal_first.event_candidate_rows_by_state_id["idle"]
  ) == ("internal", "external_transition")
  assert tuple(
    row.candidate_id for row in transition_first.event_candidate_rows_by_state_id["idle"]
  ) == ("idle_ping_open", "idle_ping_internal")


def test_derive_event_handler_slot_order_defaults_typed_documents_to_external_first():
  document = load_hsm_document(_behavioral_payload(internal_before_transitions=True))

  assert derive_event_handler_slot_order(document) == (
    "external_transitions",
    "internal_transitions",
  )


def test_prepare_hsm_generated_runtime_view_builds_lifecycle_and_initial_resolution_plans():
  payload = _behavioral_payload(internal_before_transitions=True)
  view = prepare_hsm_generated_runtime_view(
    load_hsm_document(payload),
    event_handler_slot_order=derive_event_handler_slot_order(payload),
  )

  candidate = view.event_candidate_rows_by_state_id["idle"][1]

  assert not hasattr(view, "initial_rows_by_owner_id")
  assert tuple(
    view.callable_plans_by_id[plan_id].name
    for plan_id in view.on_initial_plan_ids_by_state_id["idle"]
  ) == ("record_activity",)
  assert tuple(
    view.callable_plans_by_id[plan_id].name
    for plan_id in view.on_entry_plan_ids_by_state_id["idle"]
  ) == ("inert_entry",)
  assert tuple(
    view.callable_plans_by_id[plan_id].name
    for plan_id in view.on_exit_plan_ids_by_state_id["idle"]
  ) == ("inert_exit",)
  assert candidate.guard_plan_id is not None
  assert view.callable_plans_by_id[candidate.guard_plan_id].name == "allow_guard"
  assert candidate.activity_plan_ids == ()
  assert candidate.guard_true_branch is not None
  assert tuple(
    view.callable_plans_by_id[plan_id].name
    for plan_id in candidate.guard_true_branch.activity_plan_ids
  ) == ("count_increment",)
  assert candidate.guard_false_branch is not None
  assert candidate.guard_false_branch.branch_id == "idle_ping_open_guard_false"
  assert candidate.guard_false_branch.target_id == "idle_waiting"
  assert candidate.guard_false_branch.activity_plan_ids == ()


def test_prepare_hsm_generated_runtime_view_expands_guard_node_branches_into_runtime_candidates():
  view = prepare_hsm_generated_runtime_view(load_hsm_document(_guard_node_payload()))

  candidate = view.event_candidate_rows_by_state_id["idle"][0]

  assert candidate.candidate_id == "idle_to_job_check"
  assert candidate.event_id == "advance_evt"
  assert candidate.target_id == "job_check"
  assert candidate.guard_node_id == "job_check"
  assert candidate.guard_plan_id is not None
  assert view.callable_plans_by_id[candidate.guard_plan_id].name == "guard_job_available"
  assert candidate.guard_true_branch is not None
  assert candidate.guard_true_branch.branch_id == "job_check_true"
  assert candidate.guard_true_branch.target_id == "processing"
  assert tuple(
    view.callable_plans_by_id[plan_id].name
    for plan_id in candidate.guard_true_branch.activity_plan_ids
  ) == ("trace_guard_true_branch",)
  assert candidate.guard_false_branch is not None
  assert candidate.guard_false_branch.branch_id == "job_check_false"
  assert candidate.guard_false_branch.target_id == "blocked"
  assert tuple(
    view.callable_plans_by_id[plan_id].name
    for plan_id in candidate.guard_false_branch.activity_plan_ids
  ) == ("trace_guard_false_branch",)
