from __future__ import annotations

import re

from mbse.model.hsm import load_hsm_document
from mbse_web_viewer.svg_render import prepare_hsm_render_view
from mbse_web_viewer.svg_render import render_hsm_dot
from tests.support.hsm_payloads import hsm_document
from tests.support.hsm_payloads import hsm_external_transition
from tests.support.hsm_payloads import hsm_guard
from tests.support.hsm_payloads import hsm_guard_branch
from tests.support.hsm_payloads import hsm_initial
from tests.support.hsm_payloads import hsm_internal_transition
from tests.support.hsm_payloads import hsm_state


def _strip_text_markers(value: str) -> str:
  if hasattr(value, "text"):
    value = value.text
  value = re.sub(r"__MBSE_START__[\s\S]*?__", "", value)
  value = re.sub(r"__MBSE_END__[\s\S]*?__", "", value)
  return value


def _callable_ref(name: str) -> dict[str, str]:
  return {
    "module": "tests.support.hsm_callable_fixtures",
    "name": name,
  }


def _hierarchical_payload() -> dict[str, object]:
  return hsm_document(
    "door_machine",
    variables=[{"id": "count", "default": 0}],
    events=[{"id": "open_evt", "parameters": [{"name": "source"}]}],
    initial_transition=hsm_initial("machine_init", "parent"),
    states=[
      hsm_state(
        "parent",
        label="Parent",
        states=[
          hsm_state("child_a", label="Child A"),
          hsm_state("child_b", label="Child B"),
        ],
        initial_transition=hsm_initial("parent_init", "child_a"),
        external_transitions=[
          hsm_external_transition("parent_to_sibling", target_id="sibling")
        ],
      ),
      hsm_state(
        "sibling",
        label="Sibling",
        external_transitions=[
          hsm_external_transition(
            "sibling_to_child_b",
            target_id="child_b",
            event_id="open_evt",
          )
        ],
      ),
    ],
  )


def _deep_hierarchy_payload() -> dict[str, object]:
  return hsm_document(
    "depth_machine",
    initial_transition=hsm_initial("machine_init", "parent"),
    states=[
      hsm_state(
        "parent",
        label="Parent",
        states=[
          hsm_state(
            "child",
            label="Child",
            states=[hsm_state("grandchild", label="Grandchild")],
            initial_transition=hsm_initial("child_init", "grandchild"),
          ),
          hsm_state("sibling_child", label="Sibling Child"),
        ],
        initial_transition=hsm_initial("parent_init", "child"),
      ),
      hsm_state("sibling", label="Sibling"),
    ],
  )


def _compound_local_initial_to_compound_payload() -> dict[str, object]:
  return hsm_document(
    "compound_local_init_machine",
    initial_transition=hsm_initial("machine_init", "parent"),
    states=[
      hsm_state(
        "parent",
        label="Parent",
        states=[
          hsm_state(
            "child_group",
            label="Child Group",
            states=[hsm_state("leaf", label="Leaf")],
            initial_transition=hsm_initial("child_group_init", "leaf"),
          ),
          hsm_state("child_b", label="Child B"),
        ],
        initial_transition=hsm_initial("parent_init", "child_group"),
      )
    ],
  )


