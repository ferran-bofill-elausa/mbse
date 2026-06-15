from __future__ import annotations

from pathlib import Path

from jinja2 import Environment
from jinja2 import FileSystemLoader
from jinja2 import StrictUndefined

from mbse_web_viewer.svg_render.render_types import HsmPreparedRenderView


TEMPLATES_DIR = Path(__file__).parent
TEMPLATE_NAME = "generator_template.dot.j2"


def render_hsm_dot(view: HsmPreparedRenderView) -> str:
  template = _build_environment().get_template(TEMPLATE_NAME)
  return template.render(view=view).strip() + "\n"


def _build_environment() -> Environment:
  return Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    undefined=StrictUndefined,
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
  )
