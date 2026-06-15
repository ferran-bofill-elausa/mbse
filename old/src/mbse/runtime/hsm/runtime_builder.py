from __future__ import annotations

from pathlib import Path

from mbse.model.hsm import HsmDocument
from mbse.model.hsm import load_hsm_document

from .generator import generator as generator_module
from .generator.generator import load_generated_runtime
from .runtime import HsmRuntime
from .runtime_model.runtime_model_builder import derive_event_handler_slot_order
from .runtime_model.runtime_model_builder import prepare_hsm_generated_runtime_view


def build_hsm_runtime(
  machine: dict[str, object] | HsmDocument,
  *,
  persist_generated_runtime: bool = True,
  generated_runtime_output_dir: str | Path | None = None,
) -> HsmRuntime:
  """Build a ready-to-run HSM runtime from raw payload or model."""

  event_handler_slot_order = derive_event_handler_slot_order(machine)
  document = machine if isinstance(machine, HsmDocument) else load_hsm_document(machine)
  view = prepare_hsm_generated_runtime_view(
    document,
    event_handler_slot_order=event_handler_slot_order,
  )
  output_path = None
  if persist_generated_runtime:
    output_dir = Path(
      generated_runtime_output_dir
      or generator_module.DEFAULT_GENERATED_RUNTIME_OUTPUT_DIR
    )
    output_path = output_dir / f"{view.document_id}.py"
  generated_runtime = load_generated_runtime(view, output_path=output_path)
  return HsmRuntime(
    generated_runtime,
    variables=document.variables,
    event_ids=tuple(event.id for event in document.events),
  )
