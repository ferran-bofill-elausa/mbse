from mbse.runtime.hsm.runtime_model.runtime_model_types import HsmGeneratedRuntimeCallablePlan
from mbse.runtime.hsm.runtime_model.runtime_model_types import HsmGeneratedRuntimeEventCandidateRow
from mbse.runtime.hsm.runtime_model.runtime_model_types import HsmGeneratedRuntimeGuardBranchRow
PARENTS = {"s1": None, "s11": "s1", "s111": "s11", "s1111": "s111", "s11111": "s1111", "s2": None, "s21": "s2", "s211": "s21", "s2111": "s211", "s2112": "s211", "s3": None, "s31": "s3", "s311": "s31", "s4": None, "s41": "s4"}

ANCESTRY_BY_STATE = {"s1": ("s1",), "s11": ("s1", "s11"), "s111": ("s1", "s11", "s111"), "s1111": ("s1", "s11", "s111", "s1111"), "s11111": ("s1", "s11", "s111", "s1111", "s11111"), "s2": ("s2",), "s21": ("s2", "s21"), "s211": ("s2", "s21", "s211"), "s2111": ("s2", "s21", "s211", "s2111"), "s2112": ("s2", "s21", "s211", "s2112"), "s3": ("s3",), "s31": ("s3", "s31"), "s311": ("s3", "s31", "s311"), "s4": ("s4",), "s41": ("s4", "s41")}

INITIAL_TARGETS = {None: "s1", "s1": "s11", "s11": "s111", "s111": "s1111", "s1111": "s11111", "s2": "s21", "s21": "s211", "s211": "s2111", "s3": "s31", "s31": "s311", "s4": "s41"}

INITIAL_TRANSITION_IDS = {None: "machine_init", "s1": "s1_init", "s11": "s11_init", "s111": "s111_init", "s1111": "s1111_init", "s2": "s2_init", "s21": "s21_init", "s211": "s211_init", "s3": "s3_init", "s31": "s31_init", "s4": "s4_init"}

CALLABLE_PLANS_BY_ID = {"state:s4:on_entry:0": HsmGeneratedRuntimeCallablePlan(plan_id="state:s4:on_entry:0", module="tests.support.hsm_callable_fixtures", name="inert_entry"), "state:s4:on_exit:0": HsmGeneratedRuntimeCallablePlan(plan_id="state:s4:on_exit:0", module="tests.support.hsm_callable_fixtures", name="inert_exit")}

ON_INITIAL_PLAN_IDS_BY_STATE = {"s1": (), "s11": (), "s111": (), "s1111": (), "s11111": (), "s2": (), "s21": (), "s211": (), "s2111": (), "s2112": (), "s3": (), "s31": (), "s311": (), "s4": (), "s41": ()}

ON_ENTRY_PLAN_IDS_BY_STATE = {"s1": (), "s11": (), "s111": (), "s1111": (), "s11111": (), "s2": (), "s21": (), "s211": (), "s2111": (), "s2112": (), "s3": (), "s31": (), "s311": (), "s4": ("state:s4:on_entry:0",), "s41": ()}

ON_EXIT_PLAN_IDS_BY_STATE = {"s1": (), "s11": (), "s111": (), "s1111": (), "s11111": (), "s2": (), "s21": (), "s211": (), "s2111": (), "s2112": (), "s3": (), "s31": (), "s311": (), "s4": ("state:s4:on_exit:0",), "s41": ()}

EVENT_CANDIDATE_ROWS_BY_STATE = {"s1": (HsmGeneratedRuntimeEventCandidateRow(candidate_id="s1_to_s2111", event_id="transition_evt", source_id="s1", kind="external_transition", target_id="s2111", activity_plan_ids=()),), "s11": (), "s111": (), "s1111": (), "s11111": (), "s2": (), "s21": (), "s211": (), "s2111": (HsmGeneratedRuntimeEventCandidateRow(candidate_id="s2111_to_s2112", event_id="transition_evt", source_id="s2111", kind="external_transition", target_id="s2112", activity_plan_ids=()),), "s2112": (HsmGeneratedRuntimeEventCandidateRow(candidate_id="s2112_to_s2", event_id="transition_evt", source_id="s2112", kind="external_transition", target_id="s2", activity_plan_ids=()),), "s3": (), "s31": (), "s311": (HsmGeneratedRuntimeEventCandidateRow(candidate_id="s311_to_s4", event_id="transition_evt", source_id="s311", kind="external_transition", target_id="s4", activity_plan_ids=()),), "s4": (), "s41": (HsmGeneratedRuntimeEventCandidateRow(candidate_id="s41_to_s41", event_id="transition_evt", source_id="s41", kind="external_transition", target_id="s41", activity_plan_ids=()),)}

LEAF_STATES = frozenset({"s11111", "s2111", "s2112", "s311", "s41"})

def state_s1(ctx, event_id):
  if event_id == "transition_evt":
    return ("external_transition", "s2111")
  return ("unhandled", None)

def state_s11(ctx, event_id):
  return ("unhandled", None)

def state_s111(ctx, event_id):
  return ("unhandled", None)

def state_s1111(ctx, event_id):
  return ("unhandled", None)

def state_s11111(ctx, event_id):
  return ("unhandled", None)

def state_s2(ctx, event_id):
  return ("unhandled", None)

def state_s21(ctx, event_id):
  return ("unhandled", None)

def state_s211(ctx, event_id):
  return ("unhandled", None)

def state_s2111(ctx, event_id):
  if event_id == "transition_evt":
    return ("external_transition", "s2112")
  return ("unhandled", None)

def state_s2112(ctx, event_id):
  if event_id == "transition_evt":
    return ("external_transition", "s2")
  return ("unhandled", None)

def state_s3(ctx, event_id):
  return ("unhandled", None)

def state_s31(ctx, event_id):
  return ("unhandled", None)

def state_s311(ctx, event_id):
  if event_id == "transition_evt":
    return ("external_transition", "s4")
  return ("unhandled", None)

def state_s4(ctx, event_id):
  return ("unhandled", None)

def state_s41(ctx, event_id):
  if event_id == "transition_evt":
    return ("external_transition", "s41")
  return ("unhandled", None)
