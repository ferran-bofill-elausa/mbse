from mbse.runtime.hsm.runtime_model.runtime_model_types import HsmGeneratedRuntimeCallablePlan
from mbse.runtime.hsm.runtime_model.runtime_model_types import HsmGeneratedRuntimeEventCandidateRow
from mbse.runtime.hsm.runtime_model.runtime_model_types import HsmGeneratedRuntimeGuardBranchRow
PARENTS = {"idle": None, "processing": None}

ANCESTRY_BY_STATE = {"idle": ("idle",), "processing": ("processing",)}

INITIAL_TARGETS = {None: "idle"}

INITIAL_TRANSITION_IDS = {None: "machine_init"}

CALLABLE_PLANS_BY_ID = {"guard_branch:idle_decide_guard_false:activities:0": HsmGeneratedRuntimeCallablePlan(plan_id="guard_branch:idle_decide_guard_false:activities:0", module="tests.support.hsm_callable_fixtures", name="trace_guard_false_branch"), "guard_branch:idle_decide_guard_true:activities:0": HsmGeneratedRuntimeCallablePlan(plan_id="guard_branch:idle_decide_guard_true:activities:0", module="tests.support.hsm_callable_fixtures", name="trace_guard_true_branch"), "guard_node:idle_decide_guard:guard:0": HsmGeneratedRuntimeCallablePlan(plan_id="guard_node:idle_decide_guard:guard:0", module="tests.support.hsm_callable_fixtures", name="guard_from_flag"), "state:idle:on_entry:0": HsmGeneratedRuntimeCallablePlan(plan_id="state:idle:on_entry:0", module="tests.support.hsm_callable_fixtures", name="trace_self_entry"), "state:idle:on_exit:0": HsmGeneratedRuntimeCallablePlan(plan_id="state:idle:on_exit:0", module="tests.support.hsm_callable_fixtures", name="trace_self_exit"), "state:processing:on_entry:0": HsmGeneratedRuntimeCallablePlan(plan_id="state:processing:on_entry:0", module="tests.support.hsm_callable_fixtures", name="trace_sibling_entry")}

ON_INITIAL_PLAN_IDS_BY_STATE = {"idle": (), "processing": ()}

ON_ENTRY_PLAN_IDS_BY_STATE = {"idle": ("state:idle:on_entry:0",), "processing": ("state:processing:on_entry:0",)}

ON_EXIT_PLAN_IDS_BY_STATE = {"idle": ("state:idle:on_exit:0",), "processing": ()}

EVENT_CANDIDATE_ROWS_BY_STATE = {"idle": (HsmGeneratedRuntimeEventCandidateRow(candidate_id="idle_decide", event_id="loop_evt", source_id="idle", kind="external_transition", target_id="idle_decide_guard", guard_plan_id="guard_node:idle_decide_guard:guard:0", guard_node_id="idle_decide_guard", guard_true_branch=HsmGeneratedRuntimeGuardBranchRow(branch_id="idle_decide_guard_true", target_id="processing", activity_plan_ids=("guard_branch:idle_decide_guard_true:activities:0",)), guard_false_branch=HsmGeneratedRuntimeGuardBranchRow(branch_id="idle_decide_guard_false", target_id="idle", activity_plan_ids=("guard_branch:idle_decide_guard_false:activities:0",)), activity_plan_ids=()),), "processing": ()}

LEAF_STATES = frozenset({"idle", "processing"})

def state_idle(ctx, event_id):
  if event_id == "loop_evt":
    return ("external_transition", "idle_decide_guard")
  return ("unhandled", None)

def state_processing(ctx, event_id):
  return ("unhandled", None)
