from mbse.runtime.hsm.runtime_model.runtime_model_types import HsmGeneratedRuntimeCallablePlan
from mbse.runtime.hsm.runtime_model.runtime_model_types import HsmGeneratedRuntimeEventCandidateRow
from mbse.runtime.hsm.runtime_model.runtime_model_types import HsmGeneratedRuntimeGuardBranchRow
PARENTS = {"parent": None, "leaf": "parent", "sibling": "parent", "other": None}

ANCESTRY_BY_STATE = {"parent": ("parent",), "leaf": ("parent", "leaf"), "sibling": ("parent", "sibling"), "other": ("other",)}

INITIAL_TARGETS = {None: "parent", "parent": "leaf"}

INITIAL_TRANSITION_IDS = {None: "machine_init", "parent": "parent_init"}

CALLABLE_PLANS_BY_ID = {"guard_branch:leaf_guarded_guard_false:activities:0": HsmGeneratedRuntimeCallablePlan(plan_id="guard_branch:leaf_guarded_guard_false:activities:0", module="tests.support.hsm_callable_fixtures", name="trace_guard_false_branch"), "guard_branch:leaf_guarded_guard_true:activities:0": HsmGeneratedRuntimeCallablePlan(plan_id="guard_branch:leaf_guarded_guard_true:activities:0", module="tests.support.hsm_callable_fixtures", name="trace_transition_activity"), "guard_branch:parent_fallback_guard_true:activities:0": HsmGeneratedRuntimeCallablePlan(plan_id="guard_branch:parent_fallback_guard_true:activities:0", module="tests.support.hsm_callable_fixtures", name="trace_transition_activity"), "guard_node:leaf_guarded_guard:guard:0": HsmGeneratedRuntimeCallablePlan(plan_id="guard_node:leaf_guarded_guard:guard:0", module="tests.support.hsm_callable_fixtures", name="bad_guard_truthy"), "guard_node:parent_fallback_guard:guard:0": HsmGeneratedRuntimeCallablePlan(plan_id="guard_node:parent_fallback_guard:guard:0", module="tests.support.hsm_callable_fixtures", name="guard_true"), "state:leaf:on_exit:0": HsmGeneratedRuntimeCallablePlan(plan_id="state:leaf:on_exit:0", module="tests.support.hsm_callable_fixtures", name="trace_leaf_exit"), "state:sibling:on_entry:0": HsmGeneratedRuntimeCallablePlan(plan_id="state:sibling:on_entry:0", module="tests.support.hsm_callable_fixtures", name="trace_sibling_entry")}

ON_INITIAL_PLAN_IDS_BY_STATE = {"parent": (), "leaf": (), "sibling": (), "other": ()}

ON_ENTRY_PLAN_IDS_BY_STATE = {"parent": (), "leaf": (), "sibling": ("state:sibling:on_entry:0",), "other": ()}

ON_EXIT_PLAN_IDS_BY_STATE = {"parent": (), "leaf": ("state:leaf:on_exit:0",), "sibling": (), "other": ()}

EVENT_CANDIDATE_ROWS_BY_STATE = {"parent": (HsmGeneratedRuntimeEventCandidateRow(candidate_id="parent_fallback", event_id="advance_evt", source_id="parent", kind="external_transition", target_id="parent_fallback_guard", guard_plan_id="guard_node:parent_fallback_guard:guard:0", guard_node_id="parent_fallback_guard", guard_true_branch=HsmGeneratedRuntimeGuardBranchRow(branch_id="parent_fallback_guard_true", target_id="sibling", activity_plan_ids=("guard_branch:parent_fallback_guard_true:activities:0",)), guard_false_branch=HsmGeneratedRuntimeGuardBranchRow(branch_id="parent_fallback_guard_false", target_id="parent", activity_plan_ids=()), activity_plan_ids=()),), "leaf": (HsmGeneratedRuntimeEventCandidateRow(candidate_id="leaf_guarded", event_id="advance_evt", source_id="leaf", kind="external_transition", target_id="leaf_guarded_guard", guard_plan_id="guard_node:leaf_guarded_guard:guard:0", guard_node_id="leaf_guarded_guard", guard_true_branch=HsmGeneratedRuntimeGuardBranchRow(branch_id="leaf_guarded_guard_true", target_id="sibling", activity_plan_ids=("guard_branch:leaf_guarded_guard_true:activities:0",)), guard_false_branch=HsmGeneratedRuntimeGuardBranchRow(branch_id="leaf_guarded_guard_false", target_id="leaf", activity_plan_ids=("guard_branch:leaf_guarded_guard_false:activities:0",)), activity_plan_ids=()),), "sibling": (), "other": ()}

LEAF_STATES = frozenset({"leaf", "sibling", "other"})

def state_parent(ctx, event_id):
  if event_id == "advance_evt":
    return ("external_transition", "parent_fallback_guard")
  return ("unhandled", None)

def state_leaf(ctx, event_id):
  if event_id == "advance_evt":
    return ("external_transition", "leaf_guarded_guard")
  return ("unhandled", None)

def state_sibling(ctx, event_id):
  return ("unhandled", None)

def state_other(ctx, event_id):
  return ("unhandled", None)
