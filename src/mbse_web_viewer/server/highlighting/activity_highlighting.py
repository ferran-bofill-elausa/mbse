from __future__ import annotations

"""Activity runtime highlighting for viewer sessions."""

from typing import Any

from mbse.runtime.activity.activity_runtime import ActivityRuntimeTrace
from mbse.runtime.runtime import Runtime
from mbse_web_viewer.render.activity.activity_render import ActivityRender
from mbse_web_viewer.server.session import ViewerHighlight


def buildActivityHighlight(
  runtime: Runtime,
  model_id: str,
  rendered: ActivityRender,
) -> ViewerHighlight:
  """Resolve one Activity runtime trace into SVG ids for highlighting."""

  trace = _getActivityTrace(runtime, model_id)
  current_step = _getActivityCallStackStep(runtime, model_id)
  if trace is None and current_step is None:
    return _emptyHighlight()

  state_ids: list[str] = []
  transition_ids: list[str] = []
  text_ids: list[str] = []
  if trace is not None:
    state_ids, transition_ids, text_ids = _buildActivityTraceIds(trace, rendered)

  current_transition_ids: tuple[str, ...] = ()
  current_text_ids: tuple[str, ...] = ()
  if current_step is not None:
    current_transition_ids, current_text_ids = _buildActivityCurrentIds(
      current_step,
      rendered,
    )

  return ViewerHighlight(
    state_ids=tuple(dict.fromkeys(state_ids)),
    transition_ids=tuple(dict.fromkeys(transition_ids)),
    text_ids=tuple(dict.fromkeys(text_ids)),
    current_transition_ids=tuple(dict.fromkeys(current_transition_ids)),
    current_text_ids=tuple(dict.fromkeys(current_text_ids)),
  )


def _getActivityTrace(runtime: Runtime, model_id: str) -> ActivityRuntimeTrace | None:
  """Return the latest Activity trace for one model id."""

  traces = [
    wrapped_trace["trace"]
    for wrapped_trace in runtime.getExecutionLog()
    if wrapped_trace["runtime"] == "activity" and wrapped_trace["model_id"] == model_id
  ]
  return traces[-1] if traces else None


def _getActivityCallStackStep(runtime: Runtime, model_id: str) -> dict[str, Any] | None:
  """Return one Activity model's current call-stack step."""

  call_stack = runtime.getCallStack()
  while call_stack is not None:
    if call_stack["runtime"] == "activity" and call_stack["model_id"] == model_id:
      return call_stack["step"]
    call_stack = call_stack["nested"]
  return None


def _buildActivityTraceIds(
  trace: ActivityRuntimeTrace,
  rendered: ActivityRender,
) -> tuple[list[str], list[str], list[str]]:
  """Resolve completed Activity trace entries to SVG ids."""

  state_ids: list[str] = []
  transition_ids: list[str] = []
  text_ids: list[str] = []
  for entry in trace["entries"]:
    kind = entry["kind"]
    if kind == "initial":
      transition_ids.append(rendered.getInitialTransitionId())
      continue
    if kind == "action":
      action_id = entry["action_id"]
      action_svg_id = rendered.getActionId(action_id)
      transition_id = rendered.getActionTransitionId(action_id)
      state_ids.append(action_svg_id)
      transition_ids.append(transition_id)
      text_ids.extend(_ownedTextIds(
        rendered.getActionOwnedIds(action_id),
        action_svg_id,
      ))
      text_ids.extend(_ownedTextIds(
        rendered.getTransitionOwnedIds(transition_id),
        transition_id,
      ))
      continue
    if kind == "decision":
      decision_id = entry["decision_id"]
      edge_id = rendered.getDecisionTransitionId(decision_id, outcome=entry["result"])
      decision_svg_id = rendered.getDecisionId(decision_id)
      state_ids.append(decision_svg_id)
      transition_ids.append(edge_id)
      text_ids.extend(_ownedTextIds(
        rendered.getDecisionOwnedIds(decision_id),
        decision_svg_id,
      ))
      text_ids.extend(_ownedTextIds(rendered.getTransitionOwnedIds(edge_id), edge_id))
      continue
    if kind == "final":
      final_id = entry["final_id"]
      final_svg_id = rendered.getFinalId(final_id)
      state_ids.append(final_svg_id)
      text_ids.extend(_ownedTextIds(
        rendered.getFinalOwnedIds(final_id),
        final_svg_id,
      ))
  return state_ids, transition_ids, text_ids


def _buildActivityCurrentIds(
  current_step: dict[str, Any],
  rendered: ActivityRender,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
  """Resolve the live Activity debugger step to SVG ids."""

  kind = current_step["kind"]
  if kind == "initial":
    return (
      rendered.getInitialTransitionOwnedIds(),
      (),
    )
  if kind == "action":
    action_id = current_step["action_id"]
    action_svg_id = rendered.getActionId(action_id)
    transition_id = rendered.getActionTransitionId(action_id)
    return (
      (action_svg_id, transition_id),
      _ownedTextIds(rendered.getActionOwnedIds(action_id), action_svg_id)
      + _ownedTextIds(rendered.getTransitionOwnedIds(transition_id), transition_id),
    )
  if kind == "pending_decision":
    decision_id = current_step["decision_id"]
    decision_svg_id = rendered.getDecisionId(decision_id)
    return (
      (decision_svg_id,),
      _ownedTextIds(rendered.getDecisionOwnedIds(decision_id), decision_svg_id),
    )
  if kind == "final":
    final_id = current_step["final_id"]
    final_svg_id = rendered.getFinalId(final_id)
    return (
      (final_svg_id,),
      _ownedTextIds(rendered.getFinalOwnedIds(final_id), final_svg_id),
    )
  return (), ()


def _ownedTextIds(owned_ids: tuple[str, ...], *visual_ids: str) -> tuple[str, ...]:
  """Return ownership ids that should be highlighted as text."""

  visual_id_set = set(visual_ids)
  return tuple(element_id for element_id in owned_ids if element_id not in visual_id_set)


def _emptyHighlight() -> ViewerHighlight:
  """Return an empty highlight payload."""

  return ViewerHighlight(
    state_ids=(),
    transition_ids=(),
    text_ids=(),
    current_transition_ids=(),
    current_text_ids=(),
  )
