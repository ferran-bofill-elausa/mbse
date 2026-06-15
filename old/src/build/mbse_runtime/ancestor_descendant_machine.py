from mbse.runtime.hsm.runtime_model.runtime_model_types import HsmGeneratedRuntimeCallablePlan
from mbse.runtime.hsm.runtime_model.runtime_model_types import HsmGeneratedRuntimeEventCandidateRow
from mbse.runtime.hsm.runtime_model.runtime_model_types import HsmGeneratedRuntimeGuardBranchRow
PARENTS = {"parent": None, "leaf": "parent", "desc": "parent", "desc_leaf": "desc"}

ANCESTRY_BY_STATE = {"parent": ("parent",), "leaf": ("parent", "leaf"), "desc": ("parent", "desc"), "desc_leaf": ("parent", "desc", "desc_leaf")}

INITIAL_TARGETS = {None: "parent", "parent": "leaf", "desc": "desc_leaf"}

INITIAL_TRANSITION_IDS = {None: "machine_init", "parent": "parent_init", "desc": "desc_init"}

CALLABLE_PLANS_BY_ID = {"external_transition:leaf_to_parent:activities:0": HsmGeneratedRuntimeCallablePlan(plan_id="external_transition:leaf_to_parent:activities:0", module="tests.support.hsm_callable_fixtures", name="trace_transition_activity"), "external_transition:parent_to_desc:activities:0": HsmGeneratedRuntimeCallablePlan(plan_id="external_transition:parent_to_desc:activities:0", module="tests.support.hsm_callable_fixtures", name="trace_transition_activity"), "state:desc:on_entry:0": HsmGeneratedRuntimeCallablePlan(plan_id="state:desc:on_entry:0", module="tests.support.hsm_callable_fixtures", name="trace_desc_entry"), "state:desc:on_initial:0": HsmGeneratedRuntimeCallablePlan(plan_id="state:desc:on_initial:0", module="tests.support.hsm_callable_fixtures", name="trace_desc_initial"), "state:desc_leaf:on_entry:0": HsmGeneratedRuntimeCallablePlan(plan_id="state:desc_leaf:on_entry:0", module="tests.support.hsm_callable_fixtures", name="trace_desc_leaf_entry"), "state:leaf:on_exit:0": HsmGeneratedRuntimeCallablePlan(plan_id="state:leaf:on_exit:0", module="tests.support.hsm_callable_fixtures", name="trace_leaf_exit")}

ON_INITIAL_PLAN_IDS_BY_STATE = {"parent": (), "leaf": (), "desc": ("state:desc:on_initial:0",), "desc_leaf": ()}

ON_ENTRY_PLAN_IDS_BY_STATE = {"parent": (), "leaf": (), "desc": ("state:desc:on_entry:0",), "desc_leaf": ("state:desc_leaf:on_entry:0",)}

ON_EXIT_PLAN_IDS_BY_STATE = {"parent": (), "leaf": ("state:leaf:on_exit:0",), "desc": (), "desc_leaf": ()}

EVENT_CANDIDATE_ROWS_BY_STATE = {"parent": (HsmGeneratedRuntimeEventCandidateRow(candidate_id="parent_to_desc", event_id="down_evt", source_id="parent", kind="external_transition", target_id="desc", activity_plan_ids=("external_transition:parent_to_desc:activities:0",)),), "leaf": (HsmGeneratedRuntimeEventCandidateRow(candidate_id="leaf_to_parent", event_id="up_evt", source_id="leaf", kind="external_transition", target_id="parent", activity_plan_ids=("external_transition:leaf_to_parent:activities:0",)),), "desc": (), "desc_leaf": ()}

LEAF_STATES = frozenset({"leaf", "desc_leaf"})

def state_parent(ctx, event_id):
  if event_id == "down_evt":
    return ("external_transition", "desc")
  return ("unhandled", None)

def state_leaf(ctx, event_id):
  if event_id == "up_evt":
    return ("external_transition", "parent")
  return ("unhandled", None)

def state_desc(ctx, event_id):
  return ("unhandled", None)

def state_desc_leaf(ctx, event_id):
  return ("unhandled", None)
