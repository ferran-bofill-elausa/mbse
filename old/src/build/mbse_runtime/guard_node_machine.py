from mbse.runtime.hsm.runtime_model.runtime_model_types import HsmGeneratedRuntimeCallablePlan
from mbse.runtime.hsm.runtime_model.runtime_model_types import HsmGeneratedRuntimeEventCandidateRow
from mbse.runtime.hsm.runtime_model.runtime_model_types import HsmGeneratedRuntimeGuardBranchRow
PARENTS = {"idle": None, "processing": None, "blocked": None}

ANCESTRY_BY_STATE = {"idle": ("idle",), "processing": ("processing",), "blocked": ("blocked",)}

INITIAL_TARGETS = {None: "idle"}

INITIAL_TRANSITION_IDS = {None: "machine_init"}

CALLABLE_PLANS_BY_ID = {"guard_branch:job_check_false:activities:0": HsmGeneratedRuntimeCallablePlan(plan_id="guard_branch:job_check_false:activities:0", module="tests.support.hsm_callable_fixtures", name="trace_guard_false_branch"), "guard_branch:job_check_true:activities:0": HsmGeneratedRuntimeCallablePlan(plan_id="guard_branch:job_check_true:activities:0", module="tests.support.hsm_callable_fixtures", name="trace_guard_true_branch"), "guard_node:job_check:guard:0": HsmGeneratedRuntimeCallablePlan(plan_id="guard_node:job_check:guard:0", module="tests.support.hsm_callable_fixtures", name="guard_job_available"), "state:blocked:on_entry:0": HsmGeneratedRuntimeCallablePlan(plan_id="state:blocked:on_entry:0", module="tests.support.hsm_callable_fixtures", name="trace_desc_entry"), "state:idle:on_exit:0": HsmGeneratedRuntimeCallablePlan(plan_id="state:idle:on_exit:0", module="tests.support.hsm_callable_fixtures", name="trace_leaf_exit"), "state:processing:on_entry:0": HsmGeneratedRuntimeCallablePlan(plan_id="state:processing:on_entry:0", module="tests.support.hsm_callable_fixtures", name="trace_sibling_entry")}

ON_INITIAL_PLAN_IDS_BY_STATE = {"idle": (), "processing": (), "blocked": ()}

ON_ENTRY_PLAN_IDS_BY_STATE = {"idle": (), "processing": ("state:processing:on_entry:0",), "blocked": ("state:blocked:on_entry:0",)}

ON_EXIT_PLAN_IDS_BY_STATE = {"idle": ("state:idle:on_exit:0",), "processing": (), "blocked": ()}

EVENT_CANDIDATE_ROWS_BY_STATE = {"idle": (HsmGeneratedRuntimeEventCandidateRow(candidate_id="idle_to_job_check", event_id="advance_evt", source_id="idle", kind="external_transition", target_id="job_check", guard_plan_id="guard_node:job_check:guard:0", guard_node_id="job_check", guard_true_branch=HsmGeneratedRuntimeGuardBranchRow(branch_id="job_check_true", target_id="processing", activity_plan_ids=("guard_branch:job_check_true:activities:0",)), guard_false_branch=HsmGeneratedRuntimeGuardBranchRow(branch_id="job_check_false", target_id="blocked", activity_plan_ids=("guard_branch:job_check_false:activities:0",)), activity_plan_ids=()),), "processing": (), "blocked": ()}

LEAF_STATES = frozenset({"idle", "processing", "blocked"})

def state_idle(ctx, event_id):
  if event_id == "advance_evt":
    return ("external_transition", "job_check")
  return ("unhandled", None)

def state_processing(ctx, event_id):
  return ("unhandled", None)

def state_blocked(ctx, event_id):
  return ("unhandled", None)
