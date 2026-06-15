from __future__ import annotations

from mbse.model.hsm import load_hsm_document
from mbse.runtime.hsm import build_hsm_runtime
from mbse.runtime.hsm.generator import generator as hsm_generator_module
from mbse.runtime.hsm.generator.generator import load_generated_runtime
from mbse.runtime.hsm.generator.generator import render_generated_runtime_source
from mbse.runtime.hsm.runtime_model.runtime_model_builder import derive_event_handler_slot_order
from mbse.runtime.hsm.runtime_model.runtime_model_builder import prepare_hsm_generated_runtime_view
from mbse.runtime.hsm.runtime_model.runtime_model_types import HsmGeneratedRuntimeEventCandidateRow
from mbse.runtime.hsm.runtime_model.runtime_model_types import HsmGeneratedRuntimeGuardBranchRow
from mbse.runtime.hsm.runtime_model.runtime_model_types import HsmGeneratedRuntimeExternalTransitionRow
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
      hsm_state("open"),
      hsm_state("closed"),
    ],
  )


def _behavioral_payload() -> dict[str, object]:
  payload = hsm_document(
    "behavioral_machine",
    events=[{"id": "ping_evt"}],
    initial_transition=hsm_initial("machine_init", "idle"),
    states=[
      hsm_state(
        "idle",
        on_initial=[_callable_ref("record_activity")],
        on_entry=[_callable_ref("inert_entry")],
        on_exit=[_callable_ref("inert_exit")],
        states=[hsm_state("idle_waiting")],
        initial_transition=hsm_initial("idle_init", "idle_waiting"),
        external_transitions=[
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
        internal_transitions=[
          hsm_internal_transition(
            "idle_ping_internal",
            event_id="ping_evt",
            activities=[_callable_ref("record_activity")],
          )
        ],
      ),
      hsm_state("open"),
    ],
  )
  idle_state = payload["states"][0]
  assert isinstance(idle_state, dict)
  idle_state_base = {
    key: value
    for key, value in idle_state.items()
    if key not in {"external_transitions", "internal_transitions"}
  }
  payload["states"][0] = {
    **idle_state_base,
    "internal_transitions": idle_state["internal_transitions"],
    "external_transitions": idle_state["external_transitions"],
  }
  return payload


def _parity_payload() -> dict[str, object]:
  payload = hsm_document(
    "parity_machine",
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
  idle_state = payload["states"][0]
  assert isinstance(idle_state, dict)
  idle_state_base = {
    key: value
    for key, value in idle_state.items()
    if key not in {"external_transitions", "internal_transitions"}
  }
  payload["states"][0] = {
    **idle_state_base,
    "internal_transitions": idle_state["internal_transitions"],
    "external_transitions": idle_state["external_transitions"],
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


def test_render_generated_runtime_source_emits_private_handlers_and_indexes():
  document = load_hsm_document(_runtime_payload())

  source = render_generated_runtime_source(
    prepare_hsm_generated_runtime_view(document)
  )

  assert (
    "from mbse.runtime.hsm.runtime_model.runtime_model_types import "
    "HsmGeneratedRuntimeCallablePlan" in source
  )
  assert "from mbse.runtime.hsm import HsmGeneratedRuntimeCallablePlan" not in source
  assert "PARENTS = {" in source
  assert "ANCESTRY_BY_STATE = {" in source
  assert '"idle_waiting": ("idle", "idle_waiting")' in source
  assert '"idle_waiting": "idle"' in source
  assert 'INITIAL_TARGETS = {None: "idle", "idle": "idle_waiting"}' in source
  assert (
    'INITIAL_TRANSITION_IDS = {None: "machine_init", "idle": "idle_init"}'
    in source
  )
  assert "TRANSITION_ROWS_BY_STATE = {" not in source
  assert "HsmGeneratedRuntimeExternalTransitionRow(" not in source
  assert "EVENT_CANDIDATE_ROWS_BY_STATE = {" in source
  assert 'LEAF_STATES = frozenset({"idle_waiting", "idle_ready", "open", "closed"})' in source
  assert "def state_idle_waiting(ctx, event_id):" in source
  assert 'if event_id == "open_evt":' in source
  assert 'return ("external_transition", "open")' in source
  assert "def state_idle(ctx, event_id):" in source
  assert 'if event_id == "stop_evt":' in source
  assert 'return ("unhandled", None)' in source


def test_load_generated_runtime_keeps_generated_symbols_private_behind_wrapper():
  document = load_hsm_document(_runtime_payload())

  generated_runtime = load_generated_runtime(
    prepare_hsm_generated_runtime_view(document)
  )

  assert generated_runtime.parent_ids == {
    "idle": None,
    "idle_waiting": "idle",
    "idle_ready": "idle",
    "open": None,
    "closed": None,
  }
  assert generated_runtime.ancestry_by_state_id == {
    "idle": ("idle",),
    "idle_waiting": ("idle", "idle_waiting"),
    "idle_ready": ("idle", "idle_ready"),
    "open": ("open",),
    "closed": ("closed",),
  }
  assert generated_runtime.initial_target_ids == {None: "idle", "idle": "idle_waiting"}
  assert generated_runtime.initial_transition_ids == {
    None: "machine_init",
    "idle": "idle_init",
  }
  assert generated_runtime.external_transition_rows_by_state_id["idle"] == (
    HsmGeneratedRuntimeExternalTransitionRow(
      transition_id="idle_to_closed",
      event_id="stop_evt",
      source_id="idle",
      target_id="closed",
    ),
  )
  assert tuple(
    row.candidate_id
    for row in generated_runtime.event_candidate_rows_by_state_id["idle_waiting"]
  ) == ("waiting_to_open", "waiting_to_closed")
  assert generated_runtime.leaf_state_ids == frozenset(
    {"idle_waiting", "idle_ready", "open", "closed"}
  )
  assert generated_runtime.dispatch("idle_waiting", object(), "open_evt") == (
    "external_transition",
    "open",
  )
  assert generated_runtime.dispatch("idle", object(), "stop_evt") == (
    "external_transition",
    "closed",
  )
  assert generated_runtime.dispatch("open", object(), "open_evt") == (
    "unhandled",
    None,
  )
  assert not hasattr(generated_runtime, "state_idle_waiting")


def test_load_generated_runtime_exposes_candidate_metadata_and_resolved_handlers():
  payload = _behavioral_payload()
  document = load_hsm_document(payload)

  generated_runtime = load_generated_runtime(
    prepare_hsm_generated_runtime_view(
      document,
      event_handler_slot_order=derive_event_handler_slot_order(payload),
    )
  )

  assert not hasattr(generated_runtime, "initial_rows_by_owner_id")
  assert generated_runtime.event_candidate_rows_by_state_id["idle"] == (
    HsmGeneratedRuntimeEventCandidateRow(
      candidate_id="idle_ping_internal",
      event_id="ping_evt",
      source_id="idle",
      kind="internal",
      activity_plan_ids=("internal_transition:idle_ping_internal:activities:0",),
    ),
    HsmGeneratedRuntimeEventCandidateRow(
      candidate_id="idle_ping_open",
      event_id="ping_evt",
      source_id="idle",
      kind="external_transition",
      target_id="idle_ping_open_guard",
      guard_plan_id="guard_node:idle_ping_open_guard:guard:0",
      activity_plan_ids=(),
      guard_node_id="idle_ping_open_guard",
      guard_true_branch=HsmGeneratedRuntimeGuardBranchRow(
        branch_id="idle_ping_open_guard_true",
        target_id="open",
        activity_plan_ids=("guard_branch:idle_ping_open_guard_true:activities:0",),
      ),
      guard_false_branch=HsmGeneratedRuntimeGuardBranchRow(
        branch_id="idle_ping_open_guard_false",
        target_id="idle_waiting",
        activity_plan_ids=(),
      ),
    ),
  )
  assert tuple(
    handler.__name__
    for handler in generated_runtime.resolve_activity_handlers(
      generated_runtime.on_initial_plan_ids_by_state_id["idle"]
    )
  ) == ("record_activity",)
  assert tuple(
    handler.__name__
    for handler in generated_runtime.resolve_activity_handlers(
      generated_runtime.event_candidate_rows_by_state_id["idle"][1].guard_true_branch.activity_plan_ids
    )
  ) == ("count_increment",)
  assert generated_runtime.resolve_guard_handler(
    "guard_node:idle_ping_open_guard:guard:0"
  ).__name__ == (
    "allow_guard"
  )


def test_load_generated_runtime_keeps_root_initial_plans_and_callable_privacy():
  payload = _parity_payload()
  document = load_hsm_document(payload)

  generated_runtime = load_generated_runtime(
    prepare_hsm_generated_runtime_view(
      document,
      event_handler_slot_order=derive_event_handler_slot_order(payload),
    )
  )

  assert not hasattr(generated_runtime, "initial_rows_by_owner_id")
  assert tuple(
    row.candidate_id
    for row in generated_runtime.event_candidate_rows_by_state_id["idle"]
  ) == ("idle_ping_internal", "idle_open")
  assert generated_runtime.resolve_guard_handler(
    "guard_node:idle_open_guard:guard:0"
  ).__name__ == (
    "guard_true"
  )
  assert not hasattr(generated_runtime, "state_idle")
  assert not hasattr(generated_runtime, "guard_true")


def test_load_generated_runtime_exposes_guard_node_branch_metadata():
  document = load_hsm_document(_guard_node_payload())

  generated_runtime = load_generated_runtime(
    prepare_hsm_generated_runtime_view(document)
  )

  assert generated_runtime.event_candidate_rows_by_state_id["idle"] == (
    HsmGeneratedRuntimeEventCandidateRow(
      candidate_id="idle_to_job_check",
      event_id="advance_evt",
      source_id="idle",
      kind="external_transition",
      target_id="job_check",
      guard_plan_id="guard_node:job_check:guard:0",
      activity_plan_ids=(),
      guard_node_id="job_check",
      guard_true_branch=HsmGeneratedRuntimeGuardBranchRow(
        branch_id="job_check_true",
        target_id="processing",
        activity_plan_ids=("guard_branch:job_check_true:activities:0",),
      ),
      guard_false_branch=HsmGeneratedRuntimeGuardBranchRow(
        branch_id="job_check_false",
        target_id="blocked",
        activity_plan_ids=("guard_branch:job_check_false:activities:0",),
      ),
    ),
  )
  assert generated_runtime.resolve_guard_handler(
    "guard_node:job_check:guard:0"
  ).__name__ == (
    "guard_job_available"
  )


def test_load_generated_runtime_persists_source_when_output_path_provided(tmp_path):
  document = load_hsm_document(_runtime_payload())
  output_path = tmp_path / "door_machine.py"

  generated_runtime = load_generated_runtime(
    prepare_hsm_generated_runtime_view(document),
    output_path=output_path,
  )

  assert output_path.exists()
  assert output_path.read_text() == generated_runtime.source_code


def test_load_generated_runtime_overwrites_existing_output_file(tmp_path):
  document = load_hsm_document(_runtime_payload())
  output_path = tmp_path / "door_machine.py"
  output_path.parent.mkdir(parents=True, exist_ok=True)
  output_path.write_text("stale")

  generated_runtime = load_generated_runtime(
    prepare_hsm_generated_runtime_view(document),
    output_path=output_path,
  )

  assert output_path.read_text() == generated_runtime.source_code
  assert output_path.read_text() != "stale"


def test_load_generated_runtime_skips_disk_write_in_memory_mode(tmp_path):
  document = load_hsm_document(_runtime_payload())
  output_path = tmp_path / "door_machine.py"

  load_generated_runtime(
    prepare_hsm_generated_runtime_view(document),
    output_path=None,
  )

  assert not output_path.exists()


def test_build_hsm_runtime_persists_generated_runtime_by_default(monkeypatch, tmp_path):
  monkeypatch.setattr(
    hsm_generator_module,
    "DEFAULT_GENERATED_RUNTIME_OUTPUT_DIR",
    tmp_path,
  )
  expected_output = tmp_path / "door_machine.py"

  runtime = build_hsm_runtime(_runtime_payload())
  runtime.init()

  assert expected_output.exists()
  assert runtime.get_snapshot().state_id == "idle_waiting"


def test_build_hsm_runtime_can_skip_persistence(tmp_path):
  output_dir = tmp_path / "build"

  runtime = build_hsm_runtime(
    _runtime_payload(),
    persist_generated_runtime=False,
    generated_runtime_output_dir=output_dir,
  )
  runtime.init()

  assert not any(output_dir.glob("*.py"))
  assert runtime.get_snapshot().state_id == "idle_waiting"


def test_default_generated_runtime_output_dir_uses_visible_root_build_path():
  output_dir = hsm_generator_module.DEFAULT_GENERATED_RUNTIME_OUTPUT_DIR

  assert output_dir.name == "mbse_runtime"
  assert output_dir.parent.name == "build"


def test_default_generated_runtime_output_dir_does_not_use_hidden_mbse_path():
  output_dir = hsm_generator_module.DEFAULT_GENERATED_RUNTIME_OUTPUT_DIR

  assert ".mbse" not in output_dir.parts
  assert "runtime_build" not in output_dir.parts
