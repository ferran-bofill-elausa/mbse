from __future__ import annotations

"""Public HSM render API."""

import subprocess
from typing import Any
import xml.etree.ElementTree as ET

from jinja2 import Environment
from jinja2 import FileSystemLoader
from jinja2 import StrictUndefined

from mbse.model.hsm.hsm_model import HsmModel
from mbse_web_viewer.render.hsm import hsm_render_helpers as helpers
from mbse_web_viewer.render.hsm import hsm_render_types as types


class HsmRender:
  """Rendered HSM SVG plus lookup helpers."""

  def __init__(self) -> None:
    """HsmRender initialization."""

    self.svg_text: str | None = None
    self.dot_source: str | None = None
    self._highlight_index: types.HsmSvgHighlightIndex | None = None

  def render(self, model: HsmModel) -> None:
    """Render one HSM model and store the resulting SVG lookup state."""

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

  def getStateId(self, state_id: str) -> str:
    """Return the SVG id for one state."""

    return self._requireHighlightIndex().state_ids_by_state_id[state_id]

  def getStateLabelTextIds(self, state_id: str) -> tuple[str, ...]:
    """Return text fragment ids for one rendered state label."""

    return self._requireHighlightIndex().state_label_text_ids.get(state_id, ())

  def getRootInitialTransitionId(self) -> str:
    """Return the SVG id for the root initial transition."""

    return self._requireHighlightIndex().initial_transition_ids_by_owner_id[None]

  def getInitialTransitionId(self, state_id: str) -> str:
    """Return the SVG id for one state's local initial transition."""

    return self._requireHighlightIndex().initial_transition_ids_by_owner_id[state_id]

  def getRootInitialTransitionSourceId(self) -> str:
    """Return the SVG id for the root initial-transition source node."""

    return self._requireHighlightIndex().initial_transition_source_ids_by_owner_id[None]

  def getInitialTransitionSourceId(self, state_id: str) -> str:
    """Return the SVG id for one state's local initial-transition source node."""

    return self._requireHighlightIndex().initial_transition_source_ids_by_owner_id[state_id]

  def getInitialTransitionLabelTextIds(self, edge_id: str) -> tuple[str, ...]:
    """Return text fragment ids for one initial-transition label."""

    return self._requireHighlightIndex().initial_transition_label_text_ids.get(edge_id, ())

  def getInitialTransitionActivityTextIds(
    self,
    edge_id: str,
    activity: dict[str, str] | str,
  ) -> tuple[str, ...]:
    """Return text fragment ids for one initial-transition activity label."""

    return self._requireHighlightIndex().initial_transition_activity_text_ids.get(
      (edge_id, helpers.callableKey(activity)),
      (),
    )

  def getExternalTransitionIds(
    self,
    source_state_id: str,
    event_id: str,
    target_state_id: str,
  ) -> tuple[str, ...]:
    """Return matching SVG ids for one unguarded external transition shape."""

    return self._requireHighlightIndex().external_transition_ids_by_key[
      (source_state_id, event_id, target_state_id)
    ]

  def getGuardedTransitionIds(
    self,
    source_state_id: str,
    event_id: str,
  ) -> tuple[str, ...]:
    """Return matching SVG ids for one guarded external transition entry edge."""

    return self._requireHighlightIndex().guarded_transition_ids_by_key[
      (source_state_id, event_id)
    ]

  def getGuardNodeIds(
    self,
    source_state_id: str,
    event_id: str,
  ) -> tuple[str, ...]:
    """Return matching SVG ids for one rendered guard node."""

    return self._requireHighlightIndex().guard_node_ids_by_key[
      (source_state_id, event_id)
    ]

  def getGuardNodeTextIds(
    self,
    source_state_id: str,
    event_id: str,
  ) -> tuple[str, ...]:
    """Return text fragment ids for one rendered guard node label."""

    return self._requireHighlightIndex().guard_node_text_ids_by_key.get(
      (source_state_id, event_id),
      (),
    )

  def getGuardBranchIds(
    self,
    source_state_id: str,
    event_id: str,
    *,
    outcome: bool,
    target_state_id: str,
  ) -> tuple[str, ...]:
    """Return matching SVG ids for one rendered guard branch edge."""

    return self._requireHighlightIndex().guard_branch_ids_by_key[
      (source_state_id, event_id, outcome, target_state_id)
    ]

  def getInternalTransitionIds(
    self,
    state_id: str,
    event_id: str,
  ) -> tuple[str, ...]:
    """Return matching SVG ids for one internal transition line."""

    return self._requireHighlightIndex().internal_transition_ids_by_key[
      (state_id, event_id)
    ]

  def getStateHookSectionTextIds(
    self,
    state_id: str,
    section_name: str,
  ) -> tuple[str, ...]:
    """Return text fragment ids for one state-hook section title."""

    return self._requireHighlightIndex().state_hook_section_text_ids.get(
      (state_id, section_name),
      (),
    )

  def getStateHookActivityTextIds(
    self,
    state_id: str,
    section_name: str,
    activity: dict[str, str] | str,
  ) -> tuple[str, ...]:
    """Return text fragment ids for one state-hook activity label."""

    return self._requireHighlightIndex().state_hook_activity_text_ids.get(
      (state_id, section_name, helpers.callableKey(activity)),
      (),
    )

  def getExternalTransitionLabelTextIds(self, edge_id: str) -> tuple[str, ...]:
    """Return text fragment ids for one external-transition label."""

    return self._requireHighlightIndex().external_transition_label_text_ids.get(
      edge_id,
      (),
    )

  def getExternalTransitionActivityTextIds(
    self,
    edge_id: str,
    activity: dict[str, str] | str,
  ) -> tuple[str, ...]:
    """Return text fragment ids for one external-transition activity label."""

    return self._requireHighlightIndex().external_transition_activity_text_ids.get(
      (edge_id, helpers.callableKey(activity)),
      (),
    )

  def getInternalTransitionSectionTextIds(
    self,
    state_id: str,
    event_id: str,
  ) -> tuple[str, ...]:
    """Return text fragment ids for the internal-transitions section title."""

    return self._requireHighlightIndex().internal_transition_section_text_ids.get(
      (state_id, event_id),
      (),
    )

  def getInternalTransitionEventTextIds(self, transition_id: str) -> tuple[str, ...]:
    """Return text fragment ids for one internal-transition event label."""

    return self._requireHighlightIndex().internal_transition_event_text_ids.get(
      transition_id,
      (),
    )

  def getInternalTransitionActivityTextIds(
    self,
    transition_id: str,
    activity: dict[str, str] | str,
  ) -> tuple[str, ...]:
    """Return text fragment ids for one internal-transition activity label."""

    return self._requireHighlightIndex().internal_transition_activity_text_ids.get(
      (transition_id, helpers.callableKey(activity)),
      (),
    )

  def _prepareView(self, model: HsmModel):
    """Prepare render artifacts for one HSM model."""

    id_registry = helpers.SvgIdRegistry()
    routing_helpers = helpers.RoutingHelperRegistry()
    event_labels = {
      event["id"]: helpers.formatEventLabel(event)
      for event in model.getEvents()
    }
    state_ids_by_state_id: dict[str, str] = {}
    initial_transition_ids_by_owner_id: dict[str | None, str] = {}
    initial_transition_source_ids_by_owner_id: dict[str | None, str] = {}
    external_transition_ids_by_key: dict[tuple[str, str, str], list[str]] = {}
    guarded_transition_ids_by_key: dict[tuple[str, str], list[str]] = {}
    guard_node_ids_by_key: dict[tuple[str, str], list[str]] = {}
    guard_branch_ids_by_key: dict[tuple[str, str, bool, str], list[str]] = {}
    internal_transition_ids_by_key: dict[tuple[str, str], list[str]] = {}
    internal_transition_owner_by_id: dict[str, tuple[str, str]] = {}

    state_nodes = helpers.buildStateNodes(
      model,
      model.getStates(),
      parent_svg_id=None,
      depth=0,
      event_labels=event_labels,
      id_registry=id_registry,
      state_ids_by_state_id=state_ids_by_state_id,
      internal_transition_ids_by_key=internal_transition_ids_by_key,
      internal_transition_owner_by_id=internal_transition_owner_by_id,
    )
    compound_state_ids = {
      state_id
      for state_id in state_ids_by_state_id
      if model.getChildStates(state_id)
    }

    root_initial_target_id = model.getRootInitialTargetId()
    root_initial_id = id_registry.make(
      f"root_initial_transition_to_{root_initial_target_id}"
    )
    root_initial_source_id = routing_helpers.rootInitialSource(root_initial_id)
    initial_transition_ids_by_owner_id[None] = root_initial_id
    initial_transition_source_ids_by_owner_id[None] = root_initial_source_id
    initial_edges = [
      helpers.prepareInitialEdge(
        source_id=root_initial_source_id,
        source_cluster_svg_id=None,
        target_state_id=root_initial_target_id,
        svg_id=root_initial_id,
        label_line=None,
        state_ids_by_state_id=state_ids_by_state_id,
        compound_state_ids=compound_state_ids,
        routing_helpers=routing_helpers,
      )
    ]
    guard_nodes: list[types.RenderGuardNode] = []
    transition_edges: list[types.RenderTransitionEdge] = []

    for state in model.iterStates():
      state_id = state["id"]

      if model.hasStateInitialTransition(state_id):
        target_state_id = model.getStateInitialTargetId(state_id)
        initial_id = id_registry.make(
          f"initial_transition_{state_id}_to_{target_state_id}"
        )
        initial_source_id = routing_helpers.localInitialSource(state_ids_by_state_id[state_id])
        initial_transition_ids_by_owner_id[state_id] = initial_id
        initial_transition_source_ids_by_owner_id[state_id] = initial_source_id
        initial_edges.append(
          helpers.prepareInitialEdge(
            source_id=initial_source_id,
            source_cluster_svg_id=state_ids_by_state_id[state_id],
            target_state_id=target_state_id,
            svg_id=initial_id,
            label_line=helpers.formatInitialTransitionLabel(
              initial_id,
              model.getStateInitialTransitionActivities(state_id),
            ),
            state_ids_by_state_id=state_ids_by_state_id,
            compound_state_ids=compound_state_ids,
            routing_helpers=routing_helpers,
          )
        )

      for transition in model.getOutgoingExternalTransitions(state_id):
        event_id = transition["event_id"]
        guard_condition = transition.get("guard_condition")

        if guard_condition is None:
          target_state_id = transition["target_id"]
          edge_id = id_registry.make(
            f"external_transition_{state_id}_{event_id}_to_{target_state_id}"
          )
          external_transition_ids_by_key.setdefault(
            (state_id, event_id, target_state_id),
            [],
          ).append(edge_id)
          transition_edges.append(
            helpers.prepareTransitionEdge(
              svg_id=edge_id,
              source_state_id=state_id,
              target_state_id=target_state_id,
              label_line=helpers.formatExternalTransitionLabel(
                edge_id,
                transition,
                event_labels,
              ),
              state_ids_by_state_id=state_ids_by_state_id,
              compound_state_ids=compound_state_ids,
              routing_helpers=routing_helpers,
            )
          )
          continue

        guard_edge_id = id_registry.make(f"guarded_transition_{state_id}_{event_id}")
        guard_node_id = id_registry.make(f"guard_node_{state_id}_{event_id}")
        guarded_transition_ids_by_key.setdefault((state_id, event_id), []).append(
          guard_edge_id
        )
        guard_node_ids_by_key.setdefault((state_id, event_id), []).append(
          guard_node_id
        )
        guard_nodes.append(
          types.RenderGuardNode(
            svg_id=guard_node_id,
            title_line=types.RenderTextLine(
              fragments=(
                types.RenderTextFragment(
                  text=helpers.callableLabel(guard_condition["guard_activity"]),
                  target_payload=f"guard_node_text|{state_id}|{event_id}",
                ),
              )
            ),
          )
        )
        transition_edges.append(
          helpers.prepareTransitionEdge(
            svg_id=guard_edge_id,
            source_state_id=state_id,
            target_state_id=None,
            label_line=helpers.formatExternalTransitionLabel(
              guard_edge_id,
              transition,
              event_labels,
            ),
            state_ids_by_state_id=state_ids_by_state_id,
            compound_state_ids=compound_state_ids,
            routing_helpers=routing_helpers,
            explicit_target_svg_id=guard_node_id,
          )
        )

        for outcome, branch_key in ((True, "true_branch"), (False, "false_branch")):
          branch = guard_condition[branch_key]
          branch_edge_id = id_registry.make(
            f"guard_branch_{state_id}_{event_id}_{'true' if outcome else 'false'}_to_{branch['target_id']}"
          )
          guard_branch_ids_by_key.setdefault(
            (state_id, event_id, outcome, branch["target_id"]),
            [],
          ).append(branch_edge_id)
          transition_edges.append(
            helpers.prepareTransitionEdge(
              svg_id=branch_edge_id,
              source_state_id=None,
              target_state_id=branch["target_id"],
              label_line=helpers.formatGuardBranchLabel(
                branch_edge_id,
                outcome=outcome,
                branch=branch,
              ),
              state_ids_by_state_id=state_ids_by_state_id,
              compound_state_ids=compound_state_ids,
              routing_helpers=routing_helpers,
              explicit_source_svg_id=guard_node_id,
            )
          )

    highlightable_ids = tuple(
      list(state_ids_by_state_id.values())
      + list(initial_transition_ids_by_owner_id.values())
      + list(initial_transition_source_ids_by_owner_id.values())
      + [guard.svg_id for guard in guard_nodes]
      + [edge.svg_id for edge in transition_edges]
    )
    return types.RenderBuildResult(
      view=types.RenderView(
        document_id=model.getDocumentId(),
        state_nodes=tuple(state_nodes),
        guard_nodes=tuple(guard_nodes),
        routing_helpers=routing_helpers.ordered(),
        initial_edges=tuple(initial_edges),
        transition_edges=tuple(transition_edges),
      ),
      highlightable_ids=highlightable_ids,
      state_ids_by_state_id=state_ids_by_state_id,
      initial_transition_ids_by_owner_id=initial_transition_ids_by_owner_id,
      initial_transition_source_ids_by_owner_id=initial_transition_source_ids_by_owner_id,
      external_transition_ids_by_key={
        key: tuple(value)
        for key, value in external_transition_ids_by_key.items()
      },
      guarded_transition_ids_by_key={
        key: tuple(value)
        for key, value in guarded_transition_ids_by_key.items()
      },
      guard_node_ids_by_key={
        key: tuple(value)
        for key, value in guard_node_ids_by_key.items()
      },
      guard_branch_ids_by_key={
        key: tuple(value)
        for key, value in guard_branch_ids_by_key.items()
      },
      internal_transition_ids_by_key={
        key: tuple(value)
        for key, value in internal_transition_ids_by_key.items()
      },
      internal_transition_owner_by_id=internal_transition_owner_by_id,
    )

  def _renderDot(self, view) -> str:
    """Render one prepared HSM view to DOT."""

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
      raise RuntimeError(f"Graphviz renderer is unavailable: {error}") from error
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

  def _buildHighlightIndex(self, prepared, text_targets) -> types.HsmSvgHighlightIndex:
    """Build the lookup index for the current rendered HSM."""

    internal_transition_section_text_ids: dict[tuple[str, str], tuple[str, ...]] = {}
    for owner in prepared.internal_transition_owner_by_id.values():
      internal_transition_section_text_ids[owner] = text_targets.internal_transition_section_ids.get(
        owner[0],
        (),
      )

    return types.HsmSvgHighlightIndex(
      state_ids_by_state_id=prepared.state_ids_by_state_id,
      state_label_text_ids=text_targets.state_label_ids,
      initial_transition_ids_by_owner_id=prepared.initial_transition_ids_by_owner_id,
      initial_transition_source_ids_by_owner_id=prepared.initial_transition_source_ids_by_owner_id,
      initial_transition_label_text_ids=text_targets.initial_transition_label_ids,
      initial_transition_activity_text_ids=text_targets.initial_transition_activity_ids,
      external_transition_ids_by_key=prepared.external_transition_ids_by_key,
      guarded_transition_ids_by_key=prepared.guarded_transition_ids_by_key,
      guard_node_ids_by_key=prepared.guard_node_ids_by_key,
      guard_branch_ids_by_key=prepared.guard_branch_ids_by_key,
      guard_node_text_ids_by_key=text_targets.guard_node_text_ids,
      internal_transition_ids_by_key=prepared.internal_transition_ids_by_key,
      state_hook_section_text_ids=text_targets.state_hook_section_ids,
      state_hook_activity_text_ids=text_targets.state_hook_activity_ids,
      external_transition_label_text_ids=text_targets.external_transition_label_ids,
      external_transition_activity_text_ids=text_targets.external_transition_activity_ids,
      internal_transition_section_text_ids=internal_transition_section_text_ids,
      internal_transition_event_text_ids=text_targets.internal_transition_event_ids,
      internal_transition_activity_text_ids=text_targets.internal_transition_activity_ids,
      highlightable_ids=prepared.highlightable_ids,
    )

  def _requireSvgText(self) -> str:
    """Return rendered SVG text or fail if render has not run."""

    if self.svg_text is None:
      raise RuntimeError("HSM has not been rendered.")
    return self.svg_text

  def _requireDotSource(self) -> str:
    """Return rendered DOT source or fail if render has not run."""

    if self.dot_source is None:
      raise RuntimeError("HSM has not been rendered.")
    return self.dot_source
  
  def _requireHighlightIndex(self) -> types.HsmSvgHighlightIndex:
    """Return rendered highlight index or fail if render has not run."""

    if self._highlight_index is None:
      raise RuntimeError("HSM has not been rendered.")
    return self._highlight_index
