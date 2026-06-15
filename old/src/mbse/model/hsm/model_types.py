"""Immutable HSM model dataclasses."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HsmCallableRef:
  """Reference to a Python callable used by a guard or activity."""

  module: str
  name: str

  def __str__(self) -> str:
    """Return the callable name for compact display."""

    return self.name


@dataclass(frozen=True)
class HsmVariable:
  """Declared runtime variable and its default value."""

  id: str
  default: object


@dataclass(frozen=True)
class HsmEventParameter:
  """Named event payload field."""

  name: str


@dataclass(frozen=True)
class HsmEvent:
  """Event definition available to external and internal handlers."""

  id: str
  parameters: tuple[HsmEventParameter, ...] = ()


@dataclass(frozen=True)
class HsmInitialTransition:
  """Structural initial route to the first active child or root state."""

  id: str
  target_id: str


@dataclass(frozen=True)
class HsmExternalTransition:
  """External transition from one state to another, optionally event-triggered."""

  id: str
  source_id: str
  target_id: str
  event_id: str | None = None
  activities: tuple[HsmCallableRef, ...] = ()


@dataclass(frozen=True)
class HsmGuardBranch:
  """Resolved branch target and activities for one guard outcome."""

  target_id: str
  activities: tuple[HsmCallableRef, ...] = ()


@dataclass(frozen=True)
class HsmGuardNode:
  """Decision node referenced by a transition target."""

  id: str
  guard: HsmCallableRef
  true_branch: HsmGuardBranch
  false_branch: HsmGuardBranch


@dataclass(frozen=True)
class HsmInternalTransition:
  """Event handler that runs activities without changing state."""

  id: str
  source_id: str
  event_id: str
  activities: tuple[HsmCallableRef, ...] = ()


@dataclass(frozen=True)
class HsmState:
  """State node with optional hierarchy, lifecycle hooks, and local initial."""

  id: str
  label: str | None = None
  states: tuple["HsmState", ...] = ()
  on_initial: tuple[HsmCallableRef, ...] = ()
  on_entry: tuple[HsmCallableRef, ...] = ()
  on_exit: tuple[HsmCallableRef, ...] = ()
  initial: HsmInitialTransition | None = None


@dataclass(frozen=True)
class HsmDocument:
  """Validated HSM JSON v1 document used by runtime and renderer."""

  schema_version: str
  document_id: str
  variables: tuple[HsmVariable, ...]
  events: tuple[HsmEvent, ...]
  states: tuple[HsmState, ...]
  initial: HsmInitialTransition | None
  external_transitions: tuple[HsmExternalTransition, ...]
  guard_nodes: tuple[HsmGuardNode, ...] = ()
  internal_transitions: tuple[HsmInternalTransition, ...] = ()

__all__ = [
  "HsmCallableRef",
  "HsmDocument",
  "HsmEvent",
  "HsmEventParameter",
  "HsmGuardBranch",
  "HsmGuardNode",
  "HsmInitialTransition",
  "HsmInternalTransition",
  "HsmState",
  "HsmExternalTransition",
  "HsmVariable",
]
