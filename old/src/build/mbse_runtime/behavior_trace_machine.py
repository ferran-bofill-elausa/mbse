from mbse.runtime.hsm.runtime_model.runtime_model_types import HsmGeneratedRuntimeCallablePlan
from mbse.runtime.hsm.runtime_model.runtime_model_types import HsmGeneratedRuntimeEventCandidateRow
from mbse.runtime.hsm.runtime_model.runtime_model_types import HsmGeneratedRuntimeGuardBranchRow
PARENTS = {"session": None, "idle": "session", "active": "session", "shutdown": None}

ANCESTRY_BY_STATE = {"session": ("session",), "idle": ("session", "idle"), "active": ("session", "active"), "shutdown": ("shutdown",)}

INITIAL_TARGETS = {None: "session", "session": "idle"}

INITIAL_TRANSITION_IDS = {None: "machine_init", "session": "session_init"}

CALLABLE_PLANS_BY_ID = {"external_transition:active_refresh:activities:0": HsmGeneratedRuntimeCallablePlan(plan_id="external_transition:active_refresh:activities:0", module="test_hsm.activities", name="refresh_active_job"), "external_transition:active_to_idle:activities:0": HsmGeneratedRuntimeCallablePlan(plan_id="external_transition:active_to_idle:activities:0", module="test_hsm.activities", name="complete_active_job"), "external_transition:session_to_shutdown:activities:0": HsmGeneratedRuntimeCallablePlan(plan_id="external_transition:session_to_shutdown:activities:0", module="test_hsm.activities", name="shutdown_session"), "guard_branch:job_check_false:activities:0": HsmGeneratedRuntimeCallablePlan(plan_id="guard_branch:job_check_false:activities:0", module="test_hsm.activities", name="guard_stay_idle"), "guard_branch:job_check_true:activities:0": HsmGeneratedRuntimeCallablePlan(plan_id="guard_branch:job_check_true:activities:0", module="test_hsm.activities", name="start_processing_job"), "guard_node:job_check:guard:0": HsmGeneratedRuntimeCallablePlan(plan_id="guard_node:job_check:guard:0", module="test_hsm.activities", name="can_start_processing"), "internal_transition:idle_ping_internal:activities:0": HsmGeneratedRuntimeCallablePlan(plan_id="internal_transition:idle_ping_internal:activities:0", module="test_hsm.activities", name="idle_health_check"), "state:active:on_entry:0": HsmGeneratedRuntimeCallablePlan(plan_id="state:active:on_entry:0", module="test_hsm.activities", name="active_processing"), "state:active:on_exit:0": HsmGeneratedRuntimeCallablePlan(plan_id="state:active:on_exit:0", module="test_hsm.activities", name="active_pause"), "state:idle:on_entry:0": HsmGeneratedRuntimeCallablePlan(plan_id="state:idle:on_entry:0", module="test_hsm.activities", name="idle_ready"), "state:idle:on_exit:0": HsmGeneratedRuntimeCallablePlan(plan_id="state:idle:on_exit:0", module="test_hsm.activities", name="idle_leave"), "state:session:on_entry:0": HsmGeneratedRuntimeCallablePlan(plan_id="state:session:on_entry:0", module="test_hsm.activities", name="session_open"), "state:session:on_exit:0": HsmGeneratedRuntimeCallablePlan(plan_id="state:session:on_exit:0", module="test_hsm.activities", name="session_close"), "state:session:on_initial:0": HsmGeneratedRuntimeCallablePlan(plan_id="state:session:on_initial:0", module="test_hsm.activities", name="session_choose_initial_phase"), "state:session:on_initial:1": HsmGeneratedRuntimeCallablePlan(plan_id="state:session:on_initial:1", module="test_hsm.activities", name="session_select_first_job"), "state:shutdown:on_entry:0": HsmGeneratedRuntimeCallablePlan(plan_id="state:shutdown:on_entry:0", module="test_hsm.activities", name="shutdown_archive")}

ON_INITIAL_PLAN_IDS_BY_STATE = {"session": ("state:session:on_initial:0", "state:session:on_initial:1"), "idle": (), "active": (), "shutdown": ()}

ON_ENTRY_PLAN_IDS_BY_STATE = {"session": ("state:session:on_entry:0",), "idle": ("state:idle:on_entry:0",), "active": ("state:active:on_entry:0",), "shutdown": ("state:shutdown:on_entry:0",)}

ON_EXIT_PLAN_IDS_BY_STATE = {"session": ("state:session:on_exit:0",), "idle": ("state:idle:on_exit:0",), "active": ("state:active:on_exit:0",), "shutdown": ()}

EVENT_CANDIDATE_ROWS_BY_STATE = {"session": (HsmGeneratedRuntimeEventCandidateRow(candidate_id="session_to_shutdown", event_id="shutdown_evt", source_id="session", kind="external_transition", target_id="shutdown", activity_plan_ids=("external_transition:session_to_shutdown:activities:0",)),), "idle": (HsmGeneratedRuntimeEventCandidateRow(candidate_id="idle_to_job_check", event_id="start_evt", source_id="idle", kind="external_transition", target_id="job_check", guard_plan_id="guard_node:job_check:guard:0", guard_node_id="job_check", guard_true_branch=HsmGeneratedRuntimeGuardBranchRow(branch_id="job_check_true", target_id="active", activity_plan_ids=("guard_branch:job_check_true:activities:0",)), guard_false_branch=HsmGeneratedRuntimeGuardBranchRow(branch_id="job_check_false", target_id="idle", activity_plan_ids=("guard_branch:job_check_false:activities:0",)), activity_plan_ids=()), HsmGeneratedRuntimeEventCandidateRow(candidate_id="idle_ping_internal", event_id="ping_evt", source_id="idle", kind="internal", activity_plan_ids=("internal_transition:idle_ping_internal:activities:0",))), "active": (HsmGeneratedRuntimeEventCandidateRow(candidate_id="active_refresh", event_id="refresh_evt", source_id="active", kind="external_transition", target_id="active", activity_plan_ids=("external_transition:active_refresh:activities:0",)), HsmGeneratedRuntimeEventCandidateRow(candidate_id="active_to_idle", event_id="stop_evt", source_id="active", kind="external_transition", target_id="idle", activity_plan_ids=("external_transition:active_to_idle:activities:0",))), "shutdown": ()}

LEAF_STATES = frozenset({"idle", "active", "shutdown"})

def state_session(ctx, event_id):
  if event_id == "shutdown_evt":
    return ("external_transition", "shutdown")
  return ("unhandled", None)

def state_idle(ctx, event_id):
  if event_id == "start_evt":
    return ("external_transition", "job_check")
  return ("unhandled", None)

def state_active(ctx, event_id):
  if event_id == "refresh_evt":
    return ("external_transition", "active")
  if event_id == "stop_evt":
    return ("external_transition", "idle")
  return ("unhandled", None)

def state_shutdown(ctx, event_id):
  return ("unhandled", None)