def _activity_parity_payload() -> dict[str, object]:
  return hsm_document(
    "activity_parity_machine",
    events=[
      {"id": "open_evt", "parameters": [{"name": "source"}]},
      {"id": "tick_evt"},
      {"id": "close_evt"},
    ],
    initial_transition=hsm_initial("machine_init", "parent"),
    states=[
      hsm_state(
        "parent",
        label="Parent",
        on_initial=[_callable_ref("trace_parent_initial")],
        on_entry=[_callable_ref("enter_parent")],
        on_exit=[_callable_ref("exit_parent")],
        states=[
          hsm_state(
            "child",
            label="Child",
            on_entry=[_callable_ref("trace_child_entry")],
            external_transitions=[
              hsm_external_transition(
                "event_only",
                target_id="sibling",
                event_id="tick_evt",
              )
            ],
          )
        ],
        initial_transition=hsm_initial("parent_init", "child"),
        external_transitions=[
          hsm_external_transition(
            "event_guard_activities",
            event_id="open_evt",
            guard=hsm_guard(
              guard_id="event_guard_activities_node",
              guard=_callable_ref("guard_true"),
              true_branch=hsm_guard_branch(
                "sibling",
                activities=[_callable_ref("trace_transition_activity")],
              ),
              false_branch=hsm_guard_branch("child", activities=[]),
            ),
          )
        ],
        internal_transitions=[
          hsm_internal_transition(
            "parent_internal",
            event_id="tick_evt",
            activities=[_callable_ref("trace_internal_activity")],
          )
        ],
      ),
      hsm_state(
        "sibling",
        label="Sibling",
        on_entry=[_callable_ref("enter_sibling")],
        on_exit=[_callable_ref("inert_exit")],
        external_transitions=[
          hsm_external_transition(
            "event_guard",
            event_id="close_evt",
            guard=hsm_guard(
              guard_id="event_guard_node",
              guard=_callable_ref("guard_true"),
              true_branch=hsm_guard_branch("child"),
              false_branch=hsm_guard_branch("sibling", activities=[]),
            ),
          ),
          hsm_external_transition(
            "event_activities",
            target_id="parent",
            event_id="open_evt",
            activities=[
              _callable_ref("trace_transition_activity"),
              _callable_ref("record_activity"),
            ],
          ),
        ],
        internal_transitions=[
          hsm_internal_transition("sibling_internal", event_id="close_evt")
        ],
      ),
    ],
  )


def _guard_node_render_payload() -> dict[str, object]:
  return hsm_document(
    "guard_render_machine",
    events=[{"id": "advance_evt"}],
    initial_transition=hsm_initial("machine_init", "idle"),
    states=[
      hsm_state(
        "idle",
        on_exit=[_callable_ref("trace_leaf_exit")],
        external_transitions=[
          hsm_external_transition(
            "idle_to_job_check",
            event_id="advance_evt",
            guard=hsm_guard(
              guard_id="job_check",
              guard=_callable_ref("guard_job_available"),
              true_branch=hsm_guard_branch(
                "processing",
                activities=[_callable_ref("trace_guard_true_branch")],
              ),
              false_branch=hsm_guard_branch(
                "blocked",
                activities=[_callable_ref("trace_guard_false_branch")],
              ),
            ),
          )
        ],
      ),
      hsm_state("processing"),
      hsm_state("blocked"),
    ],
  )


def _compound_routing_edge_payload() -> dict[str, object]:
  return hsm_document(
    "compound_routing_machine",
    events=[{"id": "advance_evt"}, {"id": "retry_evt"}],
    initial_transition=hsm_initial("machine_init", "parent"),
    states=[
      hsm_state(
        "parent",
        label="Parent",
        states=[
          hsm_state("child_a", label="Child A"),
          hsm_state("child_b", label="Child B"),
        ],
        initial_transition=hsm_initial("parent_init", "child_a"),
        external_transitions=[
          hsm_external_transition(
            "parent_to_job_check",
            event_id="retry_evt",
            guard=hsm_guard(
              guard_id="job_check",
              guard=_callable_ref("guard_job_available"),
              true_branch=hsm_guard_branch("parent", activities=[]),
              false_branch=hsm_guard_branch("external", activities=[]),
            ),
          )
        ],
      ),
      hsm_state(
        "external",
        label="External",
        external_transitions=[
          hsm_external_transition(
            "external_to_parent",
            target_id="parent",
            event_id="advance_evt",
          )
        ],
      ),
    ],
  )


def _assert_routing_helpers(view, expected_helpers: tuple[tuple[str, ...], ...]) -> None:
  assert tuple(
    (
      helper.id,
      helper.kind,
      helper.parent_id,
      helper.owner_id,
      helper.visibility,
    )
    for helper in view.routing_helpers
  ) == expected_helpers


