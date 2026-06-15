from __future__ import annotations


def session_open(ctx) -> None:
  ctx.trace.append("session.entry")
  ctx.session_status = "open"
  ctx.last_action = "session.opened"


def session_choose_initial_phase(ctx) -> None:
  ctx.trace.append("session.initial")
  ctx.session_phase = "selecting_job"
  ctx.last_action = "session.initialized"


def session_select_first_job(ctx) -> None:
  ctx.trace.append("session.initial.activity")
  ctx.selected_job = "ORD-001" if ctx.job_queue > 0 else None
  ctx.last_action = "job.selected"


def session_close(ctx) -> None:
  ctx.trace.append("session.exit")
  ctx.session_status = "closed"
  ctx.last_action = "session.closed"


def idle_ready(ctx) -> None:
  ctx.trace.append("idle.entry")
  ctx.idle_entries = ctx.idle_entries + 1
  ctx.session_phase = "idle"
  ctx.last_action = "idle.ready"


def idle_leave(ctx) -> None:
  ctx.trace.append("idle.exit")
  ctx.idle_exits = ctx.idle_exits + 1
  ctx.last_action = "idle.exiting"


def active_processing(ctx) -> None:
  ctx.trace.append("active.entry")
  ctx.active_entries = ctx.active_entries + 1
  ctx.session_phase = "active"
  ctx.last_action = "active.processing"


def active_pause(ctx) -> None:
  ctx.trace.append("active.exit")
  ctx.active_exits = ctx.active_exits + 1
  ctx.last_action = "active.exiting"


def shutdown_archive(ctx) -> None:
  ctx.trace.append("shutdown.entry")
  ctx.session_phase = "shutdown"
  ctx.last_action = "shutdown.archived"


def idle_health_check(ctx) -> None:
  ctx.trace.append("internal.ping")
  ctx.health_checks = ctx.health_checks + 1
  ctx.last_action = "idle.health_check"


def start_processing_job(ctx) -> None:
  ctx.trace.append("transition.start")
  if ctx.selected_job is None:
    ctx.selected_job = "ORD-001"
  ctx.job_queue = ctx.job_queue - 1
  ctx.last_action = "job.started"


def can_start_processing(ctx) -> bool:
  ctx.trace.append("guard.can_start_processing")
  return ctx.job_queue > 0


def guard_stay_idle(ctx) -> None:
  ctx.trace.append("guard.false_branch")
  ctx.last_action = "guard.false_branch"


def refresh_active_job(ctx) -> None:
  ctx.trace.append("transition.refresh")
  ctx.refresh_count = ctx.refresh_count + 1
  ctx.last_action = "job.refreshed"


def complete_active_job(ctx) -> None:
  ctx.trace.append("transition.stop")
  ctx.completed_jobs = ctx.completed_jobs + 1
  ctx.selected_job = None
  ctx.last_action = "job.completed"


def shutdown_session(ctx) -> None:
  ctx.trace.append("transition.shutdown")
  ctx.shutdown_reason = "operator_request"
  ctx.last_action = "session.shutdown_requested"
