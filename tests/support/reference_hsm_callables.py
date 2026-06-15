from __future__ import annotations


def _trace(ctx, label: str) -> None:
  trace = ctx.trace
  if isinstance(trace, list):
    trace.append(label)


def _make_tracer(label: str):
  def _tracer(ctx) -> None:
    _trace(ctx, label)

  return _tracer


s1_entry = _make_tracer("s1.entry")
s1_initial = _make_tracer("s1.initial")
s1_exit = _make_tracer("s1.exit")
s11_entry = _make_tracer("s11.entry")
s11_initial = _make_tracer("s11.initial")
s11_exit = _make_tracer("s11.exit")
s111_entry = _make_tracer("s111.entry")
s111_initial = _make_tracer("s111.initial")
s111_exit = _make_tracer("s111.exit")
s1111_entry = _make_tracer("s1111.entry")
s1111_initial = _make_tracer("s1111.initial")
s1111_exit = _make_tracer("s1111.exit")
s11111_entry = _make_tracer("s11111.entry")
s11111_exit = _make_tracer("s11111.exit")
s2_entry = _make_tracer("s2.entry")
s2_exit = _make_tracer("s2.exit")
s21_entry = _make_tracer("s21.entry")
s21_exit = _make_tracer("s21.exit")
s211_entry = _make_tracer("s211.entry")
s211_initial = _make_tracer("s211.initial")
s211_exit = _make_tracer("s211.exit")
s2111_entry = _make_tracer("s2111.entry")
s2112_entry = _make_tracer("s2112.entry")
s2112_exit = _make_tracer("s2112.exit")
s3_entry = _make_tracer("s3.entry")
s3_exit = _make_tracer("s3.exit")
s31_entry = _make_tracer("s31.entry")
s31_exit = _make_tracer("s31.exit")
s311_entry = _make_tracer("s311.entry")
s311_exit = _make_tracer("s311.exit")
s4_entry = _make_tracer("s4.entry")
s4_initial = _make_tracer("s4.initial")
s4_exit = _make_tracer("s4.exit")
s41_entry = _make_tracer("s41.entry")
s41_exit = _make_tracer("s41.exit")
s1_to_s211 = _make_tracer("s1.to_s211")
s2111_to_s2112 = _make_tracer("s2111.to_s2112")
s2112_to_s2 = _make_tracer("s2112.to_s2")
s2_to_s21 = _make_tracer("s2.to_s21")
s21_to_s31 = _make_tracer("s21.to_s31")
s31_to_s3 = _make_tracer("s31.to_s3")
s3_to_s311 = _make_tracer("s3.to_s311")
s311_to_s41 = _make_tracer("s311.to_s41")
guard_true_branch = _make_tracer("guard.true_branch")
guard_false_branch = _make_tracer("guard.false_branch")


def guard_self_transition(ctx) -> bool:
  _trace(ctx, "guard.self_transition")
  return bool(ctx.self_transition)
