from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
import importlib
from pathlib import Path
import types
from typing import Callable

from jinja2 import Environment
from jinja2 import FileSystemLoader
from jinja2 import StrictUndefined

from mbse.model.hsm import HsmCallableRef

from ..runtime_model.runtime_model_types import HsmGeneratedRuntimeCallablePlan
from ..runtime_model.runtime_model_types import HsmGeneratedRuntimeEventCandidateRow
from ..runtime_model.runtime_model_types import HsmGeneratedRuntimeGuardBranchRow
from ..runtime_model.runtime_model_types import HsmGeneratedRuntimeExternalTransitionRow
from ..runtime_model.runtime_model_types import HsmGeneratedRuntimeView


TEMPLATES_DIR = Path(__file__).parent
TEMPLATE_NAME = "generator_template.py.j2"
DEFAULT_GENERATED_RUNTIME_OUTPUT_DIR = (
  Path(__file__).resolve().parents[4] / "build" / "mbse_runtime"
)
StateHandler = Callable[[object, str], tuple[str, str | None]]
ActivityHandler = Callable[[object], None]
GuardHandler = Callable[[object], bool]


@dataclass(frozen=True)
class GeneratedRuntime:
  """Resolved generated runtime module plus imported runtime callables."""

  source_code: str
  parent_ids: dict[str, str | None]
  ancestry_by_state_id: dict[str, tuple[str, ...]]
  initial_target_ids: dict[str | None, str]
  initial_transition_ids: dict[str | None, str]
  callable_plans_by_id: dict[str, HsmGeneratedRuntimeCallablePlan]
  on_initial_plan_ids_by_state_id: dict[str, tuple[str, ...]]
  on_entry_plan_ids_by_state_id: dict[str, tuple[str, ...]]
  on_exit_plan_ids_by_state_id: dict[str, tuple[str, ...]]
  event_candidate_rows_by_state_id: dict[
    str,
    tuple[HsmGeneratedRuntimeEventCandidateRow, ...],
  ]
  leaf_state_ids: frozenset[str]
  activity_handlers_by_plan_id: dict[str, ActivityHandler]
  guard_handlers_by_plan_id: dict[str, GuardHandler]
  _handlers: dict[str, StateHandler]

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

  def dispatch(
    self,
    state_id: str,
    ctx: object,
    event_id: str,
  ) -> tuple[str, str | None]:
    """Dispatch one event to the generated handler for a state."""

    handler = self._handlers[state_id]
    return handler(ctx, event_id)

  def resolve_activity_handlers(
    self,
    plan_ids: tuple[str, ...],
  ) -> tuple[ActivityHandler, ...]:
    """Resolve ordered activity handlers for the given plan IDs."""

    return tuple(self.activity_handlers_by_plan_id[plan_id] for plan_id in plan_ids)

  def resolve_guard_handler(self, plan_id: str) -> GuardHandler:
    """Resolve one generated runtime guard handler by plan ID."""

    return self.guard_handlers_by_plan_id[plan_id]


def render_generated_runtime_source(view: HsmGeneratedRuntimeView) -> str:
  """Render Python source for the internal generated runtime module."""

  template = _build_environment().get_template(TEMPLATE_NAME)
  return template.render(
      view=view,
      parent_ids_literal=_format_parent_ids_literal(view),
      ancestry_by_state_literal=_format_ancestry_by_state_literal(view),
      initial_target_ids_literal=_format_initial_target_ids_literal(view),
      initial_transition_ids_literal=_format_initial_transition_ids_literal(view),
      callable_plans_by_id_literal=_format_callable_plans_by_id_literal(view),
      on_initial_plan_ids_literal=_format_plan_ids_by_state_literal(
        view,
        view.on_initial_plan_ids_by_state_id,
      ),
      on_entry_plan_ids_literal=_format_plan_ids_by_state_literal(
        view,
        view.on_entry_plan_ids_by_state_id,
      ),
      on_exit_plan_ids_literal=_format_plan_ids_by_state_literal(
        view,
        view.on_exit_plan_ids_by_state_id,
      ),
      event_candidate_rows_by_state_literal=_format_event_candidate_rows_by_state_literal(
        view
      ),
      leaf_state_ids_literal=_format_leaf_state_ids_literal(view),
  ).strip() + "\n"


