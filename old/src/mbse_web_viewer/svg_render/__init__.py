"""Public SVG rendering API."""

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
from mbse_web_viewer.svg_render.graphviz.prepared_document import PreparedGraphvizDocument
from mbse_web_viewer.svg_render.graphviz.prepared_document import load_prepared_document
from mbse_web_viewer.svg_render.graphviz.prepared_document import validate_prepared_document
from mbse_web_viewer.svg_render.graphviz.runner import render_svg
from mbse_web_viewer.svg_render.render import prepare_hsm_render_view

__all__ = [
  "PreparedGraphvizDocument",
  "extract_svg_ids",
  "load_prepared_document",
  "normalize_svg_text_fragments",
  "prepare_hsm_render_view",
  "render_hsm_dot",
  "render_svg",
  "validate_prepared_document",
  "validate_rendered_contract",
]