def test_prepare_hsm_render_view_preserves_depth_first_and_authored_order():
  document = load_hsm_document(_hierarchical_payload())

  view = prepare_hsm_render_view(document)

  assert tuple(state.id for state in view.state_nodes) == (
    "parent",
    "child_a",
    "child_b",
    "sibling",
  )
  assert view.root_state_ids == ("parent", "sibling")
  assert tuple(edge.id for edge in view.initial_edges) == (
    "machine_init",
    "parent_init",
  )
  assert tuple(edge.id for edge in view.transition_edges) == (
    "parent_to_sibling",
    "sibling_to_child_b",
  )


def test_prepare_hsm_render_view_omits_top_summary_blocks_and_preserves_ids():
  document = load_hsm_document(
    hsm_document(
      "door_machine",
      variables=[
        {"id": "count", "default": 0},
        {"id": "mode", "default": "idle"},
      ],
      events=[{"id": "open_evt", "parameters": [{"name": "source"}]}],
      initial_transition=hsm_initial("machine_init", "closed"),
      states=[
        hsm_state(
          "closed",
          label="Closed",
          on_entry=[_callable_ref("count_increment")],
          on_exit=[_callable_ref("mode_idle")],
          external_transitions=[
            hsm_external_transition(
              "closed_to_open",
              target_id="open",
              event_id="open_evt",
            )
          ],
        ),
        hsm_state("open", label="Open"),
      ],
    )
  )

  view = prepare_hsm_render_view(document)

  assert _strip_text_markers(view.transition_edges[0].label or "") == "open_evt(source)"
  assert view.highlightable_ids == (
    "closed",
    "open",
    "machine_init",
    "closed_to_open",
  )
  assert not hasattr(view, "variables_block")
  assert not hasattr(view, "events_block")


def test_prepare_hsm_render_view_exposes_explicit_title_and_body_for_flat_and_compound_states():
  document = load_hsm_document(
    hsm_document(
      "door_machine",
      events=[{"id": "open_evt"}],
      initial_transition=hsm_initial("machine_init", "parent"),
      states=[
        hsm_state(
          "parent",
          label="Parent",
          on_entry=[_callable_ref("enter_parent")],
          on_exit=[_callable_ref("exit_parent")],
          states=[hsm_state("child", label="Child")],
          initial_transition=hsm_initial("parent_init", "child"),
          external_transitions=[
            hsm_external_transition(
              "parent_to_sibling",
              target_id="sibling",
              event_id="open_evt",
            )
          ],
        ),
        hsm_state(
          "sibling",
          label="Sibling",
          on_entry=[_callable_ref("enter_sibling")],
        ),
      ],
    )
  )

  view = prepare_hsm_render_view(document)

  assert tuple(state.id for state in view.state_nodes) == (
    "parent",
    "child",
    "sibling",
  )
  assert view.highlightable_ids == (
    "parent",
    "child",
    "sibling",
    "machine_init",
    "parent_init",
    "parent_to_sibling",
  )
  assert view.state_nodes[0].title_text == "Parent"
  assert tuple(_strip_text_markers(line) for line in view.state_nodes[0].body_lines) == (
    "on_entry:",
    "- enter_parent",
    "on_exit:",
    "- exit_parent",
  )
  assert view.state_nodes[1].title_text == "Child"
  assert view.state_nodes[1].body_lines == ()
  assert view.state_nodes[2].title_text == "Sibling"
  assert tuple(_strip_text_markers(line) for line in view.state_nodes[2].body_lines) == (
    "on_entry:",
    "- enter_sibling",
  )


