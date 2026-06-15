from __future__ import annotations


def _trace(ctx, label: str) -> None:
  trace = ctx.trace
  if isinstance(trace, list):
    trace.append(label)


def record_activity(ctx) -> None:
  _trace(ctx, "activity")


def allow_guard(ctx) -> bool:
  return bool(ctx.allow)


def inert_entry(ctx) -> None:
  return None


def inert_exit(ctx) -> None:
  return None


def count_increment(ctx) -> None:
  return None


def mode_idle(ctx) -> None:
  return None


def enter_parent(ctx) -> None:
  return None


def exit_parent(ctx) -> None:
  return None


def enter_sibling(ctx) -> None:
  return None


def bad_activity_no_args() -> None:
  return None


def bad_guard_two_args(ctx, extra) -> bool:
  return True


def bad_guard_truthy(ctx) -> int:
  return 1


def trace_parent_entry(ctx) -> None:
  _trace(ctx, "parent.entry")


def trace_parent_exit(ctx) -> None:
  _trace(ctx, "parent.exit")


def trace_parent_initial(ctx) -> None:
  _trace(ctx, "parent.initial")


def trace_parent_initial_activity(ctx) -> None:
  _trace(ctx, "parent.initial.activity")


def trace_root_initial_activity(ctx) -> None:
  _trace(ctx, "root.initial.activity")


def trace_child_entry(ctx) -> None:
  _trace(ctx, "child.entry")


def trace_child_initial(ctx) -> None:
  _trace(ctx, "child.initial")


def trace_child_initial_activity(ctx) -> None:
  _trace(ctx, "child.initial.activity")


def trace_leaf_entry(ctx) -> None:
  _trace(ctx, "leaf.entry")


def trace_leaf_exit(ctx) -> None:
  _trace(ctx, "leaf.exit")


def trace_sibling_entry(ctx) -> None:
  _trace(ctx, "sibling.entry")


def trace_desc_entry(ctx) -> None:
  _trace(ctx, "desc.entry")


def trace_desc_initial(ctx) -> None:
  _trace(ctx, "desc.initial")


def trace_desc_initial_activity(ctx) -> None:
  _trace(ctx, "desc.initial.activity")


def trace_desc_leaf_entry(ctx) -> None:
  _trace(ctx, "desc.leaf.entry")


def trace_self_entry(ctx) -> None:
  _trace(ctx, "self.entry")


def trace_self_exit(ctx) -> None:
  _trace(ctx, "self.exit")


def trace_internal_activity(ctx) -> None:
  _trace(ctx, "internal.activity")


def trace_transition_activity(ctx) -> None:
  _trace(ctx, "transition.activity")


def guard_from_flag(ctx) -> bool:
  _trace(ctx, "guard.flag")
  return bool(ctx.guard_flag)


def guard_true(ctx) -> bool:
  _trace(ctx, "guard.true")
  return True


def guard_job_available(ctx) -> bool:
  _trace(ctx, "guard.job_available")
  return ctx.job_queue > 0


def trace_guard_true_branch(ctx) -> None:
  _trace(ctx, "guard.true_branch")


def trace_guard_false_branch(ctx) -> None:
  _trace(ctx, "guard.false_branch")
