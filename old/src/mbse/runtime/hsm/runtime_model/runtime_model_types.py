from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property


@dataclass(frozen=True)
class HsmGeneratedRuntimeExternalTransitionRow:
  """Generated runtime external-transition metadata for one handler row."""

  transition_id: str
  event_id: str
  source_id: str
  target_id: str


@dataclass(frozen=True)
class HsmGeneratedRuntimeCallablePlan:
  """Import target for one generated runtime activity or guard callable."""

  plan_id: str
  module: str
  name: str


@dataclass(frozen=True)
class HsmGeneratedRuntimeGuardBranchRow:
  """Generated runtime guard branch target and branch-local activities."""

  branch_id: str
  target_id: str
  activity_plan_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class HsmGeneratedRuntimeEventCandidateRow:
  """Generated runtime event candidate considered during bubbling."""

  candidate_id: str
  event_id: str
  source_id: str
  kind: str
  target_id: str | None = None
  guard_plan_id: str | None = None
  activity_plan_ids: tuple[str, ...] = ()
  guard_node_id: str | None = None
  guard_true_branch: HsmGeneratedRuntimeGuardBranchRow | None = None
  guard_false_branch: HsmGeneratedRuntimeGuardBranchRow | None = None


@dataclass(frozen=True)
class HsmGeneratedRuntimeView:
  """Generated runtime metadata derived from one validated HSM document."""

  document_id: str
  state_ids: tuple[str, ...]
  parent_ids: dict[str, str | None]
  ancestry_by_state_id: dict[str, tuple[str, ...]]
  initial_target_ids: dict[str | None, str]
  initial_transition_ids: dict[str | None, str]
  leaf_state_ids: tuple[str, ...]
  callable_plans_by_id: dict[str, HsmGeneratedRuntimeCallablePlan]
  on_initial_plan_ids_by_state_id: dict[str, tuple[str, ...]]
  on_entry_plan_ids_by_state_id: dict[str, tuple[str, ...]]
  on_exit_plan_ids_by_state_id: dict[str, tuple[str, ...]]
  event_candidate_rows_by_state_id: dict[
    str,
    tuple[HsmGeneratedRuntimeEventCandidateRow, ...],
  ]

  @cached_property
  def external_transition_rows_by_state_id(
    self,
  ) -> dict[str, tuple[HsmGeneratedRuntimeExternalTransitionRow, ...]]:
    """Project external-transition rows from mixed event candidate rows."""

    return {
      state_id: tuple(
          HsmGeneratedRuntimeExternalTransitionRow(
          transition_id=row.candidate_id,
          event_id=row.event_id,
          source_id=row.source_id,
          target_id=row.target_id or "",
        )
        for row in rows
        if row.kind == "external_transition" and row.target_id is not None
      )
      for state_id, rows in self.event_candidate_rows_by_state_id.items()
    }


__all__ = [
  "HsmGeneratedRuntimeCallablePlan",
  "HsmGeneratedRuntimeEventCandidateRow",
  "HsmGeneratedRuntimeGuardBranchRow",
  "HsmGeneratedRuntimeExternalTransitionRow",
  "HsmGeneratedRuntimeView",
]
