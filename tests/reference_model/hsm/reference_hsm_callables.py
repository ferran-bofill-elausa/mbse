from __future__ import annotations


def _noop(ctx) -> None:
  return


# These reference-model hooks and activities stay as explicit no-ops because the
# runtime tests validate planning and activation order in execution_log, not the
# internal business logic of each callable body.
s1_entry = _noop
s1_initial = _noop
s1_exit = _noop
s11_entry = _noop
s11_initial = _noop
s11_exit = _noop
s111_entry = _noop
s111_initial = _noop
s111_exit = _noop
s1111_entry = _noop
s1111_initial = _noop
s1111_exit = _noop
s11111_entry = _noop
s11111_exit = _noop
s2_entry = _noop
s2_exit = _noop
s21_entry = _noop
s21_exit = _noop
s211_entry = _noop
s211_initial = _noop
s211_exit = _noop
s2111_entry = _noop
s2112_entry = _noop
s2112_exit = _noop
s3_entry = _noop
s3_exit = _noop
s31_entry = _noop
s31_exit = _noop
s311_entry = _noop
s311_exit = _noop
s4_entry = _noop
s4_initial = _noop
s4_exit = _noop
s41_entry = _noop
s41_exit = _noop
s1_to_s211 = _noop
s2111_to_s2112 = _noop
s2112_to_s2 = _noop
s2_to_s21 = _noop
s21_to_s31 = _noop
s31_to_s3 = _noop
s3_to_s311 = _noop
s311_to_s41 = _noop
guard_true_branch = _noop
guard_false_branch = _noop


def guard_choose_transition(ctx) -> bool:
  return bool(ctx.event_parameters["self_transition"])


def trace_ping_value(ctx) -> None:
  ctx.last_ping_value = ctx.event_parameters["value"]


def apply_target_mode(ctx) -> None:
  ctx.current_mode = ctx.event_parameters["target_mode"]


def enqueue_transition(ctx) -> None:
  ctx.send_event("transition")
