from mbse.runtime.hsm.runtime_model.runtime_model_types import HsmGeneratedRuntimeCallablePlan
from mbse.runtime.hsm.runtime_model.runtime_model_types import HsmGeneratedRuntimeEventCandidateRow
from mbse.runtime.hsm.runtime_model.runtime_model_types import HsmGeneratedRuntimeGuardBranchRow
PARENTS = {"parent": None, "child": "parent", "leaf": "child"}

ANCESTRY_BY_STATE = {"parent": ("parent",), "child": ("parent", "child"), "leaf": ("parent", "child", "leaf")}

INITIAL_TARGETS = {None: "parent", "parent": "child", "child": "leaf"}

INITIAL_TRANSITION_IDS = {None: "machine_init", "parent": "parent_init", "child": "child_init"}

CALLABLE_PLANS_BY_ID = {"state:child:on_entry:0": HsmGeneratedRuntimeCallablePlan(plan_id="state:child:on_entry:0", module="tests.support.hsm_callable_fixtures", name="trace_child_entry"), "state:child:on_initial:0": HsmGeneratedRuntimeCallablePlan(plan_id="state:child:on_initial:0", module="tests.support.hsm_callable_fixtures", name="trace_child_initial"), "state:leaf:on_entry:0": HsmGeneratedRuntimeCallablePlan(plan_id="state:leaf:on_entry:0", module="tests.support.hsm_callable_fixtures", name="trace_leaf_entry"), "state:parent:on_entry:0": HsmGeneratedRuntimeCallablePlan(plan_id="state:parent:on_entry:0", module="tests.support.hsm_callable_fixtures", name="trace_parent_entry"), "state:parent:on_initial:0": HsmGeneratedRuntimeCallablePlan(plan_id="state:parent:on_initial:0", module="tests.support.hsm_callable_fixtures", name="trace_parent_initial")}

ON_INITIAL_PLAN_IDS_BY_STATE = {"parent": ("state:parent:on_initial:0",), "child": ("state:child:on_initial:0",), "leaf": ()}

ON_ENTRY_PLAN_IDS_BY_STATE = {"parent": ("state:parent:on_entry:0",), "child": ("state:child:on_entry:0",), "leaf": ("state:leaf:on_entry:0",)}

ON_EXIT_PLAN_IDS_BY_STATE = {"parent": (), "child": (), "leaf": ()}

EVENT_CANDIDATE_ROWS_BY_STATE = {"parent": (), "child": (), "leaf": ()}

LEAF_STATES = frozenset({"leaf"})

def state_parent(ctx, event_id):
  return ("unhandled", None)

def state_child(ctx, event_id):
  return ("unhandled", None)

def state_leaf(ctx, event_id):
  return ("unhandled", None)
