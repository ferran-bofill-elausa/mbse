from __future__ import annotations


def is_ready(ctx) -> bool:
  """Return whether the reference activity should execute its action path."""

  return getattr(ctx, "is_ready", True)


def prepare_output(ctx) -> None:
  """Record that the reference activity action was executed."""

  ctx.output_prepared = True


def is_full_reset_requested(ctx) -> bool:
  """Return whether the HSM requested a full context reset."""

  return bool(getattr(ctx, "full_reset_requested", False))


def reset_context_variables(ctx) -> None:
  """Reset shared context variables to their authored defaults."""

  ctx.last_ping_value = 0
  ctx.current_mode = "normal"
  ctx.is_ready = True
  ctx.output_prepared = False
  ctx.full_reset_requested = False


def set_result_true(ctx) -> None:
  """Set the shared model-call result variable to true."""

  ctx.result = True


def return_not_bool(ctx) -> str:
  """Return an invalid decision result for runtime error tests."""

  return "not-bool"