def load_generated_runtime(
  view: HsmGeneratedRuntimeView,
  *,
  output_path: str | Path | None = None,
) -> GeneratedRuntime:
  """Render, import, and resolve one generated runtime instance."""

  source_code = render_generated_runtime_source(view)
  if output_path is not None:
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(source_code)
  module = types.ModuleType(f"_mbse_generated_hsm_{view.document_id}")
  exec(source_code, module.__dict__)
  return GeneratedRuntime(
    source_code=source_code,
    parent_ids=dict(module.PARENTS),
    ancestry_by_state_id={
      state_id: tuple(module.ANCESTRY_BY_STATE[state_id])
      for state_id in view.state_ids
    },
    initial_target_ids=dict(module.INITIAL_TARGETS),
    initial_transition_ids=dict(module.INITIAL_TRANSITION_IDS),
    callable_plans_by_id=dict(module.CALLABLE_PLANS_BY_ID),
    on_initial_plan_ids_by_state_id={
      state_id: tuple(module.ON_INITIAL_PLAN_IDS_BY_STATE[state_id])
      for state_id in view.state_ids
    },
    on_entry_plan_ids_by_state_id={
      state_id: tuple(module.ON_ENTRY_PLAN_IDS_BY_STATE[state_id])
      for state_id in view.state_ids
    },
    on_exit_plan_ids_by_state_id={
      state_id: tuple(module.ON_EXIT_PLAN_IDS_BY_STATE[state_id])
      for state_id in view.state_ids
    },
    event_candidate_rows_by_state_id={
      state_id: tuple(module.EVENT_CANDIDATE_ROWS_BY_STATE[state_id])
      for state_id in view.state_ids
    },
    leaf_state_ids=frozenset(module.LEAF_STATES),
    activity_handlers_by_plan_id=_resolve_handlers_by_plan_id(
      module.CALLABLE_PLANS_BY_ID,
      _collect_activity_plan_ids(view),
    ),
    guard_handlers_by_plan_id=_resolve_guard_handlers_by_plan_id(view),
    _handlers={
      state_id: getattr(module, f"state_{state_id}") for state_id in view.state_ids
    },
  )


def _build_environment() -> Environment:
  """Build the Jinja environment used for generated runtime rendering."""

  return Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    undefined=StrictUndefined,
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
  )


def _format_parent_ids_literal(view: HsmGeneratedRuntimeView) -> str:
  """Format parent IDs as a Python literal for code generation."""

  parts = []
  for state_id in view.state_ids:
    parent_id = view.parent_ids[state_id]
    value = "None" if parent_id is None else f'"{parent_id}"'
    parts.append(f'"{state_id}": {value}')
  return "{" + ", ".join(parts) + "}"


def _format_initial_target_ids_literal(view: HsmGeneratedRuntimeView) -> str:
  """Format initial target IDs as a Python literal."""

  parts: list[str] = []
  if None in view.initial_target_ids:
    parts.append(f'None: "{view.initial_target_ids[None]}"')
  for state_id in view.state_ids:
    if state_id in view.initial_target_ids:
      parts.append(
        f'"{state_id}": "{view.initial_target_ids[state_id]}"'
      )
  return "{" + ", ".join(parts) + "}"


def _format_ancestry_by_state_literal(view: HsmGeneratedRuntimeView) -> str:
  """Format ancestry paths as a Python literal."""

  parts: list[str] = []
  for state_id in view.state_ids:
    ancestry = ", ".join(
      f'"{ancestor_id}"' for ancestor_id in view.ancestry_by_state_id[state_id]
    )
    if len(view.ancestry_by_state_id[state_id]) == 1:
      ancestry = f"{ancestry},"
    parts.append(f'"{state_id}": ({ancestry})')
  return "{" + ", ".join(parts) + "}"


