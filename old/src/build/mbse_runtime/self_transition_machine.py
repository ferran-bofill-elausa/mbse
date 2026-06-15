from mbse.runtime.hsm.runtime_model.runtime_model_types import HsmGeneratedRuntimeCallablePlan
from mbse.runtime.hsm.runtime_model.runtime_model_types import HsmGeneratedRuntimeEventCandidateRow
from mbse.runtime.hsm.runtime_model.runtime_model_types import HsmGeneratedRuntimeGuardBranchRow
PARENTS = {"self_state": None}

ANCESTRY_BY_STATE = {"self_state": ("self_state",)}

INITIAL_TARGETS = {None: "self_state"}

INITIAL_TRANSITION_IDS = {None: "machine_init"}

CALLABLE_PLANS_BY_ID = {"external_transition:self_loop:activities:0": HsmGeneratedRuntimeCallablePlan(plan_id="external_transition:self_loop:activities:0", module="tests.support.hsm_callable_fixtures", name="trace_transition_activity"), "state:self_state:on_entry:0": HsmGeneratedRuntimeCallablePlan(plan_id="state:self_state:on_entry:0", module="tests.support.hsm_callable_fixtures", name="trace_self_entry"), "state:self_state:on_exit:0": HsmGeneratedRuntimeCallablePlan(plan_id="state:self_state:on_exit:0", module="tests.support.hsm_callable_fixtures", name="trace_self_exit")}

ON_INITIAL_PLAN_IDS_BY_STATE = {"self_state": ()}

ON_ENTRY_PLAN_IDS_BY_STATE = {"self_state": ("state:self_state:on_entry:0",)}

ON_EXIT_PLAN_IDS_BY_STATE = {"self_state": ("state:self_state:on_exit:0",)}

EVENT_CANDIDATE_ROWS_BY_STATE = {"self_state": (HsmGeneratedRuntimeEventCandidateRow(candidate_id="self_loop", event_id="loop_evt", source_id="self_state", kind="external_transition", target_id="self_state", activity_plan_ids=("external_transition:self_loop:activities:0",)),)}

LEAF_STATES = frozenset({"self_state"})

def state_self_state(ctx, event_id):
  if event_id == "loop_evt":
    return ("external_transition", "self_state")
  return ("unhandled", None)
