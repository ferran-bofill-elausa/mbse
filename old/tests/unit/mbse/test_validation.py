from __future__ import annotations

from pathlib import Path
import re

import pytest
from jsonschema import Draft202012Validator

from mbse.model.hsm import load_hsm_document
from mbse.model.hsm import load_hsm_schema
from mbse.model.hsm.validation.exceptions import HsmValidationError
from mbse_web_viewer.svg_render.graphviz.exceptions import (
  GraphvizValidationError,
)
from mbse_web_viewer.svg_render.graphviz.prepared_document import (
  PreparedGraphvizDocument,
)
from mbse_web_viewer.svg_render.graphviz.prepared_document import (
  load_prepared_document,
)
from mbse_web_viewer.svg_render.graphviz.prepared_document import (
  validate_prepared_document,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
FORBIDDEN_IMPORT_PATTERN = re.compile(r"(^|\n)\s*(from|import)\s+src\.mbse(\.|\s|$)")


@pytest.mark.parametrize(
  ("payload", "missing_field"),
  [
    ({"dot_source": "digraph G {}", "highlightable_ids": ["state_idle"]}, "document_id"),
    ({"document_id": "demo", "highlightable_ids": ["state_idle"]}, "dot_source"),
    ({"document_id": "demo", "dot_source": "digraph G {}"}, "highlightable_ids"),
  ],
)
def test_load_prepared_document_requires_all_fields(payload, missing_field):
  with pytest.raises(GraphvizValidationError) as excinfo:
    load_prepared_document(payload)

  assert excinfo.value.code == "prepared_document.missing_field"
  assert missing_field in excinfo.value.message


def test_validate_prepared_document_rejects_duplicate_highlightable_ids():
  document = PreparedGraphvizDocument(
    document_id="demo",
    dot_source='digraph G { idle [id="state_idle"]; }',
    highlightable_ids=("state_idle", "state_idle"),
  )

  with pytest.raises(GraphvizValidationError) as excinfo:
    validate_prepared_document(document)

  assert excinfo.value.code == "prepared_document.duplicate_highlightable_id"
  assert excinfo.value.message == "Duplicate highlightable_id 'state_idle'."


def test_validate_prepared_document_rejects_ids_not_authored_in_dot_source():
  document = PreparedGraphvizDocument(
    document_id="demo",
    dot_source='digraph G { idle [id="state_idle"]; }',
    highlightable_ids=("state_missing",),
  )

  with pytest.raises(GraphvizValidationError) as excinfo:
    validate_prepared_document(document)

  assert excinfo.value.code == "prepared_document.id_not_authored"
  assert excinfo.value.message == (
    "Highlightable ID 'state_missing' is not authored in dot_source."
  )


def test_load_prepared_document_accepts_exact_authored_ids():
  document = load_prepared_document(
    {
      "document_id": "demo",
      "dot_source": (
        'digraph G { idle [id="state_idle"]; idle -> ready '
        '[id="edge_start"]; }'
      ),
      "highlightable_ids": ["state_idle", "edge_start"],
    }
  )

  assert document == PreparedGraphvizDocument(
    document_id="demo",
    dot_source=(
      'digraph G { idle [id="state_idle"]; idle -> ready '
      '[id="edge_start"]; }'
    ),
    highlightable_ids=("state_idle", "edge_start"),
  )


def test_hsm_schema_accepts_callable_refs_in_lifecycle_internal_and_transition_slots():
  validator = Draft202012Validator(load_hsm_schema())

  errors = sorted(
    validator.iter_errors(
      {
        "schema_version": "hsm-v1",
        "document_id": "door_machine",
        "variables": [],
        "events": [{"id": "open_evt"}],
        "states": [
          {
            "id": "closed",
            "states": [],
            "hooks": {
              "on_initial": [
                {
                  "module": "tests.support.hsm_callable_fixtures",
                  "name": "record_activity",
                }
              ],
              "on_entry": [
                {
                  "module": "tests.support.hsm_callable_fixtures",
                  "name": "record_activity",
                }
              ],
              "on_exit": [
                {
                  "module": "tests.support.hsm_callable_fixtures",
                  "name": "record_activity",
                }
              ],
            },
            "initial_transition": {
              "id": "closed_init",
              "target_id": "closed",
            },
            "external_transitions": [
              {
                "id": "closed_to_closed",
                "event_id": "open_evt",
                "guard": {
                  "guard": {
                    "module": "tests.support.hsm_callable_fixtures",
                    "name": "allow_guard",
                  },
                  "true_branch": {
                    "target_id": "closed",
                    "activities": [
                      {
                        "module": "tests.support.hsm_callable_fixtures",
                        "name": "record_activity",
                      }
                    ],
                  },
                  "false_branch": {
                    "target_id": "closed",
                    "activities": [
                      {
                        "module": "tests.support.hsm_callable_fixtures",
                        "name": "record_activity",
                      }
                    ],
                  },
                },
              }
            ],
            "internal_transitions": [
              {
                "id": "closed_ping",
                "event_id": "open_evt",
                "activities": [
                  {
                    "module": "tests.support.hsm_callable_fixtures",
                    "name": "record_activity",
                  }
                ],
              }
            ],
          }
        ],
        "initial_transition": {
          "id": "machine_init",
          "target_id": "closed",
        },
      }
    ),
    key=str,
  )

  assert errors == []


def test_hsm_schema_requires_default_for_declared_variables():
  validator = Draft202012Validator(load_hsm_schema())

  errors = sorted(
    validator.iter_errors(
      {
        "schema_version": "hsm-v1",
        "document_id": "door_machine",
        "variables": [{"id": "count"}],
        "events": [],
        "initial_transition": {"id": "machine_init", "target_id": "closed"},
        "states": [
          {
            "id": "closed",
            "states": [],
            "hooks": {"on_initial": [], "on_entry": [], "on_exit": []},
            "external_transitions": [],
            "internal_transitions": [],
          }
        ],
      }
    ),
    key=str,
  )

  assert len(errors) == 1
  assert errors[0].validator == "required"
  assert list(errors[0].path) == ["variables", 0]


def test_hsm_schema_accepts_embedded_guards_with_branch_activities():
  validator = Draft202012Validator(load_hsm_schema())

  errors = sorted(
    validator.iter_errors(
      {
        "schema_version": "hsm-v1",
        "document_id": "guard_node_machine",
        "variables": [{"id": "job_queue", "default": 0}],
        "events": [{"id": "advance_evt"}],
        "initial_transition": {"id": "machine_init", "target_id": "idle"},
        "states": [
          {
            "id": "idle",
            "states": [],
            "hooks": {"on_initial": [], "on_entry": [], "on_exit": []},
            "external_transitions": [
              {
                "id": "idle_to_job_check",
                "event_id": "advance_evt",
                "guard": {
                  "guard": {
                    "module": "tests.support.hsm_callable_fixtures",
                    "name": "guard_job_available",
                  },
                  "true_branch": {
                    "target_id": "processing",
                    "activities": [
                      {
                        "module": "tests.support.hsm_callable_fixtures",
                        "name": "trace_guard_true_branch",
                      }
                    ],
                  },
                  "false_branch": {
                    "target_id": "blocked",
                    "activities": [
                      {
                        "module": "tests.support.hsm_callable_fixtures",
                        "name": "trace_guard_false_branch",
                      }
                    ],
                  },
                },
              }
            ],
            "internal_transitions": [],
          },
          {
            "id": "processing",
            "states": [],
            "hooks": {"on_initial": [], "on_entry": [], "on_exit": []},
            "external_transitions": [],
            "internal_transitions": [],
          },
          {
            "id": "blocked",
            "states": [],
            "hooks": {"on_initial": [], "on_entry": [], "on_exit": []},
            "external_transitions": [],
            "internal_transitions": [],
          },
        ],
      }
    ),
    key=str,
  )

  assert errors == []


def test_hsm_schema_rejects_embedded_guard_without_false_branch():
  validator = Draft202012Validator(load_hsm_schema())

  errors = sorted(
    validator.iter_errors(
      {
        "schema_version": "hsm-v1",
        "document_id": "guard_node_machine",
        "variables": [],
        "events": [{"id": "advance_evt"}],
        "initial_transition": {"id": "machine_init", "target_id": "idle"},
        "states": [
          {
            "id": "idle",
            "states": [],
            "hooks": {"on_initial": [], "on_entry": [], "on_exit": []},
            "external_transitions": [
              {
                "id": "idle_to_job_check",
                "event_id": "advance_evt",
                "guard": {
                  "guard": {
                    "module": "tests.support.hsm_callable_fixtures",
                    "name": "guard_job_available",
                  },
                  "true_branch": {
                    "target_id": "processing",
                  },
                },
              }
            ],
            "internal_transitions": [],
          },
          {
            "id": "processing",
            "states": [],
            "hooks": {"on_initial": [], "on_entry": [], "on_exit": []},
            "external_transitions": [],
            "internal_transitions": [],
          },
        ],
      }
    ),
    key=str,
  )

  assert len(errors) == 1
  assert errors[0].validator == "required"
  assert list(errors[0].path) == ["states", 0, "external_transitions", 0, "guard"]


def test_hsm_schema_rejects_external_transition_with_target_and_guard():
  validator = Draft202012Validator(load_hsm_schema())

  errors = sorted(
    validator.iter_errors(
      {
        "schema_version": "hsm-v1",
        "document_id": "guard_node_machine",
        "variables": [],
        "events": [{"id": "advance_evt"}],
        "initial_transition": {"id": "machine_init", "target_id": "idle"},
        "states": [
          {
            "id": "idle",
            "states": [],
            "hooks": {"on_initial": [], "on_entry": [], "on_exit": []},
            "external_transitions": [
              {
                "id": "idle_to_job_check",
                "target_id": "processing",
                "event_id": "advance_evt",
                "guard": {
                  "guard": {
                    "module": "tests.support.hsm_callable_fixtures",
                    "name": "guard_job_available",
                  },
                  "true_branch": {"target_id": "processing"},
                  "false_branch": {"target_id": "idle"},
                },
              }
            ],
            "internal_transitions": [],
          },
          {
            "id": "processing",
            "states": [],
            "hooks": {"on_initial": [], "on_entry": [], "on_exit": []},
            "external_transitions": [],
            "internal_transitions": [],
          },
        ],
      }
    ),
    key=str,
  )

  assert len(errors) == 1
  assert errors[0].validator == "oneOf"


def test_hsm_schema_requires_root_initial_transition():
  validator = Draft202012Validator(load_hsm_schema())

  errors = sorted(
    validator.iter_errors(
      {
        "schema_version": "hsm-v1",
        "document_id": "door_machine",
        "variables": [],
        "events": [],
        "states": [
          {
            "id": "closed",
            "states": [],
            "hooks": {"on_initial": [], "on_entry": [], "on_exit": []},
            "external_transitions": [],
            "internal_transitions": [],
          }
        ],
      }
    ),
    key=str,
  )

  assert len(errors) == 1
  assert errors[0].validator == "required"
  assert list(errors[0].path) == []


def test_hsm_schema_rejects_guard_on_internal_transition():
  validator = Draft202012Validator(load_hsm_schema())

  errors = sorted(
    validator.iter_errors(
      {
        "schema_version": "hsm-v1",
        "document_id": "door_machine",
        "variables": [],
        "events": [{"id": "open_evt"}],
        "initial_transition": {"id": "machine_init", "target_id": "closed"},
        "states": [
          {
            "id": "closed",
            "states": [],
            "hooks": {"on_initial": [], "on_entry": [], "on_exit": []},
            "external_transitions": [],
            "internal_transitions": [
              {
                "id": "closed_to_closed",
                "event_id": "open_evt",
                "guard": {
                  "guard": {
                    "module": "tests.support.hsm_callable_fixtures",
                    "name": "allow_guard",
                  },
                  "true_branch": {"target_id": "closed"},
                  "false_branch": {"target_id": "closed"},
                },
              }
            ],
          }
        ],
      }
    ),
    key=str,
  )

  assert len(errors) == 1
  assert errors[0].validator == "additionalProperties"
  assert list(errors[0].path) == ["states", 0, "internal_transitions", 0]


def test_load_hsm_document_rejects_inline_strings_in_callable_slots():
  with pytest.raises(HsmValidationError) as excinfo:
    load_hsm_document(
      {
        "schema_version": "hsm-v1",
        "document_id": "door_machine",
        "variables": [],
        "events": [{"id": "open_evt"}],
        "states": [
          {
            "id": "closed",
            "states": [],
            "hooks": {
              "on_initial": [],
              "on_entry": ["count = count + 1"],
              "on_exit": [],
            },
            "external_transitions": [],
            "internal_transitions": [],
          }
        ],
        "initial_transition": {"id": "machine_init", "target_id": "closed"},
      }
    )

  assert excinfo.value.code == "hsm_document.inline_string_not_allowed"
  assert excinfo.value.message == (
    "Inline executable strings are not allowed at 'states[0].hooks.on_entry[0]'; "
    "use a callable ref object with 'module' and 'name'."
  )


def test_hsm_schema_requires_event_id_for_internal_transitions():
  validator = Draft202012Validator(load_hsm_schema())

  errors = sorted(
    validator.iter_errors(
      {
        "schema_version": "hsm-v1",
        "document_id": "door_machine",
        "variables": [],
        "events": [{"id": "open_evt"}],
        "initial_transition": {"id": "machine_init", "target_id": "closed"},
        "states": [
          {
            "id": "closed",
            "states": [],
            "hooks": {"on_initial": [], "on_entry": [], "on_exit": []},
            "external_transitions": [],
            "internal_transitions": [
              {
                "id": "closed_ping",
                "activities": [
                  {
                    "module": "tests.support.hsm_callable_fixtures",
                    "name": "record_activity",
                  }
                ],
              }
            ],
          }
        ],
      }
    ),
    key=str,
  )

  assert len(errors) == 1
  assert errors[0].validator == "required"
  assert list(errors[0].path) == ["states", 0, "internal_transitions", 0]


def test_mbse_package_tree_does_not_import_src_prefixed_package_paths():
  package_root = REPO_ROOT / "src" / "mbse"
  forbidden = []

  for path in sorted(package_root.rglob("*.py")):
    source = path.read_text(encoding="utf-8")
    if FORBIDDEN_IMPORT_PATTERN.search(source):
      forbidden.append(path.relative_to(REPO_ROOT).as_posix())

  assert forbidden == []