def _format_leaf_state_ids_literal(view: HsmGeneratedRuntimeView) -> str:
  """Format leaf state IDs as a frozen-set literal."""

  parts = ", ".join(f'"{state_id}"' for state_id in view.leaf_state_ids)
  return f"frozenset({{{parts}}})"


def _format_initial_transition_ids_literal(view: HsmGeneratedRuntimeView) -> str:
  """Format initial transition IDs as a Python literal."""

  parts: list[str] = []
  if None in view.initial_transition_ids:
    parts.append(f'None: "{view.initial_transition_ids[None]}"')
  for state_id in view.state_ids:
    if state_id in view.initial_transition_ids:
      parts.append(
        f'"{state_id}": "{view.initial_transition_ids[state_id]}"'
      )
  return "{" + ", ".join(parts) + "}"


def _format_callable_plans_by_id_literal(view: HsmGeneratedRuntimeView) -> str:
  """Format callable plans as inline constructor literals."""

  parts: list[str] = []
  for plan_id in sorted(view.callable_plans_by_id.keys()):
    plan = view.callable_plans_by_id[plan_id]
    parts.append(
      f'"{plan_id}": HsmGeneratedRuntimeCallablePlan('
      f'plan_id="{plan.plan_id}", '
      f'module="{plan.module}", '
      f'name="{plan.name}")'
    )
  return "{" + ", ".join(parts) + "}"


def _format_plan_ids_by_state_literal(
  view: HsmGeneratedRuntimeView,
  plan_ids_by_state_id: dict[str, tuple[str, ...]],
) -> str:
  """Format plan IDs keyed by state as a Python literal."""

  parts: list[str] = []
  for state_id in view.state_ids:
    parts.append(
      f'"{state_id}": '
      f"{_format_plan_ids_tuple_literal(plan_ids_by_state_id[state_id])}"
    )
  return "{" + ", ".join(parts) + "}"


def _format_plan_ids_tuple_literal(plan_ids: tuple[str, ...]) -> str:
  """Format one tuple of plan IDs with valid tuple syntax."""

  if not plan_ids:
    return "()"
  inner = ", ".join(f'"{plan_id}"' for plan_id in plan_ids)
  if len(plan_ids) == 1:
    inner = f"{inner},"
  return f"({inner})"


def _format_event_candidate_rows_by_state_literal(
  view: HsmGeneratedRuntimeView,
) -> str:
  """Format generated runtime event candidates as a Python literal."""

  parts: list[str] = []
  for state_id in view.state_ids:
    row_parts = ", ".join(
      _format_event_candidate_row_literal(row)
      for row in view.event_candidate_rows_by_state_id[state_id]
    )
    if row_parts and len(view.event_candidate_rows_by_state_id[state_id]) == 1:
      row_parts = f"{row_parts},"
    parts.append(f'"{state_id}": ({row_parts})')
  return "{" + ", ".join(parts) + "}"


def _format_event_candidate_row_literal(
  row: HsmGeneratedRuntimeEventCandidateRow,
) -> str:
  """Format one event candidate row constructor literal."""

  parts = [
    "HsmGeneratedRuntimeEventCandidateRow(",
    f'candidate_id="{row.candidate_id}", ',
    f'event_id="{row.event_id}", ',
    f'source_id="{row.source_id}", ',
    f'kind="{row.kind}"',
  ]
  if row.target_id is not None:
    parts.append(f', target_id="{row.target_id}"')
  if row.guard_plan_id is not None:
    parts.append(f', guard_plan_id="{row.guard_plan_id}"')
  if row.guard_node_id is not None:
    parts.append(f', guard_node_id="{row.guard_node_id}"')
  if row.guard_true_branch is not None:
    parts.append(
      f", guard_true_branch={_format_guard_branch_row_literal(row.guard_true_branch)}"
    )
  if row.guard_false_branch is not None:
    parts.append(
      f", guard_false_branch={_format_guard_branch_row_literal(row.guard_false_branch)}"
    )
  parts.append(
    f", activity_plan_ids={_format_plan_ids_tuple_literal(row.activity_plan_ids)})"
  )
  return "".join(parts)


