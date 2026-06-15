from mbse.runtime.hsm.runtime_model.runtime_model_types import HsmGeneratedRuntimeCallablePlan
from mbse.runtime.hsm.runtime_model.runtime_model_types import HsmGeneratedRuntimeEventCandidateRow
from mbse.runtime.hsm.runtime_model.runtime_model_types import HsmGeneratedRuntimeGuardBranchRow
PARENTS = {"idle": None, "idle_waiting": "idle", "open": "idle"}

ANCESTRY_BY_STATE = {"idle": ("idle",), "idle_waiting": ("idle", "idle_waiting"), "open": ("idle", "open")}

INITIAL_TARGETS = {None: "idle", "idle": "idle_waiting"}

INITIAL_TRANSITION_IDS = {None: "machine_init", "idle": "idle_init"}

CALLABLE_PLANS_BY_ID = {"guard_branch:idle_open_guard_true:activities:0": HsmGeneratedRuntimeCallablePlan(plan_id="guard_branch:idle_open_guard_true:activities:0", module="tests.support.hsm_callable_fixtures", name="trace_transition_activity"), "guard_node:idle_open_guard:guard:0": HsmGeneratedRuntimeCallablePlan(plan_id="guard_node:idle_open_guard:guard:0", module="tests.support.hsm_callable_fixtures", name="guard_true"), "internal_transition:idle_ping_internal:activities:0": HsmGeneratedRuntimeCallablePlan(plan_id="internal_transition:idle_ping_internal:activities:0", module="tests.support.hsm_callable_fixtures", name="trace_internal_activity"), "state:idle:on_entry:0": HsmGeneratedRuntimeCallablePlan(plan_id="state:idle:on_entry:0", module="tests.support.hsm_callable_fixtures", name="trace_parent_entry"), "state:idle:on_initial:0": HsmGeneratedRuntimeCallablePlan(plan_id="state:idle:on_initial:0", module="tests.support.hsm_callable_fixtures", name="trace_parent_initial"), "state:idle_waiting:on_entry:0": HsmGeneratedRuntimeCallablePlan(plan_id="state:idle_waiting:on_entry:0", module="tests.support.hsm_callable_fixtures", name="trace_child_entry"), "state:idle_waiting:on_exit:0": HsmGeneratedRuntimeCallablePlan(plan_id="state:idle_waiting:on_exit:0", module="tests.support.hsm_callable_fixtures", name="trace_leaf_exit"), "state:open:on_entry:0": HsmGeneratedRuntimeCallablePlan(plan_id="state:open:on_entry:0", module="tests.support.hsm_callable_fixtures", name="trace_sibling_entry")}

ON_INITIAL_PLAN_IDS_BY_STATE = {"idle": ("state:idle:on_initial:0",), "idle_waiting": (), "open": ()}

ON_ENTRY_PLAN_IDS_BY_STATE = {"idle": ("state:idle:on_entry:0",), "idle_waiting": ("state:idle_waiting:on_entry:0",), "open": ("state:open:on_entry:0",)}

ON_EXIT_PLAN_IDS_BY_STATE = {"idle": (), "idle_waiting": ("state:idle_waiting:on_exit:0",), "open": ()}

EVENT_CANDIDATE_ROWS_BY_STATE = {"idle": (HsmGeneratedRuntimeEventCandidateRow(candidate_id="idle_open", event_id="open_evt", source_id="idle", kind="external_transition", target_id="idle_open_guard", guard_plan_id="guard_node:idle_open_guard:guard:0", guard_node_id="idle_open_guard", guard_true_branch=HsmGeneratedRuntimeGuardBranchRow(branch_id="idle_open_guard_true", target_id="open", activity_plan_ids=("guard_branch:idle_open_guard_true:activities:0",)), guard_false_branch=HsmGeneratedRuntimeGuardBranchRow(branch_id="idle_open_guard_false", target_id="idle_waiting", activity_plan_ids=()), activity_plan_ids=()), HsmGeneratedRuntimeEventCandidateRow(candidate_id="idle_ping_internal", event_id="ping_evt", source_id="idle", kind="internal", activity_plan_ids=("internal_transition:idle_ping_internal:activities:0",))), "idle_waiting": (), "open": ()}

LEAF_STATES = frozenset({"idle_waiting", "open"})

def state_idle(ctx, event_id):
  if event_id == "open_evt":
    return ("external_transition", "idle_open_guard")
  return ("unhandled", None)

def state_idle_waiting(ctx, event_id):
  return ("unhandled", None)

def state_open(ctx, event_id):
  return ("unhandled", None)
