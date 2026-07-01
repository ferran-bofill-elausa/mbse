from __future__ import annotations

"""Rendered model catalog for project viewer sessions."""

from typing import Any

from mbse.model.activity.activity_model import ActivityModel
from mbse.model.hsm.hsm_model import HsmModel
from mbse.model.project.project_registry import ProjectRegistry
from mbse_web_viewer.render.activity.activity_render import ActivityRender
from mbse_web_viewer.render.hsm.hsm_render import HsmRender


class ProjectModelCatalog:
  """Render and serve all executable project models."""

  def __init__(self, registry: ProjectRegistry) -> None:
    """Initialize the catalog from one loaded project registry."""

    self._registry = registry
    self._rendered_svgs = self._renderProjectModels(registry)

  def getModelSvgText(self, model_id: str) -> str:
    """Return the rendered SVG document for one project model id."""

    try:
      return self._rendered_svgs[model_id].getSvgText()
    except KeyError as error:
      raise KeyError(f"Unknown model_id '{model_id}'.") from error

  def getViewerModels(self) -> tuple[dict[str, object], ...]:
    """Return executable project models available to the viewer session."""

    entrypoint_id = self._registry.getEntrypointModel().getDocumentId()
    return tuple(
      {
        "model_id": model.getDocumentId(),
        "kind": "hsm" if isinstance(model, HsmModel) else "activity",
        "svg_url": f"/artifacts/models/{model.getDocumentId()}/diagram.svg",
        "is_entrypoint": model.getDocumentId() == entrypoint_id,
      }
      for model in self._registry.iterExecutableModels()
    )

  def getRenderedModels(self) -> dict[str, Any]:
    """Return rendered model objects by model id."""

    return self._rendered_svgs

  def _renderProjectModels(self, registry: ProjectRegistry) -> dict[str, Any]:
    """Render every executable project model by document id."""

    rendered_svgs: dict[str, Any] = {}
    for model in registry.iterExecutableModels():
      model_id = model.getDocumentId()
      if isinstance(model, HsmModel):
        rendered = HsmRender()
      elif isinstance(model, ActivityModel):
        rendered = ActivityRender()
      else:
        continue
      rendered.render(model)
      rendered_svgs[model_id] = rendered
    return rendered_svgs