def test_prepare_hsm_render_view_shapes_ordered_state_body_sections():
  document = load_hsm_document(_activity_parity_payload())

  view = prepare_hsm_render_view(document)
  states_by_id = {state.id: state for state in view.state_nodes}

  assert tuple(
    (
      _strip_text_markers(section.title_text),
      tuple(_strip_text_markers(line) for line in section.lines),
    )
    for section in states_by_id["parent"].body_sections
  ) == (
    ("on_entry:", ("- enter_parent",)),
    ("on_initial:", ("- trace_parent_initial",)),
    ("on_exit:", ("- exit_parent",)),
    ("internal_transitions:", ("- tick_evt/trace_internal_activity",)),
  )
  assert tuple(
    (
      _strip_text_markers(section.title_text),
      tuple(_strip_text_markers(line) for line in section.lines),
    )
    for section in states_by_id["sibling"].body_sections
  ) == (
    ("on_entry:", ("- enter_sibling",)),
    ("on_exit:", ("- inert_exit",)),
    ("internal_transitions:", ("- close_evt",)),
  )
  assert tuple(
    (
      _strip_text_markers(section.title_text),
      tuple(_strip_text_markers(line) for line in section.lines),
    )
    for section in states_by_id["child"].body_sections
  ) == (("on_entry:", ("- trace_child_entry",)),)


def test_prepare_hsm_render_view_formats_transition_labels_without_initial_transition_body_text():
  document = load_hsm_document(_activity_parity_payload())

  view = prepare_hsm_render_view(document)
  transition_labels = {
    edge.id: edge.label for edge in view.transition_edges
  }
  initial_labels = {edge.id: edge.label for edge in view.initial_edges}
  states_by_id = {state.id: state for state in view.state_nodes}

  assert {key: _strip_text_markers(value or "") for key, value in transition_labels.items()} == {
    "event_only": "tick_evt",
    "event_guard": "close_evt",
    "event_activities": (
      "open_evt(source)/trace_transition_activity, record_activity"
    ),
    "event_guard_activities": "open_evt(source)",
    "event_guard_node_true": "true",
    "event_guard_node_false": "false",
    "event_guard_activities_node_true": "true / trace_transition_activity",
    "event_guard_activities_node_false": "false",
  }
  assert initial_labels == {
    "machine_init": None,
    "parent_init": None,
  }
  assert tuple(
    (
      _strip_text_markers(section.title_text),
      tuple(_strip_text_markers(line) for line in section.lines),
    )
    for section in states_by_id["parent"].body_sections
  ) == (
    ("on_entry:", ("- enter_parent",)),
    ("on_initial:", ("- trace_parent_initial",)),
    ("on_exit:", ("- exit_parent",)),
    ("internal_transitions:", ("- tick_evt/trace_internal_activity",)),
  )


def test_prepare_hsm_render_view_emits_private_text_targets_for_lifecycle_transition_and_internal_rows():
  document = load_hsm_document(_activity_parity_payload())

  view = prepare_hsm_render_view(document)
  states_by_id = {state.id: state for state in view.state_nodes}

  assert states_by_id["parent"].body_sections[1].title_line.fragments[0].target_payload == (
    "lifecycle_section|parent|on_initial"
  )
  assert tuple(
    (fragment.text, fragment.target_payload)
    for fragment in states_by_id["parent"].body_sections[1].lines[0].fragments
  ) == (
    ("- ", None),
    (
      "trace_parent_initial",
      "lifecycle_activity|parent|on_initial|trace_parent_initial",
    ),
  )
  assert tuple(
    (fragment.text, fragment.target_payload)
    for fragment in next(
      edge.label_line for edge in view.transition_edges if edge.id == "event_activities"
    ).fragments
  ) == (
    ("open_evt(source)/", "external_transition_label|event_activities"),
    (
      "trace_transition_activity",
      "external_transition_activity|event_activities|trace_transition_activity",
    ),
    (", ", None),
    (
      "record_activity",
      "external_transition_activity|event_activities|record_activity",
    ),
  )
  assert tuple(
    (fragment.text, fragment.target_payload)
    for fragment in states_by_id["parent"].body_sections[3].lines[0].fragments
  ) == (
    ("- ", None),
    ("tick_evt/", "internal_transition_event|parent_internal"),
    (
      "trace_internal_activity",
      "internal_transition_activity|parent_internal|trace_internal_activity",
    ),
  )


