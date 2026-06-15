from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from mbse.model.hsm import load_hsm_document
from mbse_web_viewer.svg_render.graphviz.contract_validation import (
  extract_svg_ids,
)
from mbse_web_viewer.svg_render.graphviz.contract_validation import (
  normalize_svg_text_fragments,
)
from mbse_web_viewer.svg_render.graphviz.contract_validation import (
  validate_rendered_contract,
)
from mbse_web_viewer.svg_render.graphviz.generator.generator import render_hsm_dot
from mbse_web_viewer.svg_render.graphviz.runner import render_svg
from mbse_web_viewer.svg_render.graphviz.prepared_document import PreparedGraphvizDocument
from mbse_web_viewer.svg_render.graphviz.prepared_document import load_prepared_document
from mbse_web_viewer.svg_render.graphviz.prepared_document import validate_prepared_document
from mbse_web_viewer.svg_render.render import prepare_hsm_render_view

from .viewer_state_types import ViewerAppState


def build_viewer_session(
  prepared_document_path: Path,
  output_dir: Path,
  *,
  graphviz_command: tuple[str, ...] | None = None,
) -> ViewerAppState:
  prepared_document_text = prepared_document_path.read_text(encoding="utf-8")
  payload = json.loads(prepared_document_text)
  (
    document,
    prepared_document_name,
    prepared_document_text,
    generated_from_hsm,
  ) = _load_session_document(
    payload,
    fallback_name=prepared_document_path.name,
    source_text=prepared_document_text,
  )
  rendered_svg = render_svg(document.dot_source, command=graphviz_command)
  normalized_svg = normalize_svg_text_fragments(rendered_svg)
  svg_text = normalized_svg.svg_text
  rendered_ids = extract_svg_ids(svg_text)
  validate_rendered_contract(document.highlightable_ids, rendered_ids)

  session = ViewerAppState(
    document_id=document.document_id,
    svg_url="/artifacts/diagram.svg",
    highlightable_ids=document.highlightable_ids,
    text_targets=_resolve_text_targets(
      document.viewer_text_targets,
      normalized_svg.text_targets,
    ),
  )
  if generated_from_hsm:
    document = PreparedGraphvizDocument(
      document_id=document.document_id,
      dot_source=document.dot_source,
      highlightable_ids=document.highlightable_ids,
      viewer_text_targets=normalized_svg.text_targets,
    )
    prepared_document_text = json.dumps(asdict(document), indent=2)
  write_viewer_session_artifacts(
    output_dir,
    prepared_document_name=prepared_document_name,
    prepared_document_text=prepared_document_text,
    svg_text=svg_text,
  )
  return session


def write_viewer_session_artifacts(
  output_dir: Path,
  *,
  prepared_document_name: str,
  prepared_document_text: str,
  svg_text: str,
) -> None:
  output_dir.mkdir(parents=True, exist_ok=True)
  (output_dir / prepared_document_name).write_text(
    prepared_document_text,
    encoding="utf-8",
  )
  (output_dir / "diagram.svg").write_text(svg_text, encoding="utf-8")


def _load_session_document(
  payload: dict[str, object],
  *,
  fallback_name: str,
  source_text: str,
) -> tuple[
  PreparedGraphvizDocument,
  str,
  str,
  bool,
]:
  if "schema_version" not in payload:
    document = load_prepared_document(payload)
    return document, fallback_name, source_text, False

  hsm_document = load_hsm_document(payload)
  render_view = prepare_hsm_render_view(hsm_document)
  prepared_document = PreparedGraphvizDocument(
    document_id=render_view.document_id,
    dot_source=render_hsm_dot(render_view),
    highlightable_ids=render_view.highlightable_ids,
  )
  validate_prepared_document(prepared_document)
  return (
    prepared_document,
    "prepared-document.json",
    json.dumps(asdict(prepared_document), indent=2),
    True,
  )


def _resolve_text_targets(
  prepared_targets,
  normalized_targets,
):
  if any(
    (
      prepared_targets.lifecycle_section_ids,
      prepared_targets.lifecycle_activity_ids,
      prepared_targets.external_transition_label_ids,
      prepared_targets.external_transition_activity_ids,
      prepared_targets.internal_transition_section_ids,
      prepared_targets.internal_transition_event_ids,
      prepared_targets.internal_transition_activity_ids,
    )
  ):
    return prepared_targets
  return normalized_targets
