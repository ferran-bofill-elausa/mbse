from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HsmExecutedActivity:
  """One executed activity with semantic ownership metadata."""

  activity_id: str
  owner_kind: str
  owner_id: str


@dataclass(frozen=True)
class HsmRuntimeMetadata:
  """Canonical runtime-declared controls metadata."""

  event_ids: tuple[str, ...]
  variable_ids: tuple[str, ...]


@dataclass(frozen=True)
class HsmRuntimeLastEvent:
  """Outcome of the latest runtime event resolution."""

  event_id: str | None = None
  handled: bool = False
  handler_kind: str | None = None
  handler_id: str | None = None
  guard_node_id: str | None = None
  guard_branch_id: str | None = None
  transition_path_ids: tuple[str, ...] = ()
  executed_activities: tuple[HsmExecutedActivity, ...] = ()


@dataclass(frozen=True)
class HsmRuntimeSnapshot:
  """Inspectable runtime state returned to callers and bridges."""

  state_id: str
  active_path: tuple[str, ...]
  variables: dict[str, object]
  last_event: HsmRuntimeLastEvent = HsmRuntimeLastEvent()


__all__ = [
  "HsmExecutedActivity",
  "HsmRuntimeMetadata",
  "HsmRuntimeLastEvent",
  "HsmRuntimeSnapshot",
]