def _format_guard_branch_row_literal(
  row: HsmGeneratedRuntimeGuardBranchRow,
) -> str:
  """Format one guard branch row constructor literal."""

  return (
    "HsmGeneratedRuntimeGuardBranchRow("
    f'branch_id="{row.branch_id}", '
    f'target_id="{row.target_id}", '
    f"activity_plan_ids={_format_plan_ids_tuple_literal(row.activity_plan_ids)})"
  )


def _collect_activity_plan_ids(view: HsmGeneratedRuntimeView) -> set[str]:
  """Collect every activity plan ID referenced by the generated runtime view."""

  plan_ids: set[str] = set()
  for plans_by_state in (
    view.on_initial_plan_ids_by_state_id,
    view.on_entry_plan_ids_by_state_id,
    view.on_exit_plan_ids_by_state_id,
  ):
    for state_plan_ids in plans_by_state.values():
      plan_ids.update(state_plan_ids)
  for rows in view.event_candidate_rows_by_state_id.values():
    for row in rows:
      plan_ids.update(row.activity_plan_ids)
      if row.guard_true_branch is not None:
        plan_ids.update(row.guard_true_branch.activity_plan_ids)
      if row.guard_false_branch is not None:
        plan_ids.update(row.guard_false_branch.activity_plan_ids)
  return plan_ids


def _resolve_handlers_by_plan_id(
  callable_plans_by_id: dict[str, HsmGeneratedRuntimeCallablePlan],
  plan_ids: set[str],
) -> dict[str, Callable]:
  """Import activity handlers for the selected plan IDs."""

  return {
    plan_id: _resolve_callable(
      HsmCallableRef(
        module=callable_plans_by_id[plan_id].module,
        name=callable_plans_by_id[plan_id].name,
      )
    )
    for plan_id in sorted(plan_ids)
  }


def _resolve_guard_handlers_by_plan_id(
  view: HsmGeneratedRuntimeView,
) -> dict[str, GuardHandler]:
  """Import and type-wrap guard handlers referenced by the view."""

  plan_ids = {
    row.guard_plan_id
    for rows in view.event_candidate_rows_by_state_id.values()
    for row in rows
    if row.guard_plan_id is not None
  }
  handlers_by_plan_id: dict[str, GuardHandler] = {}
  for plan_id in sorted(plan_ids):
    ref = HsmCallableRef(
      module=view.callable_plans_by_id[plan_id].module,
      name=view.callable_plans_by_id[plan_id].name,
    )
    handlers_by_plan_id[plan_id] = _wrap_guard_callable(
      _resolve_callable(ref),
      ref=ref,
    )
  return handlers_by_plan_id


def _resolve_callable(ref: HsmCallableRef):
  """Import one callable reference from its module path."""

  module = importlib.import_module(ref.module)
  return getattr(module, ref.name)


def _wrap_guard_callable(handler: Callable, *, ref: HsmCallableRef) -> GuardHandler:
  """Wrap one guard callable with a strict bool return check."""

  def _guard(ctx: object) -> bool:
    """Call the guard and enforce a boolean result."""

    result = handler(ctx)
    if isinstance(result, bool):
      return result
    raise TypeError(
      "Guard callable "
      f"'{ref.module}.{ref.name}' must return bool, got {type(result).__name__}."
    )

  setattr(_guard, "__name__", getattr(handler, "__name__", ref.name))
  return _guard
