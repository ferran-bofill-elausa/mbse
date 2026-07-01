"""Shared viewer session payload types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ViewerHighlight:
  """Resolved SVG ids to highlight for the current viewer session."""

  state_ids: tuple[str, ...]
  transition_ids: tuple[str, ...]
  text_ids: tuple[str, ...]
  current_transition_ids: tuple[str, ...]
  current_text_ids: tuple[str, ...]


@dataclass(frozen=True)
class ViewerTrace:
  """Serialized view of the latest runtime trace."""

  event_id: str | None
  entries: list[dict[str, object]]


@dataclass(frozen=True)
class ViewerBreakpointTarget:
  """One semantic debugger breakpoint target resolved to SVG ids."""

  id: str
  model_id: str
  label: str
  svg_ids: tuple[str, ...]
  text_ids: tuple[str, ...]
  is_set: bool
  enabled: bool


@dataclass(frozen=True)
class ViewerFocus:
  """Resolved focus contexts for model-centric and trace-centric viewer modes."""

  state_related_ids: tuple[str, ...]
  trace_related_ids: tuple[str, ...]
  state_viewport_focus_ids: tuple[str, ...]
  trace_viewport_focus_ids: tuple[str, ...]


@dataclass(frozen=True)
class ViewerSession:
  """Full JSON session served to the browser viewer."""

  active_model_id: str
  models: tuple[dict[str, object], ...]
  enums: tuple[dict[str, object], ...]
  events: tuple[dict[str, object], ...]
  variables: tuple[dict[str, object], ...]
  state: dict[str, str | None]
  variable_values: dict[str, Any]
  changed_variable_ids: tuple[str, ...]
  execution_log: list[dict[str, object]]
  debugger: dict[str, object]
  highlight: ViewerHighlight
  highlights_by_model: dict[str, ViewerHighlight]
  focus: ViewerFocus
  last_trace: ViewerTrace
  breakpoints: tuple[ViewerBreakpointTarget, ...]
