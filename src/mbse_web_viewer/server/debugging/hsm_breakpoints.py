from __future__ import annotations

"""HSM debugger breakpoint targets and matching."""

from typing import Any

from mbse.model.hsm.hsm_model import HsmModel
from mbse.runtime.hsm.hsm_runtime import HsmRuntimePendingExecutionTypeAlias
from mbse_web_viewer.render.hsm.hsm_render import HsmRender
from mbse_web_viewer.server.session import ViewerBreakpointTarget


def hsmBreakpointIdForStep(
  step: HsmRuntimePendingExecutionTypeAlias,
  *,
  event_id: str | None,
) -> str | None:
  """Return breakpoint id for one HSM runtime step."""

  kind = step["kind"]
  if kind in {"on_entry", "on_exit"}:
    return breakpointKey(kind, step["source_state_id"], executableKey(step["activity"]))
  if kind == "change_active_state":
    return breakpointKey(kind, step["target_state_id"])
  if kind == "initial_transition" and step["activity"] is not None:
    return breakpointKey(
      kind,
      step["source_state_id"],
      step["target_state_id"],
      executableKey(step["activity"]),
    )
  if kind == "internal_transition" and event_id is not None and step["activity"] is not None:
    return breakpointKey(
      kind,
      step["source_state_id"],
      event_id,
      executableKey(step["activity"]),
    )
  if kind == "external_transition" and event_id is not None and step["activity"] is not None:
    return breakpointKey(
      kind,
      step["source_state_id"],
      event_id,
      step["target_state_id"],
      executableKey(step["activity"]),
    )
  if kind == "guarded_transition" and event_id is not None and step["activity"] is not None:
    return breakpointKey(
      kind,
      step["source_state_id"],
      event_id,
      "guard",
      executableKey(step["activity"]),
    )
  if kind == "guard_branch_transition" and event_id is not None and step["activity"] is not None:
    return breakpointKey(
      kind,
      step["source_state_id"],
      event_id,
      str(step["result"]),
      step["target_state_id"],
      executableKey(step["activity"]),
    )
  if kind == "pending_guard_condition" and event_id is not None:
    return breakpointKey(
      "guard_condition",
      step["source_state_id"],
      event_id,
      executableKey(step["guard_activity"]),
    )
  return None


def buildHsmBreakpointTargets(
  model: HsmModel,
  rendered: HsmRender,
  *,
  is_set_by_id: dict[str, bool],
) -> dict[str, ViewerBreakpointTarget]:
  """Build executable HSM breakpoint targets."""

  targets: dict[str, ViewerBreakpointTarget] = {}
  for state in model.iterStates():
    state_id = state["id"]
    _addTarget(
      targets,
      breakpoint_id=breakpointKey("change_active_state", state_id),
      model_id=model.getDocumentId(),
      label=f"Enter state: {model.getStateLabel(state_id)}",
      svg_ids=(rendered.getStateId(state_id),),
      text_ids=rendered.getStateLabelTextIds(state_id),
      is_set_by_id=is_set_by_id,
    )

    for section_name, activities in (
      ("on_entry", model.getStateOnEntry(state_id)),
      ("on_exit", model.getStateOnExit(state_id)),
    ):
      for activity in activities:
        _addTarget(
          targets,
          breakpoint_id=breakpointKey(section_name, state_id, executableKey(activity)),
          model_id=model.getDocumentId(),
          label=(
            f"{formatHookName(section_name)}: "
            f"{model.getStateLabel(state_id)} / {executableLabel(activity)}"
          ),
          svg_ids=(rendered.getStateId(state_id),),
          text_ids=rendered.getStateHookActivityTextIds(state_id, section_name, activity),
          is_set_by_id=is_set_by_id,
        )

    for transition in model.getStateInternalTransitions(state_id):
      event_id = transition["event_id"]
      for activity in transition.get("activities", []):
        transition_ids = rendered.getInternalTransitionIds(state_id, event_id)
        text_ids: list[str] = []
        for transition_id in transition_ids:
          text_ids.extend(rendered.getInternalTransitionActivityTextIds(transition_id, activity))
        _addTarget(
          targets,
          breakpoint_id=breakpointKey(
            "internal_transition",
            state_id,
            event_id,
            executableKey(activity),
          ),
          model_id=model.getDocumentId(),
          label=(
            "Internal transition: "
            f"{model.getStateLabel(state_id)} / {event_id} / {executableLabel(activity)}"
          ),
          svg_ids=transition_ids,
          text_ids=tuple(text_ids),
          is_set_by_id=is_set_by_id,
        )

    if model.hasStateInitialTransition(state_id):
      target_state_id = model.getStateInitialTargetId(state_id)
      transition_id = rendered.getInitialTransitionId(state_id)
      for activity in model.getStateInitialTransitionActivities(state_id):
        _addTarget(
          targets,
          breakpoint_id=breakpointKey(
            "initial_transition",
            state_id,
            target_state_id,
            executableKey(activity),
          ),
          model_id=model.getDocumentId(),
          label=(
            "Initial transition: "
            f"{model.getStateLabel(state_id)} -> "
            f"{model.getStateLabel(target_state_id)} / {executableLabel(activity)}"
          ),
          svg_ids=(transition_id,),
          text_ids=rendered.getInitialTransitionActivityTextIds(transition_id, activity),
          is_set_by_id=is_set_by_id,
        )

    for transition in model.getOutgoingExternalTransitions(state_id):
      _appendExternalTargets(targets, model, rendered, state_id, transition, is_set_by_id)

  return targets


