from __future__ import annotations

"""HSM runtime highlighting and focus derivation for viewer sessions."""

from mbse.model.hsm.hsm_model import HsmExternalTransitionRelation
from mbse.model.hsm.hsm_model import HsmGuardedTransitionBranchRelation
from mbse.model.hsm.hsm_model import HsmRelatedState
from mbse.runtime.hsm.hsm_runtime import HsmRuntimeTrace
from mbse_web_viewer.server.session import ViewerFocus
from mbse_web_viewer.server.session import ViewerHighlight


class HsmHighlightingMixin:
  """Provide HSM highlight and focus derivation for a controller."""

  def _buildCurrentTraceHighlight(self) -> ViewerHighlight:
    """Resolve the latest runtime trace into SVG ids for highlighting."""

    trace = self._getExecutionLog()[-1]
    state_ids = self._buildStateHighlightIds()
    transition_ids = list(self._buildTraceTransitionIds(trace))
    text_ids = list(self._buildTraceTextIds(trace, transition_ids))
    current_transition_ids: tuple[str, ...] = ()
    current_text_ids: tuple[str, ...] = ()
    next_step = self._getCallStackStep()
    if next_step is not None:
      if next_step["kind"] == "change_active_state":
        current_transition_ids = (
          self._rendered_svg.getStateId(next_step["target_state_id"]),
        )
        current_text_ids = self._rendered_svg.getStateLabelTextIds(
          next_step["target_state_id"]
        )
      else:
        current_transition_ids, current_text_ids = self._buildCurrentEntryHighlightIds(next_step)
    return ViewerHighlight(
      state_ids=state_ids,
      transition_ids=tuple(dict.fromkeys(transition_ids)),
      text_ids=tuple(dict.fromkeys(text_ids)),
      current_transition_ids=tuple(dict.fromkeys(current_transition_ids)),
      current_text_ids=tuple(dict.fromkeys(current_text_ids)),
    )

  def _buildModelHighlights(self) -> dict[str, ViewerHighlight]:
    """Return current highlights keyed by rendered model id."""

    return {self._model.getDocumentId(): self._last_highlight}

  def _emptyHighlight(self) -> ViewerHighlight:
    """Return an empty highlight payload."""

    return ViewerHighlight(
      state_ids=(),
      transition_ids=(),
      text_ids=(),
      current_transition_ids=(),
      current_text_ids=(),
    )

  def _buildCurrentStateFocus(self) -> ViewerFocus:
    """Resolve state-focus and trace-focus contexts for the viewer."""

    return ViewerFocus(
      state_related_ids=self._buildStateModeRelatedIds(),
      trace_related_ids=self._buildTraceModeRelatedIds(),
      state_viewport_focus_ids=self._buildStateModeViewportFocusIds(),
      trace_viewport_focus_ids=self._buildTraceModeViewportFocusIds(),
    )

  def _buildStateModeRelatedIds(self) -> tuple[str, ...]:
    """Return the non-dimmed ids for focus-current-state mode."""

    state_id = self._getEffectiveFocusStateId()
    if state_id is None:
      return ()

    related = self._model.getStateRelatedElements(state_id)
    related_ids = self._buildStateFocusIds(related.states)

    for chain in related.initial_entry_chains:
      for transition in chain:
        related_ids.extend(
          self._rendered_svg.getInitialTransitionOwnedIds(transition.source_state_id)
        )

    for transition in related.outgoing_external_transitions:
      related_ids.extend(self._buildExternalTransitionFocusIds(transition))

    for transition in related.incoming_external_transitions:
      related_ids.extend(self._buildExternalTransitionFocusIds(transition))

    for branch in related.guarded_transition_branches:
      related_ids.extend(self._buildGuardedBranchFocusIds(branch))

    for pending_state_id in sorted(self._getPendingTraceStateIds()):
      related_ids.extend(self._buildStateOwnedFocusIds(pending_state_id))

    related_ids.extend(self._buildHighlightFocusIds())
    return self._normalizeFocusIds(related_ids)

  def _buildTraceModeRelatedIds(self) -> tuple[str, ...]:
    """Return the non-dimmed ids for focus-trace mode."""

    execution_log = self._getExecutionLog()
    if not execution_log:
      return ()

    trace = execution_log[-1]
    related_ids = self._buildHighlightFocusIds()
    state_ids = self._getTraceStateIds(trace)
    state_ids.update(self._getPendingTraceStateIds())
    if not state_ids:
      state_id = self._getEffectiveFocusStateId()
      if state_id is not None:
        state_ids.add(state_id)

    for state_id in sorted(state_ids):
      related_ids.extend(self._buildStateOwnedFocusIds(state_id))

    for entry in trace["entries"]:
      if entry["kind"] != "initial_transition":
        continue
      related_ids.extend(
        self._rendered_svg.getInitialTransitionOwnedIds(entry["source_state_id"])
      )

    return self._normalizeFocusIds(related_ids)

  def _buildStateModeViewportFocusIds(self) -> tuple[str, ...]:
    """Return the viewport target for focus-current-state mode."""

    state_ids = self._last_highlight.state_ids
    if state_ids:
      return state_ids
    return self._last_highlight.transition_ids

  def _buildTraceModeViewportFocusIds(self) -> tuple[str, ...]:
    """Return the viewport target for focus-trace mode."""

    if self._last_highlight.current_transition_ids:
      return self._last_highlight.current_transition_ids

    if self._last_highlight.current_text_ids:
      return self._last_highlight.current_text_ids

    state_ids = self._last_highlight.state_ids
    if state_ids:
      return state_ids
    return self._last_highlight.transition_ids

  def _buildHighlightFocusIds(self) -> list[str]:
    """Return all currently highlighted ids so focus mode never dims them."""

    return list(self._expandOwnedFocusIds(
      self._last_highlight.state_ids
      + self._last_highlight.transition_ids
      + self._last_highlight.text_ids
      + self._last_highlight.current_transition_ids
      + self._last_highlight.current_text_ids
    ))

  def _normalizeFocusIds(self, related_ids: list[str]) -> tuple[str, ...]:
    """Expand focused ids to complete visual owners and deduplicate."""

    return self._expandOwnedFocusIds(related_ids)

  def _expandOwnedFocusIds(self, related_ids: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    """Expand each focused id to all visible ids owned by the same semantic item."""

    normalized_ids: list[str] = []
    for related_id in related_ids:
      normalized_ids.extend(self._rendered_svg.getOwnedIdsForHighlightId(related_id))
    return tuple(dict.fromkeys(normalized_ids))

  def _buildStateFocusIds(self, related_states: tuple[HsmRelatedState, ...]) -> list[str]:
    """Resolve state and state-owned text ids for the related state set."""

    related_ids: list[str] = []

    for related_state in related_states:
      related_ids.extend(self._buildStateOwnedFocusIds(related_state.state_id))

    return related_ids

  def _buildStateOwnedFocusIds(self, state_id: str) -> list[str]:
    """Resolve one state plus visible parent-state context for focus."""

    owned_ids = list(self._rendered_svg.getStateOwnedIds(state_id))
    for parent_state_id in self._model.getParentStateIds(state_id):
      owned_ids.extend(self._rendered_svg.getStateOwnedIds(parent_state_id))
    return owned_ids

  def _buildExternalTransitionFocusIds(
    self,
    transition: HsmExternalTransitionRelation,
  ) -> list[str]:
    """Resolve one unguarded external transition and its related ids."""

    transition_ids = self._rendered_svg.getExternalTransitionIds(
      transition.source_state_id,
      transition.event_id,
      transition.target_state_id,
    )
    related_ids: list[str] = []
    for transition_id in transition_ids:
      related_ids.extend(self._rendered_svg.getExternalTransitionOwnedIds(transition_id))
    related_ids.extend(self._buildStateOwnedFocusIds(transition.source_state_id))
    related_ids.extend(self._buildStateOwnedFocusIds(transition.target_state_id))
    return related_ids

  def _buildGuardedBranchFocusIds(
    self,
    branch: HsmGuardedTransitionBranchRelation,
  ) -> list[str]:
    """Resolve one guarded branch relation and its related ids."""

    related_ids: list[str] = []
    guarded_ids = self._rendered_svg.getGuardedTransitionIds(
      branch.source_state_id,
      branch.event_id,
    )
    guard_node_ids = self._rendered_svg.getGuardNodeIds(
      branch.source_state_id,
      branch.event_id,
    )
    branch_ids = self._rendered_svg.getGuardBranchIds(
      branch.source_state_id,
      branch.event_id,
      outcome=branch.guard_result,
      target_state_id=branch.target_state_id,
    )
    for guarded_id in guarded_ids:
      related_ids.extend(self._rendered_svg.getExternalTransitionOwnedIds(guarded_id))
    for guard_node_id in guard_node_ids:
      related_ids.extend(self._rendered_svg.getGuardNodeOwnedIds(guard_node_id))
    for branch_id in branch_ids:
      related_ids.extend(self._rendered_svg.getExternalTransitionOwnedIds(branch_id))
    related_ids.extend(self._buildStateOwnedFocusIds(branch.source_state_id))
    related_ids.extend(self._buildStateOwnedFocusIds(branch.target_state_id))

    return related_ids

  def _buildStateHighlightIds(self) -> tuple[str, ...]:
    """Return the highlight ids for the current active state."""

    if self._isPendingInitialTracePreviewMode():
      return (self._rendered_svg.getRootInitialTransitionSourceId(),)

    state_id = self._getEffectiveFocusStateId()
    if state_id is None:
      return ()
    return (self._rendered_svg.getStateId(state_id),)

  def _getEffectiveFocusStateId(self) -> str | None:
    """Return the state id used for focus while step execution is in progress."""

    state_id = self._runtime.getState()["id"]
    if state_id is not None:
      return state_id

    execution_log = self._getExecutionLog()
    if not self._runtime.hasPendingExecution() or not execution_log:
      return None

    trace = execution_log[-1]
    if trace["event"]["event_id"] is not None:
      return None

    if not trace["entries"]:
      return None

    for entry in reversed(trace["entries"]):
      source_state_id = entry.get("source_state_id")
      if source_state_id is not None:
        return source_state_id
      target_state_id = entry.get("target_state_id")
      if target_state_id is not None:
        return target_state_id

    return self._model.getRootInitialTargetId()

  def _getTraceStateIds(self, trace: HsmRuntimeTrace) -> set[str]:
    """Return the set of states touched structurally by one runtime trace."""

    state_ids: set[str] = set()
    for entry in trace["entries"]:
      source_state_id = entry.get("source_state_id")
      if source_state_id is not None:
        state_ids.add(source_state_id)
      target_state_id = entry.get("target_state_id")
      if target_state_id is not None:
        state_ids.add(target_state_id)
    return state_ids

  def _getPendingTraceStateIds(self) -> set[str]:
    """Return states semantically owned by the next pending debugger step."""

    next_step = self._getCallStackStep()
    if next_step is None:
      return set()

    state_ids: set[str] = set()
    if next_step["kind"] in {
      "on_entry",
      "on_exit",
      "internal_transition",
      "pending_guard_condition",
      "guarded_transition",
    }:
      source_state_id = next_step["source_state_id"]
      if source_state_id is not None:
        state_ids.add(source_state_id)
      return state_ids

    if next_step["kind"] == "change_active_state":
      state_ids.add(next_step["target_state_id"])
      return state_ids

    if next_step["kind"] in {"external_transition", "guard_branch_transition"}:
      source_state_id = next_step["source_state_id"]
      target_state_id = next_step["target_state_id"]
      if source_state_id is not None:
        state_ids.add(source_state_id)
      if target_state_id is not None:
        state_ids.add(target_state_id)
      return state_ids

    if next_step["kind"] == "initial_transition":
      source_state_id = next_step["source_state_id"]
      if source_state_id is not None:
        state_ids.add(source_state_id)

    return state_ids

  def _isPendingInitialTracePreviewMode(self) -> bool:
    """Return whether the runtime is paused before the first init step executes."""

    execution_log = self._getExecutionLog()
    return (
      self._runtime.isPaused()
      and self._runtime.hasPendingExecution()
      and bool(execution_log)
      and execution_log[-1]["event"]["event_id"] is None
    )

  def _buildTraceTransitionIds(
    self,
    trace: HsmRuntimeTrace,
  ) -> tuple[str, ...]:
    """Resolve structural transition ids from one completed runtime trace."""

    event_id = trace["event"]["event_id"]
    resolved_ids: list[str] = []

    for entry in trace["entries"]:
      if entry["kind"] == "initial_transition":
        source_state_id = entry["source_state_id"]
        if source_state_id is None:
          resolved_ids.append(self._rendered_svg.getRootInitialTransitionId())
        else:
          resolved_ids.append(
            self._rendered_svg.getInitialTransitionId(source_state_id)
          )
        continue

      if event_id is None:
        continue

      if entry["kind"] == "internal_transition":
        resolved_ids.extend(
          self._rendered_svg.getInternalTransitionIds(
            entry["source_state_id"],
            event_id,
          )
        )
        continue

      if entry["kind"] == "guard_condition":
        source_state_id = entry["source_state_id"]
        resolved_ids.extend(
          self._rendered_svg.getGuardNodeIds(source_state_id, event_id)
        )
        continue

      if entry["kind"] == "guarded_transition":
        resolved_ids.extend(
          self._getGuardedTransitionIds(entry["source_state_id"], event_id)
        )
        continue

      if entry["kind"] == "guard_branch_transition":
        resolved_ids.extend(
          self._rendered_svg.getGuardBranchIds(
            entry["source_state_id"],
            event_id,
            outcome=entry["result"],
            target_state_id=entry["target_state_id"],
          )
        )
        continue

      if entry["kind"] == "external_transition":
        resolved_ids.extend(
          self._rendered_svg.getExternalTransitionIds(
            entry["source_state_id"],
            event_id,
            entry["target_state_id"],
          )
        )
    return tuple(resolved_ids)

  def _buildTraceTextIds(
    self,
    trace: HsmRuntimeTrace,
    transition_ids: list[str],
  ) -> tuple[str, ...]:
    """Resolve the text fragment ids associated with the latest trace."""

    event_id = trace["event"]["event_id"]
    resolved_ids: list[str] = []

    for transition_id in transition_ids:
      resolved_ids.extend(
        self._rendered_svg.getInitialTransitionLabelTextIds(transition_id)
      )
      resolved_ids.extend(
        self._rendered_svg.getExternalTransitionLabelTextIds(transition_id)
      )

    for entry in trace["entries"]:
      if entry["kind"] in {"on_entry", "on_exit"}:
        source_state_id = entry["source_state_id"]
        resolved_ids.extend(
          self._rendered_svg.getStateHookSectionTextIds(
            source_state_id,
            entry["kind"],
          )
        )
        resolved_ids.extend(
          self._rendered_svg.getStateHookActivityTextIds(
            source_state_id,
            entry["kind"],
            entry["activity"],
          )
        )
        continue

      if event_id is None:
        if entry["kind"] != "initial_transition" or entry["activity"] is None:
          continue
        transition_id = self._rendered_svg.getRootInitialTransitionId()
        if entry["source_state_id"] is not None:
          transition_id = self._rendered_svg.getInitialTransitionId(entry["source_state_id"])
        resolved_ids.extend(
          self._rendered_svg.getInitialTransitionActivityTextIds(
            transition_id,
            entry["activity"],
          )
        )
        continue

      if entry["kind"] == "initial_transition":
        if entry["activity"] is None:
          continue
        transition_id = self._rendered_svg.getInitialTransitionId(entry["source_state_id"])
        resolved_ids.extend(
          self._rendered_svg.getInitialTransitionActivityTextIds(
            transition_id,
            entry["activity"],
          )
        )
        continue

      if entry["kind"] == "internal_transition":
        source_state_id = entry["source_state_id"]
        transition_ids_for_entry = self._rendered_svg.getInternalTransitionIds(
          source_state_id,
          event_id,
        )
        if entry["activity"] is None:
          for transition_id in transition_ids_for_entry:
            resolved_ids.extend(
              self._rendered_svg.getInternalTransitionSectionTextIds(
                source_state_id,
                event_id,
              )
            )
            resolved_ids.extend(
              self._rendered_svg.getInternalTransitionEventTextIds(
                transition_id,
              )
            )
          continue
        for transition_id in transition_ids_for_entry:
          resolved_ids.extend(
            self._rendered_svg.getInternalTransitionActivityTextIds(
              transition_id,
              entry["activity"],
            )
          )
        continue

      if entry["kind"] == "guard_condition":
        source_state_id = entry["source_state_id"]
        resolved_ids.extend(
          self._rendered_svg.getGuardNodeTextIds(source_state_id, event_id)
        )
        continue

      if entry["kind"] == "guard_branch_transition":
        if entry["activity"] is None:
          continue
        branch_ids = self._rendered_svg.getGuardBranchIds(
          entry["source_state_id"],
          event_id,
          outcome=entry["result"],
          target_state_id=entry["target_state_id"],
        )
        for branch_id in branch_ids:
          resolved_ids.extend(
            self._rendered_svg.getExternalTransitionActivityTextIds(
              branch_id,
              entry["activity"],
            )
          )
        continue

      if entry["kind"] != "external_transition":
        if entry["kind"] != "guarded_transition":
          continue

      if entry["activity"] is None:
        continue
      if entry["kind"] == "guarded_transition":
        transition_ids_for_entry = self._getGuardedTransitionIds(
          entry["source_state_id"],
          event_id,
        )
      else:
        transition_ids_for_entry = self._rendered_svg.getExternalTransitionIds(
          entry["source_state_id"],
          event_id,
          entry["target_state_id"],
        )
      for transition_id in transition_ids_for_entry:
        resolved_ids.extend(
          self._rendered_svg.getExternalTransitionActivityTextIds(
            transition_id,
            entry["activity"],
          )
        )
    return tuple(resolved_ids)

  def _buildCurrentEntryHighlightIds(
    self,
    current_entry: HsmRuntimePendingExecutionTypeAlias,
  ) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Resolve the live debugger emphasis for the next pending entry."""

    event_id = self._getPendingEventId()

    if current_entry["kind"] == "initial_transition":
      source_state_id = current_entry["source_state_id"]
      transition_ids = (
        (
          self._rendered_svg.getRootInitialTransitionId(),
          self._rendered_svg.getRootInitialTransitionSourceId(),
        )
        if source_state_id is None
        else (
          self._rendered_svg.getInitialTransitionId(source_state_id),
          self._rendered_svg.getInitialTransitionSourceId(source_state_id),
        )
      )
      if current_entry["activity"] is None:
        return transition_ids, ()
      return transition_ids, (
        self._rendered_svg.getInitialTransitionLabelTextIds(transition_ids[0])
        + self._rendered_svg.getInitialTransitionActivityTextIds(
          transition_ids[0],
          current_entry["activity"],
        )
      )

    if current_entry["kind"] == "internal_transition" and event_id is not None:
      transition_ids = self._rendered_svg.getInternalTransitionIds(
        current_entry["source_state_id"],
        event_id,
      )
      resolved_ids: list[str] = []
      for transition_id in transition_ids:
        resolved_ids.extend(
          self._rendered_svg.getInternalTransitionSectionTextIds(
            current_entry["source_state_id"],
            event_id,
          )
        )
        resolved_ids.extend(
          self._rendered_svg.getInternalTransitionEventTextIds(transition_id)
        )
        if current_entry["activity"] is not None:
          resolved_ids.extend(
            self._rendered_svg.getInternalTransitionActivityTextIds(
              transition_id,
              current_entry["activity"],
            )
          )
      return transition_ids, tuple(resolved_ids)

    if current_entry["kind"] == "guarded_transition" and event_id is not None:
      transition_ids = self._getGuardedTransitionIds(
        current_entry["source_state_id"],
        event_id,
      )
      resolved_ids: list[str] = []
      for transition_id in transition_ids:
        resolved_ids.extend(
          self._rendered_svg.getExternalTransitionLabelTextIds(transition_id)
        )
        if current_entry["activity"] is not None:
          resolved_ids.extend(
            self._rendered_svg.getExternalTransitionActivityTextIds(
              transition_id,
              current_entry["activity"],
            )
          )
      return transition_ids, tuple(resolved_ids)

    if current_entry["kind"] == "external_transition" and event_id is not None:
      transition_ids = self._rendered_svg.getExternalTransitionIds(
        current_entry["source_state_id"],
        event_id,
        current_entry["target_state_id"],
      )
      resolved_ids: list[str] = []
      for transition_id in transition_ids:
        resolved_ids.extend(
          self._rendered_svg.getExternalTransitionLabelTextIds(transition_id)
        )
        if current_entry["activity"] is not None:
          resolved_ids.extend(
            self._rendered_svg.getExternalTransitionActivityTextIds(
              transition_id,
              current_entry["activity"],
            )
          )
      return transition_ids, tuple(resolved_ids)

    if current_entry["kind"] == "guard_branch_transition" and event_id is not None:
      branch_ids = self._rendered_svg.getGuardBranchIds(
        current_entry["source_state_id"],
        event_id,
        outcome=current_entry["result"],
        target_state_id=current_entry["target_state_id"],
      )
      resolved_ids: list[str] = []
      for branch_id in branch_ids:
        resolved_ids.extend(
          self._rendered_svg.getExternalTransitionLabelTextIds(branch_id)
        )
        if current_entry["activity"] is not None:
          resolved_ids.extend(
            self._rendered_svg.getExternalTransitionActivityTextIds(
              branch_id,
              current_entry["activity"],
            )
          )
      return branch_ids, tuple(resolved_ids)

    if current_entry["kind"] == "pending_guard_condition" and event_id is not None:
      return (
        self._rendered_svg.getGuardNodeIds(current_entry["source_state_id"], event_id),
        self._rendered_svg.getGuardNodeTextIds(current_entry["source_state_id"], event_id),
      )

    if current_entry["kind"] in {"on_entry", "on_exit"}:
      return (), (
        self._rendered_svg.getStateHookSectionTextIds(
          current_entry["source_state_id"],
          current_entry["kind"],
        )
        + self._rendered_svg.getStateHookActivityTextIds(
          current_entry["source_state_id"],
          current_entry["kind"],
          current_entry["activity"],
        )
      )

    return (), ()

  def _getPendingEventId(self) -> str | None:
    """Return the event id for the currently pending trace, if any."""

    execution_log = self._getExecutionLog()
    if not self._runtime.hasPendingExecution() or not execution_log:
      return None
    return execution_log[-1]["event"]["event_id"]

  def _getGuardedTransitionIds(
    self,
    source_state_id: str,
    event_id: str,
  ) -> tuple[str, ...]:
    """Return guarded transition ids when that state-event pair is rendered."""

    try:
      return self._rendered_svg.getGuardedTransitionIds(source_state_id, event_id)
    except KeyError:
      return ()
