from __future__ import annotations

"""Activity debugger breakpoint targets and matching."""

from typing import Any

from mbse.model.activity.activity_model import ActivityModel
from mbse_web_viewer.render.activity.activity_render import ActivityRender
from mbse_web_viewer.server.session import ViewerBreakpointTarget


def activityBreakpointIdForStep(model_id: str, step: dict[str, Any]) -> str | None:
  """Return breakpoint id for one Activity runtime step."""

  kind = step["kind"]
  if kind == "initial":
    return _breakpointKey("activity_initial", model_id, step["target_id"])
  if kind == "action":
    return _breakpointKey(
      "activity_action",
      model_id,
      step["action_id"],
      _executableKey(step["executable"]),
    )
  if kind == "pending_decision":
    return _breakpointKey(
      "activity_decision",
      model_id,
      step["decision_id"],
      _executableKey(step["condition"]),
    )
  if kind == "final":
    return _breakpointKey("activity_final", model_id, step["final_id"])
  return None


def buildActivityBreakpointTargets(
  model: ActivityModel,
  rendered: ActivityRender,
  *,
  is_set_by_id: dict[str, bool],
) -> dict[str, ViewerBreakpointTarget]:
  """Build executable Activity breakpoint targets."""

  targets: dict[str, ViewerBreakpointTarget] = {}
  model_id = model.getDocumentId()
  for action in model.getActions():
    executable = action["executable"]
    breakpoint_id = _breakpointKey(
      "activity_action",
      model_id,
      action["id"],
      _executableKey(executable),
    )
    _addTarget(
      targets,
      breakpoint_id=breakpoint_id,
      model_id=model_id,
      label=f"Activity action: {action['label']} / {_executableLabel(executable)}",
      svg_ids=(rendered.getActionId(action["id"]),),
      text_ids=rendered.getActionExecutableTextIds(action["id"], executable),
      is_set_by_id=is_set_by_id,
    )

  for decision in model.getDecisions():
    condition = decision["condition"]
    breakpoint_id = _breakpointKey(
      "activity_decision",
      model_id,
      decision["id"],
      _executableKey(condition),
    )
    _addTarget(
      targets,
      breakpoint_id=breakpoint_id,
      model_id=model_id,
      label=f"Activity decision: {decision['label']} / {_executableLabel(condition)}",
      svg_ids=(rendered.getDecisionId(decision["id"]),),
      text_ids=rendered.getDecisionConditionTextIds(decision["id"], condition),
      is_set_by_id=is_set_by_id,
    )

  for final in model.getFinals():
    breakpoint_id = _breakpointKey("activity_final", model_id, final["id"])
    _addTarget(
      targets,
      breakpoint_id=breakpoint_id,
      model_id=model_id,
      label=f"Activity final: {final['label']}",
      svg_ids=(rendered.getFinalId(final["id"]),),
      text_ids=rendered.getFinalLabelTextIds(final["id"]),
      is_set_by_id=is_set_by_id,
    )
  return targets


def _addTarget(
  targets: dict[str, ViewerBreakpointTarget],
  *,
  breakpoint_id: str,
  model_id: str,
  label: str,
  svg_ids: tuple[str, ...],
  text_ids: tuple[str, ...],
  is_set_by_id: dict[str, bool],
) -> None:
  """Store one Activity breakpoint target when it has a rendered text anchor."""

  if not text_ids:
    return
  targets[breakpoint_id] = ViewerBreakpointTarget(
    id=breakpoint_id,
    model_id=model_id,
    label=label,
    svg_ids=svg_ids,
    text_ids=text_ids,
    is_set=breakpoint_id in is_set_by_id,
    enabled=is_set_by_id.get(breakpoint_id, False),
  )


def _breakpointKey(*parts: object) -> str:
  """Return one stable serialized breakpoint key."""

  return "|".join("" if part is None else str(part) for part in parts)


def _executableKey(executable: dict[str, Any]) -> str:
  """Return one stable executable key."""

  if executable["kind"] == "model":
    return executable["model_id"]
  return f"{executable['module']}.{executable['name']}"


def _executableLabel(executable: dict[str, Any]) -> str:
  """Return one readable executable label."""

  if executable["kind"] == "model":
    return executable["model_id"]
  return executable["name"]