def breakpointKey(*parts: object) -> str:
  """Return one stable serialized breakpoint key."""

  return "|".join("" if part is None else str(part) for part in parts)


def executableKey(activity: dict[str, Any]) -> str:
  """Return one stable executable key matching render-layer text targeting."""

  if activity["kind"] == "model":
    return activity["model_id"]
  return f"{activity['module']}.{activity['name']}"


def executableLabel(activity: dict[str, Any]) -> str:
  """Return one readable executable label."""

  if activity["kind"] == "model":
    return activity["model_id"]
  return activity["name"]


def formatHookName(section_name: str) -> str:
  """Return a readable label for one state hook section."""

  return "On entry" if section_name == "on_entry" else "On exit"


def _appendExternalTargets(
  targets: dict[str, ViewerBreakpointTarget],
  model: HsmModel,
  rendered: HsmRender,
  state_id: str,
  transition: dict[str, Any],
  is_set_by_id: dict[str, bool],
) -> None:
  """Append breakpoint targets for one authored external transition."""

  event_id = transition["event_id"]
  guard_condition = transition.get("guard_condition")
  if guard_condition is None:
    target_state_id = transition["target_id"]
    transition_ids = rendered.getExternalTransitionIds(state_id, event_id, target_state_id)
    for activity in transition.get("activities", []):
      _addTransitionActivityTarget(
        targets,
        model,
        rendered,
        kind="external_transition",
        state_id=state_id,
        event_id=event_id,
        target_state_id=target_state_id,
        transition_ids=transition_ids,
        activity=activity,
        is_set_by_id=is_set_by_id,
      )
    return

  guard_activity = guard_condition["guard_activity"]
  _addTarget(
    targets,
    breakpoint_id=breakpointKey("guard_condition", state_id, event_id, executableKey(guard_activity)),
    model_id=model.getDocumentId(),
    label=(
      "Guard: "
      f"{model.getStateLabel(state_id)} / {event_id} / {executableLabel(guard_activity)}"
    ),
    svg_ids=rendered.getGuardNodeIds(state_id, event_id),
    text_ids=rendered.getGuardNodeTextIds(state_id, event_id),
    is_set_by_id=is_set_by_id,
  )

  guarded_ids = rendered.getGuardedTransitionIds(state_id, event_id)
  for activity in transition.get("activities", []):
    _addTransitionActivityTarget(
      targets,
      model,
      rendered,
      kind="guarded_transition",
      state_id=state_id,
      event_id=event_id,
      target_state_id="guard",
      transition_ids=guarded_ids,
      activity=activity,
      is_set_by_id=is_set_by_id,
    )

  for result, branch_key in ((True, "true_branch"), (False, "false_branch")):
    branch = guard_condition[branch_key]
    target_state_id = branch["target_id"]
    branch_ids = rendered.getGuardBranchIds(
      state_id,
      event_id,
      outcome=result,
      target_state_id=target_state_id,
    )
    for activity in branch.get("activities", []):
      text_ids: list[str] = []
      for branch_id in branch_ids:
        text_ids.extend(rendered.getExternalTransitionActivityTextIds(branch_id, activity))
      _addTarget(
        targets,
        breakpoint_id=breakpointKey(
          "guard_branch_transition",
          state_id,
          event_id,
          str(result),
          target_state_id,
          executableKey(activity),
        ),
        model_id=model.getDocumentId(),
        label=(
          "Guard branch: "
          f"{event_id} {'true' if result else 'false'} -> "
          f"{model.getStateLabel(target_state_id)} / {executableLabel(activity)}"
        ),
        svg_ids=branch_ids,
        text_ids=tuple(text_ids),
        is_set_by_id=is_set_by_id,
      )


def _addTransitionActivityTarget(
  targets: dict[str, ViewerBreakpointTarget],
  model: HsmModel,
  rendered: HsmRender,
  *,
  kind: str,
  state_id: str,
  event_id: str,
  target_state_id: str,
  transition_ids: tuple[str, ...],
  activity: dict[str, Any],
  is_set_by_id: dict[str, bool],
) -> None:
  """Append one external-transition activity breakpoint target."""

  target_label = "guard" if target_state_id == "guard" else model.getStateLabel(target_state_id)
  text_ids: list[str] = []
  for transition_id in transition_ids:
    text_ids.extend(rendered.getExternalTransitionActivityTextIds(transition_id, activity))
  _addTarget(
    targets,
    breakpoint_id=breakpointKey(kind, state_id, event_id, target_state_id, executableKey(activity)),
    model_id=model.getDocumentId(),
    label=(
      "Transition: "
      f"{model.getStateLabel(state_id)} --{event_id}--> "
      f"{target_label} / {executableLabel(activity)}"
    ),
    svg_ids=transition_ids,
    text_ids=tuple(text_ids),
    is_set_by_id=is_set_by_id,
  )


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
  """Store one breakpoint target when it has a rendered text anchor."""

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