def test_render_hsm_dot_omits_initial_transition_text_without_changing_public_id_order():
  document = load_hsm_document(_activity_parity_payload())

  view = prepare_hsm_render_view(document)
  dot_source = render_hsm_dot(view)

  assert tuple(
    _strip_text_markers(line)
    for line in dot_source.splitlines()
    if "id=\"" in line
  )[:10] == (
    '    id="parent";',
    '    "child" [id="child", shape=box, label=<',
    '    "sibling" [id="sibling", shape=box, label=<',
    '    "event_guard_activities_node" [id="event_guard_activities_node", shape=diamond, label="", xlabel="guard_true"];',
    '    "event_guard_node" [id="event_guard_node", shape=diamond, label="", xlabel="guard_true"];',
    '  "__routing_helper_root_initial_source__machine_init" -> '
    '"__routing_helper_compound_anchor__parent" '
    '[id="machine_init", label="", lhead="cluster_parent"];',
    '  "__routing_helper_local_initial_source__parent" -> "child" '
    '[id="parent_init", label=""];',
    '  "child" -> "sibling" [id="event_only", label=<',
    '  "__routing_helper_compound_anchor__parent" -> "event_guard_activities_node" [id="event_guard_activities", label=<',
    '  "event_guard_activities_node" -> "sibling" [id="event_guard_activities_node_true", label=<',
  )
  assert 'TOOLTIP="lifecycle_section|parent|on_initial"' in dot_source
  assert 'TOOLTIP="external_transition_label|event_activities"' in dot_source
  assert 'TOOLTIP="internal_transition_event|parent_internal"' in dot_source
  assert "on_initial:" in dot_source
  assert "initial_transition:" not in dot_source
  assert "trace_child_initial_activity" not in dot_source
  assert 'trace_child_initial_activity' not in dot_source
  assert 'trace_root_initial_activity' not in dot_source
  assert "internal_transitions:" in dot_source
  assert "tick_evt" in dot_source
  assert "trace_internal_activity" in dot_source


def test_render_hsm_dot_transition_metadata_does_not_change_layout_input_text():
  document = load_hsm_document(_activity_parity_payload())

  dot_source = render_hsm_dot(prepare_hsm_render_view(document))

  assert "__MBSE_START__" not in dot_source
  assert "open_evt(source)/trace_transition_activity, record_activity" not in dot_source
  assert 'TOOLTIP="external_transition_label|event_activities"' in dot_source
  assert '>open_evt(source)</TD>' in dot_source


def test_prepare_hsm_render_view_assigns_deterministic_fill_colors_by_depth():
  document = load_hsm_document(_deep_hierarchy_payload())

  view = prepare_hsm_render_view(document)
  states_by_id = {state.id: state for state in view.state_nodes}

  assert states_by_id["parent"].depth == 0
  assert states_by_id["child"].depth == 1
  assert states_by_id["sibling_child"].depth == 1
  assert states_by_id["grandchild"].depth == 2
  assert states_by_id["sibling"].depth == 0
  assert states_by_id["parent"].fill_rgb == "#DCE8F2"
  assert states_by_id["child"].fill_rgb == "#EFE1E3"
  assert states_by_id["sibling_child"].fill_rgb == "#EFE1E3"
  assert states_by_id["grandchild"].fill_rgb == "#E2F0E6"
  assert states_by_id["sibling"].fill_rgb == "#DCE8F2"
  assert states_by_id["child"].fill_rgb != states_by_id["parent"].fill_rgb
  assert states_by_id["grandchild"].fill_rgb != states_by_id["child"].fill_rgb


