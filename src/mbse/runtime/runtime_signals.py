"""Shared runtime control signals."""

from __future__ import annotations


class RuntimeExecutionSuspended(Exception):
  """Signal that one runtime step suspended into a child model frame."""
