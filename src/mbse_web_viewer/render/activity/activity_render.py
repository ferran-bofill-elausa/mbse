from __future__ import annotations

"""Public Activity render API."""

import subprocess
from typing import Any
import xml.etree.ElementTree as ET

from jinja2 import Environment
from jinja2 import FileSystemLoader
from jinja2 import StrictUndefined

from mbse.model.activity.activity_model import ActivityModel
from mbse_web_viewer.render.activity import activity_render_helpers as helpers
from mbse_web_viewer.render.activity import activity_render_types as types


class ActivityRender:
  """Rendered Activity SVG plus lookup helpers."""

  def __init__(self) -> None:
    """ActivityRender initialization."""

    self.svg_text: str | None = None
    self.dot_source: str | None = None
    self._highlight_index: types.ActivitySvgHighlightIndex | None = None

  def render(self, model: ActivityModel) -> None:
    """Render one Activity model and store the resulting SVG lookup state."""

    prepared = self._prepareView(model)
    dot_source = self._renderDot(prepared.view)
    svg_text = self._renderDotToSvg(dot_source)
    normalized_svg, text_targets = self._normalizeSvgTextFragments(svg_text)
    rendered_ids = self._extractSvgIds(normalized_svg)
    self._validateRenderedContract(prepared.highlightable_ids, rendered_ids)
    self.svg_text = normalized_svg
    self.dot_source = dot_source
    self._highlight_index = self._buildHighlightIndex(prepared, text_targets)

  def getSvgText(self) -> str:
    """Return the rendered SVG document."""

    return self._requireSvgText()

  def getDotSource(self) -> str:
    """Return the DOT source used to produce the SVG."""

    return self._requireDotSource()

  def getInitialTransitionId(self) -> str:
    """Return the SVG id for the initial transition."""

    return self._requireHighlightIndex().initial_transition_id

  def getInitialTransitionSourceId(self) -> str:
    """Return the SVG id for the initial source node."""

    return self._requireHighlightIndex().initial_transition_source_id

  def getActionId(self, action_id: str) -> str:
    """Return the SVG id for one action."""

    return self._requireHighlightIndex().action_ids_by_action_id[action_id]

  def getDecisionId(self, decision_id: str) -> str:
    """Return the SVG id for one decision."""

    return self._requireHighlightIndex().decision_ids_by_decision_id[decision_id]

  def getFinalId(self, final_id: str) -> str:
    """Return the SVG id for one final."""

    return self._requireHighlightIndex().final_ids_by_final_id[final_id]

  def getActionTransitionId(self, action_id: str) -> str:
    """Return the SVG id for one action transition."""

    return self._requireHighlightIndex().action_transition_ids_by_action_id[action_id]

  def getDecisionTransitionId(self, decision_id: str, *, outcome: bool) -> str:
    """Return the SVG id for one decision transition branch."""

    return self._requireHighlightIndex().decision_transition_ids_by_key[
      (decision_id, outcome)
    ]

  def getActionLabelTextIds(self, action_id: str) -> tuple[str, ...]:
    """Return text fragment ids for one rendered action label."""

    return self._requireHighlightIndex().action_label_text_ids.get(action_id, ())

  def getActionExecutableTextIds(
    self,
    action_id: str,
    executable: dict[str, Any],
  ) -> tuple[str, ...]:
    """Return text fragment ids for one rendered action executable."""

    return self._requireHighlightIndex().action_executable_text_ids.get(
      (action_id, helpers.executableKey(executable)),
      (),
    )

  def getDecisionLabelTextIds(self, decision_id: str) -> tuple[str, ...]:
    """Return text fragment ids for one rendered decision label."""

    return self._requireHighlightIndex().decision_label_text_ids.get(decision_id, ())

  def getDecisionConditionTextIds(
    self,
    decision_id: str,
    condition: dict[str, Any],
  ) -> tuple[str, ...]:
    """Return text fragment ids for one rendered decision condition."""

    return self._requireHighlightIndex().decision_condition_text_ids.get(
      (decision_id, helpers.executableKey(condition)),
      (),
    )

  def getFinalLabelTextIds(self, final_id: str) -> tuple[str, ...]:
    """Return text fragment ids for one rendered final label."""

    return self._requireHighlightIndex().final_label_text_ids.get(final_id, ())

  def getTransitionLabelTextIds(self, edge_id: str) -> tuple[str, ...]:
    """Return text fragment ids for one rendered transition label."""

    return self._requireHighlightIndex().transition_label_text_ids.get(edge_id, ())

  def getInitialTransitionOwnedIds(self) -> tuple[str, ...]:
    """Return all visible SVG ids owned by the initial transition."""

    highlight_index = self._requireHighlightIndex()
    return (
      highlight_index.initial_transition_id,
      highlight_index.initial_transition_source_id,
    )

  def getActionOwnedIds(self, action_id: str) -> tuple[str, ...]:
    """Return all visible SVG ids owned by one rendered action."""

    highlight_index = self._requireHighlightIndex()
    owned_ids = [self.getActionId(action_id)]
    owned_ids.extend(highlight_index.action_label_text_ids.get(action_id, ()))
    owned_ids.extend(self._getTextIdsByFirstKeyPart(
      highlight_index.action_executable_text_ids,
      action_id,
    ))
    return tuple(dict.fromkeys(owned_ids))

  def getDecisionOwnedIds(self, decision_id: str) -> tuple[str, ...]:
    """Return all visible SVG ids owned by one rendered decision."""

    highlight_index = self._requireHighlightIndex()
    owned_ids = [self.getDecisionId(decision_id)]
    owned_ids.extend(highlight_index.decision_label_text_ids.get(decision_id, ()))
    owned_ids.extend(self._getTextIdsByFirstKeyPart(
      highlight_index.decision_condition_text_ids,
      decision_id,
    ))
    return tuple(dict.fromkeys(owned_ids))

  def getFinalOwnedIds(self, final_id: str) -> tuple[str, ...]:
    """Return all visible SVG ids owned by one rendered final node."""

    owned_ids = [self.getFinalId(final_id)]
    owned_ids.extend(self.getFinalLabelTextIds(final_id))
    return tuple(dict.fromkeys(owned_ids))

  def getTransitionOwnedIds(self, edge_id: str) -> tuple[str, ...]:
    """Return all visible SVG ids owned by one rendered transition edge."""

    owned_ids = [edge_id]
    owned_ids.extend(self.getTransitionLabelTextIds(edge_id))
    return tuple(dict.fromkeys(owned_ids))

  def getOwnedIdsForHighlightId(self, element_id: str) -> tuple[str, ...]:
    """Return the complete visible owner set for one SVG highlight id."""

    highlight_index = self._requireHighlightIndex()
    if element_id in self.getInitialTransitionOwnedIds():
      return self.getInitialTransitionOwnedIds()

    for action_id, action_svg_id in highlight_index.action_ids_by_action_id.items():
      if element_id == action_svg_id or element_id in self.getActionOwnedIds(action_id):
        return self.getActionOwnedIds(action_id)

    for decision_id, decision_svg_id in (
      highlight_index.decision_ids_by_decision_id.items()
    ):
      if (
        element_id == decision_svg_id
        or element_id in self.getDecisionOwnedIds(decision_id)
      ):
        return self.getDecisionOwnedIds(decision_id)

    for final_id, final_svg_id in highlight_index.final_ids_by_final_id.items():
      if element_id == final_svg_id or element_id in self.getFinalOwnedIds(final_id):
        return self.getFinalOwnedIds(final_id)

    for edge_id in self._iterTransitionIds():
      if element_id in self.getTransitionOwnedIds(edge_id):
        return self.getTransitionOwnedIds(edge_id)

    return (element_id,)

  def _prepareView(self, model: ActivityModel) -> types.RenderBuildResult:
    """Prepare render artifacts for one Activity model."""

    id_registry = helpers.SvgIdRegistry()
    initial_source_id = id_registry.make("initial_source")
    initial_transition_id = id_registry.make(
      f"initial_transition_to_{model.getInitialTargetId()}"
    )
    action_ids_by_action_id: dict[str, str] = {}
    decision_ids_by_decision_id: dict[str, str] = {}
    final_ids_by_final_id: dict[str, str] = {}
    action_transition_ids_by_action_id: dict[str, str] = {}
    decision_transition_ids_by_key: dict[tuple[str, bool], str] = {}
    nodes: list[types.RenderActivityNode] = []
    edges: list[types.RenderActivityEdge] = []

    for action in model.getActions():
      action_id = action["id"]
      svg_id = id_registry.make(f"action_{action_id}")
      action_ids_by_action_id[action_id] = svg_id
      nodes.append(
        types.RenderActivityNode(
          svg_id=svg_id,
          element_id=action_id,
          shape="box",
          label_lines=helpers.actionLabelLines(action),
        )
      )

    for decision in model.getDecisions():
      decision_id = decision["id"]
      svg_id = id_registry.make(f"decision_{decision_id}")
      decision_ids_by_decision_id[decision_id] = svg_id
      nodes.append(
        types.RenderActivityNode(
          svg_id=svg_id,
          element_id=decision_id,
          shape="diamond",
          label_lines=helpers.decisionLabelLines(decision),
        )
      )

    for final in model.getFinals():
      final_id = final["id"]
      svg_id = id_registry.make(f"final_{final_id}")
      final_ids_by_final_id[final_id] = svg_id
      nodes.append(
        types.RenderActivityNode(
          svg_id=svg_id,
          element_id=final_id,
          shape="doublecircle",
          label_lines=helpers.finalLabelLines(final),
        )
      )

    node_ids_by_element_id = {
      **action_ids_by_action_id,
      **decision_ids_by_decision_id,
      **final_ids_by_final_id,
    }
    edges.append(
      types.RenderActivityEdge(
        svg_id=initial_transition_id,
        source_id=initial_source_id,
        target_id=node_ids_by_element_id[model.getInitialTargetId()],
        label_line=None,
      )
    )

    for action in model.getActions():
      action_id = action["id"]
      target_id = action["transition"]["target_id"]
      edge_id = id_registry.make(f"action_transition_{action_id}_to_{target_id}")
      action_transition_ids_by_action_id[action_id] = edge_id
      edges.append(
        types.RenderActivityEdge(
          svg_id=edge_id,
          source_id=action_ids_by_action_id[action_id],
          target_id=node_ids_by_element_id[target_id],
          label_line=None,
        )
      )

    for decision in model.getDecisions():
      decision_id = decision["id"]
      for outcome, transition_key, label in (
        (True, "true_transition", "true"),
        (False, "false_transition", "false"),
      ):
        target_id = decision[transition_key]["target_id"]
        edge_id = id_registry.make(
          f"decision_transition_{decision_id}_{label}_to_{target_id}"
        )
        decision_transition_ids_by_key[(decision_id, outcome)] = edge_id
        edges.append(
          types.RenderActivityEdge(
            svg_id=edge_id,
            source_id=decision_ids_by_decision_id[decision_id],
            target_id=node_ids_by_element_id[target_id],
            label_line=helpers.transitionLabelLine(edge_id, label),
          )
        )

    highlightable_ids = tuple(
      [initial_source_id, initial_transition_id]
      + list(action_ids_by_action_id.values())
      + list(decision_ids_by_decision_id.values())
      + list(final_ids_by_final_id.values())
      + list(action_transition_ids_by_action_id.values())
      + list(decision_transition_ids_by_key.values())
    )
    return types.RenderBuildResult(
      view=types.RenderView(
        document_id=model.getDocumentId(),
        initial_source_id=initial_source_id,
        nodes=tuple(nodes),
        edges=tuple(edges),
      ),
      highlightable_ids=highlightable_ids,
      initial_transition_id=initial_transition_id,
      initial_transition_source_id=initial_source_id,
      action_ids_by_action_id=action_ids_by_action_id,
      decision_ids_by_decision_id=decision_ids_by_decision_id,
      final_ids_by_final_id=final_ids_by_final_id,
      action_transition_ids_by_action_id=action_transition_ids_by_action_id,
      decision_transition_ids_by_key=decision_transition_ids_by_key,
    )

  def _renderDot(self, view: types.RenderView) -> str:
    """Render one prepared Activity view to DOT."""

    template = Environment(
      loader=FileSystemLoader(helpers.TEMPLATES_DIR),
      undefined=StrictUndefined,
      autoescape=False,
      trim_blocks=True,
      lstrip_blocks=True,
    ).get_template(helpers.TEMPLATE_NAME)
    return template.render(view=view).strip() + "\n"

  def _renderDotToSvg(self, dot_source: str) -> str:
    """Render one DOT document to SVG."""

    try:
      completed = subprocess.run(
        args=["dot", "-Tsvg"],
        input=dot_source,
        text=True,
        capture_output=True,
        check=False,
        timeout=10.0,
      )
    except FileNotFoundError as error:
      raise RuntimeError(
        "Graphviz is required to render MBSE diagrams. Install Graphviz and "
        "ensure 'dot' is on PATH."
      ) from error
    except subprocess.TimeoutExpired as error:
      raise RuntimeError(
        f"Graphviz renderer timed out after {error.timeout} seconds."
      ) from error

    if completed.returncode != 0:
      raise RuntimeError(
        "Graphviz renderer failed with exit code "
        f"{completed.returncode}: {completed.stderr.strip()}"
      )

    svg_text = completed.stdout
    try:
      root = ET.fromstring(svg_text)
    except ET.ParseError as error:
      raise RuntimeError(
        f"Graphviz renderer returned malformed SVG: {error}"
      ) from error
    if not root.tag.endswith("svg"):
      raise RuntimeError("Graphviz renderer returned a non-SVG document.")
    return svg_text

  def _extractSvgIds(self, svg_text: str) -> tuple[str, ...]:
    """Extract public SVG ids from one rendered SVG document."""

    root = ET.fromstring(svg_text)
    ids = tuple(
      element_id
      for element in root.iter()
      if (element_id := element.attrib.get("id")) is not None
    )
    duplicates = helpers.duplicateValues(ids)
    if duplicates:
      raise RuntimeError(f"Rendered SVG contains duplicate id '{duplicates[0]}'.")
    return ids

  def _normalizeSvgTextFragments(self, svg_text: str):
    """Normalize Graphviz SVG text fragments for stable highlighting."""

    ET.register_namespace("", helpers.SVG_NAMESPACE)
    root = ET.fromstring(svg_text)
    collector = helpers.TextTargetCollector()
    helpers.collapseTextFragmentRuns(root, collector)
    for element in root.iter():
      if element.tag == helpers.ANCHOR_TAG:
        helpers.normalizeAnchorTarget(element, collector)
    helpers.stripGeneratedAnchorGroupIds(root)
    return ET.tostring(root, encoding="unicode"), collector.build()

  def _validateRenderedContract(
    self,
    expected_ids: tuple[str, ...],
    rendered_ids: tuple[str, ...],
  ) -> None:
    """Require all expected public ids to exist in the rendered SVG."""

    rendered_id_set = set(rendered_ids)
    for expected_id in expected_ids:
      if expected_id not in rendered_id_set:
        raise RuntimeError(f"Rendered SVG is missing expected id '{expected_id}'.")

  def _buildHighlightIndex(
    self,
    prepared: types.RenderBuildResult,
    text_targets: types.NormalizedSvgTextTargets,
  ) -> types.ActivitySvgHighlightIndex:
    """Build the lookup index for the current rendered Activity."""

    return types.ActivitySvgHighlightIndex(
      initial_transition_id=prepared.initial_transition_id,
      initial_transition_source_id=prepared.initial_transition_source_id,
      action_ids_by_action_id=prepared.action_ids_by_action_id,
      decision_ids_by_decision_id=prepared.decision_ids_by_decision_id,
      final_ids_by_final_id=prepared.final_ids_by_final_id,
      action_transition_ids_by_action_id=prepared.action_transition_ids_by_action_id,
      decision_transition_ids_by_key=prepared.decision_transition_ids_by_key,
      action_label_text_ids=text_targets.action_label_ids,
      action_executable_text_ids=text_targets.action_executable_ids,
      decision_label_text_ids=text_targets.decision_label_ids,
      decision_condition_text_ids=text_targets.decision_condition_ids,
      final_label_text_ids=text_targets.final_label_ids,
      transition_label_text_ids=text_targets.transition_label_ids,
      highlightable_ids=prepared.highlightable_ids,
    )

  def _requireSvgText(self) -> str:
    """Return rendered SVG text or fail if render has not run."""

    if self.svg_text is None:
      raise RuntimeError("Activity has not been rendered.")
    return self.svg_text

  def _requireDotSource(self) -> str:
    """Return rendered DOT source or fail if render has not run."""

    if self.dot_source is None:
      raise RuntimeError("Activity has not been rendered.")
    return self.dot_source

  def _requireHighlightIndex(self) -> types.ActivitySvgHighlightIndex:
    """Return rendered highlight index or fail if render has not run."""

    if self._highlight_index is None:
      raise RuntimeError("Activity has not been rendered.")
    return self._highlight_index

  def _getTextIdsByFirstKeyPart(self, text_ids_by_key, first_key_part: str) -> list[str]:
    """Return text ids whose semantic key starts with one SVG id."""

    ids: list[str] = []
    for key, text_ids in text_ids_by_key.items():
      if key[0] == first_key_part:
        ids.extend(text_ids)
    return ids

  def _iterTransitionIds(self):
    """Yield all rendered transition SVG ids."""

    highlight_index = self._requireHighlightIndex()
    yield highlight_index.initial_transition_id
    yield from highlight_index.action_transition_ids_by_action_id.values()
    yield from highlight_index.decision_transition_ids_by_key.values()