def test_render_hsm_dot_keeps_empty_body_partition_visible_for_leaf_and_compound():
  document = load_hsm_document(
    hsm_document(
      "empty_partition_machine",
      initial_transition=hsm_initial("machine_init", "parent"),
      states=[
        hsm_state(
          "parent",
          label="Parent",
          states=[hsm_state("child", label="Child")],
        ),
        hsm_state("leaf", label="Leaf"),
      ],
    )
  )

  view = prepare_hsm_render_view(document)
  dot_source = render_hsm_dot(view)
  states_by_id = {state.id: state for state in view.state_nodes}

  assert states_by_id["parent"].has_body_content is False
  assert states_by_id["child"].has_body_content is False
  assert states_by_id["leaf"].has_body_content is False
  assert dot_source.count('<TR><TD ALIGN="LEFT">&#160;</TD></TR>') == 3
  assert 'id="parent";' in dot_source
  assert '"leaf" [id="leaf", shape=box' in dot_source


def test_render_hsm_dot_uses_template_with_exact_authored_ids():
  document = load_hsm_document(_hierarchical_payload())

  dot_source = render_hsm_dot(prepare_hsm_render_view(document))

  assert 'subgraph "cluster_parent" {' in dot_source
  assert 'id="parent";' in dot_source
  assert 'label=<' in dot_source
  assert "<B>Parent</B>" in dot_source
  assert '"parent" [id="parent", shape=box' not in dot_source
  assert (
    '"__routing_helper_root_initial_source__machine_init" '
    '[shape=point, label="", width=0.1, height=0.1, fixedsize=true, '
    'style=filled, fillcolor=black, color=black];'
  ) in dot_source
  assert (
    '"__routing_helper_local_initial_source__parent" '
    '[shape=point, label="", width=0.1, height=0.1, fixedsize=true, '
    'style=filled, fillcolor=black, color=black];'
  ) in dot_source
  assert (
    '"__routing_helper_compound_anchor__parent" '
    '[shape=point, label="", width=0.1, height=0.1, fixedsize=true, '
    'style=invis];'
  ) in dot_source
  assert (
    '"__routing_helper_root_initial_source__machine_init" -> '
    '"__routing_helper_compound_anchor__parent" '
    '[id="machine_init", label="", lhead="cluster_parent"];'
  ) in dot_source
  assert (
    '"__routing_helper_compound_anchor__parent" -> "sibling" '
    '[id="parent_to_sibling", label="", ltail="cluster_parent"];'
  ) in dot_source
  assert 'id="child_a"' in dot_source
  assert '"child_a" [id="child_a", shape=box, label=<' in dot_source
  assert "<B>Child A</B>" in dot_source
  assert 'id="machine_init"' in dot_source
  assert 'id="sibling_to_child_b"' in dot_source
  assert 'TOOLTIP="external_transition_label|sibling_to_child_b"' in dot_source
  assert '>open_evt(source)</TD>' in dot_source
  assert "Variables:" not in dot_source
  assert "Events:" not in dot_source


def test_prepare_hsm_render_view_keeps_public_ids_and_routes_compound_edges_to_anchor():
  document = load_hsm_document(_hierarchical_payload())

  view = prepare_hsm_render_view(document)

  _assert_routing_helpers(view, (
    (
      "__routing_helper_root_initial_source__machine_init",
      "root_initial_source",
      None,
      "machine_init",
      "visible_source",
    ),
    (
      "__routing_helper_compound_anchor__parent",
      "compound_anchor",
      "parent",
      "parent",
      "private_anchor",
    ),
    (
      "__routing_helper_local_initial_source__parent",
      "local_initial_source",
      "parent",
      "parent_init",
      "visible_source",
    ),
  ))
  assert view.highlightable_ids == (
    "parent",
    "child_a",
    "child_b",
    "sibling",
    "machine_init",
    "parent_init",
    "parent_to_sibling",
    "sibling_to_child_b",
  )
  assert tuple(edge.source_id for edge in view.initial_edges) == (
    "__routing_helper_root_initial_source__machine_init",
    "__routing_helper_local_initial_source__parent",
  )
  assert tuple(edge.target_id for edge in view.initial_edges) == (
    "__routing_helper_compound_anchor__parent",
    "child_a",
  )
  assert tuple(edge.source_id for edge in view.transition_edges) == (
    "__routing_helper_compound_anchor__parent",
    "sibling",
  )
  assert tuple(edge.target_id for edge in view.transition_edges) == (
    "sibling",
    "child_b",
  )
  assert tuple(edge.source_cluster_id for edge in view.transition_edges) == (
    "parent",
    None,
  )
  assert tuple(edge.target_cluster_id for edge in view.transition_edges) == (
    None,
    None,
  )


