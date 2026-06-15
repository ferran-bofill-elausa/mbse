from mbse.runtime.hsm.runtime_model.runtime_model_types import HsmGeneratedRuntimeCallablePlan
from mbse.runtime.hsm.runtime_model.runtime_model_types import HsmGeneratedRuntimeEventCandidateRow
from mbse.runtime.hsm.runtime_model.runtime_model_types import HsmGeneratedRuntimeGuardBranchRow
PARENTS = {"parent": None, "leaf": "parent", "other": None}

ANCESTRY_BY_STATE = {"parent": ("parent",), "leaf": ("parent", "leaf"), "other": ("other",)}

INITIAL_TARGETS = {None: "parent", "parent": "leaf"}

INITIAL_TRANSITION_IDS = {None: "machine_init", "parent": "parent_init"}

CALLABLE_PLANS_BY_ID = {"external_transition:parent_ping_transition:activities:0": HsmGeneratedRuntimeCallablePlan(plan_id="external_transition:parent_ping_transition:activities:0", module="tests.support.hsm_callable_fixtures", name="trace_transition_activity"), "internal_transition:parent_ping_internal:activities:0": HsmGeneratedRuntimeCallablePlan(plan_id="internal_transition:parent_ping_internal:activities:0", module="tests.support.hsm_callable_fixtures", name="trace_internal_activity")}

ON_INITIAL_PLAN_IDS_BY_STATE = {"parent": (), "leaf": (), "other": ()}

ON_ENTRY_PLAN_IDS_BY_STATE = {"parent": (), "leaf": (), "other": ()}

ON_EXIT_PLAN_IDS_BY_STATE = {"parent": (), "leaf": (), "other": ()}

EVENT_CANDIDATE_ROWS_BY_STATE = {"parent": (HsmGeneratedRuntimeEventCandidateRow(candidate_id="parent_ping_internal", event_id="ping_evt", source_id="parent", kind="internal", activity_plan_ids=("internal_transition:parent_ping_internal:activities:0",)), HsmGeneratedRuntimeEventCandidateRow(candidate_id="parent_ping_transition", event_id="ping_evt", source_id="parent", kind="external_transition", target_id="other", activity_plan_ids=("external_transition:parent_ping_transition:activities:0",))), "leaf": (), "other": ()}

LEAF_STATES = frozenset({"leaf", "other"})

def state_parent(ctx, event_id):
  if event_id == "ping_evt":
    return ("external_transition", "other")
  return ("unhandled", None)

def state_leaf(ctx, event_id):
  return ("unhandled", None)

def state_other(ctx, event_id):
  return ("unhandled", None)
