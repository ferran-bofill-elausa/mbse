from __future__ import annotations

import subprocess
import xml.etree.ElementTree as ET


class GraphvizRenderError(RuntimeError):
  pass


def render_svg(
  dot_source: str,
  *,
  command: tuple[str, ...] | None = None,
  timeout_seconds: float = 10.0,
) -> str:
  resolved_command = command or ("dot", "-Tsvg")
  try:
    completed = subprocess.run(
      args=list(resolved_command),
      input=dot_source,
      text=True,
      capture_output=True,
      check=False,
      timeout=timeout_seconds,
    )
  except FileNotFoundError as error:
    raise GraphvizRenderError(f"Graphviz renderer is unavailable: {error}") from error
  except subprocess.TimeoutExpired as error:
    raise GraphvizRenderError(
      f"Graphviz renderer timed out after {error.timeout} seconds."
    ) from error

  if completed.returncode != 0:
    raise GraphvizRenderError(
      "Graphviz renderer failed with exit code "
      f"{completed.returncode}: {completed.stderr.strip()}"
    )

  svg_text = completed.stdout
  _validate_svg_document(svg_text)
  return svg_text


def _validate_svg_document(svg_text: str) -> None:
  try:
    root = ET.fromstring(svg_text)
  except ET.ParseError as error:
    raise GraphvizRenderError(
      f"Graphviz renderer returned malformed SVG: {error}"
    ) from error

  if not root.tag.endswith("svg"):
    raise GraphvizRenderError(
      "Graphviz renderer returned a non-SVG document."
    )