def test_prepare_hsm_render_view_routes_local_initial_targets_to_compound_anchors():
  document = load_hsm_document(_compound_local_initial_to_compound_payload())

  view = prepare_hsm_render_view(document)

  _assert_routing_helpers(view, (
    (
      "__routing_helper_root_initial_source__machine_init",
      "root_initial_source",
      None,
      "machine_init",
      "visible_source",
    ),
    (
      "__routing_helper_compound_anchor__parent",
      "compound_anchor",
      "parent",
      "parent",
      "private_anchor",
    ),
    (
      "__routing_helper_local_initial_source__parent",
      "local_initial_source",
      "parent",
      "parent_init",
      "visible_source",
    ),
    (
      "__routing_helper_compound_anchor__child_group",
      "compound_anchor",
      "child_group",
      "child_group",
      "private_anchor",
    ),
    (
      "__routing_helper_local_initial_source__child_group",
      "local_initial_source",
      "child_group",
      "child_group_init",
      "visible_source",
    ),
  ))
  assert view.highlightable_ids == (
    "parent",
    "child_group",
    "leaf",
    "child_b",
    "machine_init",
    "parent_init",
    "child_group_init",
  )
  assert tuple(edge.source_id for edge in view.initial_edges) == (
    "__routing_helper_root_initial_source__machine_init",
    "__routing_helper_local_initial_source__parent",
    "__routing_helper_local_initial_source__child_group",
  )
  assert tuple(edge.target_id for edge in view.initial_edges) == (
    "__routing_helper_compound_anchor__parent",
    "__routing_helper_compound_anchor__child_group",
    "leaf",
  )
  assert tuple(edge.target_cluster_id for edge in view.initial_edges) == (
    "parent",
    "child_group",
    None,
  )

  dot_source = render_hsm_dot(view)

  assert (
    '"__routing_helper_local_initial_source__parent" -> '
    '"__routing_helper_compound_anchor__child_group" '
    '[id="parent_init", label="", lhead="cluster_child_group"];'
  ) in dot_source
  assert 'style=invis' in dot_source


def test_prepare_hsm_render_view_exposes_guard_nodes_and_branch_edges():
  document = load_hsm_document(_guard_node_render_payload())

  view = prepare_hsm_render_view(document)

  assert tuple(guard.id for guard in view.guard_nodes) == ("job_check",)
  assert view.guard_nodes[0].title_text == "guard_job_available"
  assert view.highlightable_ids == (
    "idle",
    "processing",
    "blocked",
    "job_check",
    "machine_init",
    "idle_to_job_check",
    "job_check_true",
    "job_check_false",
  )
  assert tuple(edge.id for edge in view.transition_edges) == (
    "idle_to_job_check",
    "job_check_true",
    "job_check_false",
  )
  assert tuple(edge.source_id for edge in view.transition_edges) == (
    "idle",
    "job_check",
    "job_check",
  )
  assert tuple(edge.target_id for edge in view.transition_edges) == (
    "job_check",
    "processing",
    "blocked",
  )
  assert {
    edge.id: _strip_text_markers(edge.label or "") for edge in view.transition_edges
  } == {
    "idle_to_job_check": "advance_evt",
    "job_check_true": "true / trace_guard_true_branch",
    "job_check_false": "false / trace_guard_false_branch",
  }
  assert {
    edge.id: _strip_text_markers(edge.xlabel or "") for edge in view.transition_edges
  } == {
    "idle_to_job_check": "",
    "job_check_true": "",
    "job_check_false": "",
  }
  assert tuple(
    (fragment.text, fragment.target_payload)
    for fragment in next(
      edge.label_line for edge in view.transition_edges if edge.id == "job_check_true"
    ).fragments
  ) == (
    ("true", "external_transition_label|job_check_true"),
    (
      " / trace_guard_true_branch",
      "external_transition_activity|job_check_true|trace_guard_true_branch",
    ),
  )
  assert next(
    edge.xlabel_line for edge in view.transition_edges if edge.id == "job_check_true"
  ) is None

