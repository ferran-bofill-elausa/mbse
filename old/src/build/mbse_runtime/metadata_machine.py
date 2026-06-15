from mbse.runtime.hsm.runtime_model.runtime_model_types import HsmGeneratedRuntimeCallablePlan
from mbse.runtime.hsm.runtime_model.runtime_model_types import HsmGeneratedRuntimeEventCandidateRow
from mbse.runtime.hsm.runtime_model.runtime_model_types import HsmGeneratedRuntimeGuardBranchRow
PARENTS = {"idle": None}

ANCESTRY_BY_STATE = {"idle": ("idle",)}

INITIAL_TARGETS = {None: "idle"}

INITIAL_TRANSITION_IDS = {None: "machine_init"}

CALLABLE_PLANS_BY_ID = {}

ON_INITIAL_PLAN_IDS_BY_STATE = {"idle": ()}

ON_ENTRY_PLAN_IDS_BY_STATE = {"idle": ()}

ON_EXIT_PLAN_IDS_BY_STATE = {"idle": ()}

EVENT_CANDIDATE_ROWS_BY_STATE = {"idle": ()}

LEAF_STATES = frozenset({"idle"})

def state_idle(ctx, event_id):
  return ("unhandled", None)