def test_render_hsm_dot_renders_guard_nodes_as_diamonds_and_branch_edges():
  document = load_hsm_document(_guard_node_render_payload())

  dot_source = render_hsm_dot(prepare_hsm_render_view(document))

  assert 'graph [nodesep=0.45, ranksep=0.65];' in dot_source
  assert (
    '"job_check" [id="job_check", shape=diamond, '
    'label="", xlabel="guard_job_available"];'
  ) in dot_source
  assert '"idle" -> "job_check" [id="idle_to_job_check", label=<' in dot_source
  assert '"job_check" -> "processing" [id="job_check_true", label=<' in dot_source
  assert '"job_check" -> "blocked" [id="job_check_false", label=<' in dot_source
  assert 'TOOLTIP="external_transition_label|job_check_true"' in dot_source
  assert (
    'TOOLTIP="external_transition_activity|job_check_true|trace_guard_true_branch"'
    in dot_source
  )


def test_prepare_hsm_render_view_routes_compound_edges_across_all_relevant_edge_types():
  document = load_hsm_document(_compound_routing_edge_payload())

  view = prepare_hsm_render_view(document)

  assert tuple(
    (edge.id, edge.source_id, edge.target_id, edge.source_cluster_id, edge.target_cluster_id)
    for edge in view.initial_edges
  ) == (
    (
      "machine_init",
      "__routing_helper_root_initial_source__machine_init",
      "__routing_helper_compound_anchor__parent",
      None,
      "parent",
    ),
    (
      "parent_init",
      "__routing_helper_local_initial_source__parent",
      "child_a",
      None,
      None,
    ),
  )
  assert tuple(
    (edge.id, edge.source_id, edge.target_id, edge.source_cluster_id, edge.target_cluster_id)
    for edge in view.transition_edges
  ) == (
    ("parent_to_job_check", "__routing_helper_compound_anchor__parent", "job_check", "parent", None),
    ("job_check_true", "job_check", "__routing_helper_compound_anchor__parent", None, "parent"),
    ("job_check_false", "job_check", "external", None, None),
    ("external_to_parent", "external", "__routing_helper_compound_anchor__parent", None, "parent"),
  )


def test_render_hsm_dot_routes_all_compound_touching_edges_through_cluster_boundaries():
  document = load_hsm_document(_compound_routing_edge_payload())

  dot_source = render_hsm_dot(prepare_hsm_render_view(document))

  assert (
    '"__routing_helper_root_initial_source__machine_init" -> '
    '"__routing_helper_compound_anchor__parent" '
    '[id="machine_init", label="", lhead="cluster_parent"];'
  ) in dot_source
  assert (
    '"external" -> "__routing_helper_compound_anchor__parent" '
    '[id="external_to_parent", label=<'
  ) in dot_source
  assert (
    '"__routing_helper_compound_anchor__parent" -> "job_check" '
    '[id="parent_to_job_check", label=<'
  ) in dot_source
  assert (
    '"job_check" -> "__routing_helper_compound_anchor__parent" '
    '[id="job_check_true", label=<'
  ) in dot_source
  assert 'id="external_to_parent"' in dot_source
  assert 'id="parent_to_job_check"' in dot_source
  assert 'id="job_check_true"' in dot_source
  assert dot_source.count('lhead="cluster_parent"') >= 2
  assert 'ltail="cluster_parent"' in dot_source
