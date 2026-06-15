from __future__ import annotations

import pytest
from jsonschema import Draft202012Validator

from mbse.model.hsm import HsmCallableRef
from mbse.model.hsm import HsmDocument
from mbse.model.hsm import HsmEvent
from mbse.model.hsm import HsmEventParameter
from mbse.model.hsm import HsmGuardBranch
from mbse.model.hsm import HsmGuardNode
from mbse.model.hsm import HsmInitialTransition
from mbse.model.hsm import HsmInternalTransition
from mbse.model.hsm import HsmState
from mbse.model.hsm import HsmExternalTransition
from mbse.model.hsm import HsmVariable
from mbse.model.hsm import load_hsm_document
from mbse.model.hsm import load_hsm_schema
from mbse.model.hsm import validate_hsm_document
from mbse.model.hsm.validation.exceptions import HsmValidationError


def _minimal_hsm_payload() -> dict[str, object]:
  return {
    "schema_version": "hsm-v1",
    "document_id": "door_machine",
    "variables": [],
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


def _callable_ref(name: str) -> dict[str, str]:
  return {
    "module": "tests.support.hsm_callable_fixtures",
    "name": name,
  }


def test_load_hsm_document_accepts_minimal_fsm_document():
  document = load_hsm_document(_minimal_hsm_payload())

  assert document == HsmDocument(
    schema_version="hsm-v1",
    document_id="door_machine",
    variables=(),
    events=(),
    states=(HsmState(id="closed"),),
    initial=HsmInitialTransition(id="machine_init", target_id="closed"),
    external_transitions=(),
  )


def test_validate_hsm_document_accepts_behavioral_metadata_without_runtime():
  document = load_hsm_document(
    {
      "schema_version": "hsm-v1",
      "document_id": "door_machine",
      "variables": [{"id": "count", "default": 0}],
      "events": [
        {
          "id": "open_evt",
          "parameters": [{"name": "source"}, {"name": "actor"}],
        }
      ],
      "initial_transition": {
        "id": "machine_init",
        "target_id": "closed",
      },
      "states": [
        {
          "id": "closed",
          "states": [],
          "hooks": {
            "on_initial": [_callable_ref("record_activity")],
            "on_entry": [_callable_ref("record_activity")],
            "on_exit": [_callable_ref("record_activity")],
          },
          "external_transitions": [
            {
              "id": "closed_to_closed",
              "event_id": "open_evt",
              "guard": {
                "guard": _callable_ref("allow_guard"),
                "true_branch": {
                  "target_id": "closed",
                  "activities": [_callable_ref("record_activity")],
                },
                "false_branch": {
                  "target_id": "closed",
                  "activities": [_callable_ref("record_activity")],
                },
              },
            }
          ],
          "internal_transitions": [
            {
              "id": "closed_ping",
              "event_id": "open_evt",
              "activities": [_callable_ref("record_activity")],
            }
          ],
        }
      ],
    }
  )

  assert document == HsmDocument(
    schema_version="hsm-v1",
    document_id="door_machine",
    variables=(HsmVariable(id="count", default=0),),
    events=(
      HsmEvent(
        id="open_evt",
        parameters=(
          HsmEventParameter(name="source"),
          HsmEventParameter(name="actor"),
        ),
      ),
    ),
    states=(
      HsmState(
        id="closed",
        on_initial=(
          HsmCallableRef(
            module="tests.support.hsm_callable_fixtures",
            name="record_activity",
          ),
        ),
        on_entry=(
          HsmCallableRef(
            module="tests.support.hsm_callable_fixtures",
            name="record_activity",
          ),
        ),
        on_exit=(
          HsmCallableRef(
            module="tests.support.hsm_callable_fixtures",
            name="record_activity",
          ),
        ),
      ),
    ),
    initial=HsmInitialTransition(
      id="machine_init",
      target_id="closed",
    ),
    external_transitions=(
      HsmExternalTransition(
        id="closed_to_closed",
        source_id="closed",
        target_id="closed_to_closed_guard",
        event_id="open_evt",
      ),
    ),
    guard_nodes=(
      HsmGuardNode(
        id="closed_to_closed_guard",
        guard=HsmCallableRef(
          module="tests.support.hsm_callable_fixtures",
          name="allow_guard",
        ),
        true_branch=HsmGuardBranch(
          target_id="closed",
          activities=(
            HsmCallableRef(
              module="tests.support.hsm_callable_fixtures",
              name="record_activity",
            ),
          ),
        ),
        false_branch=HsmGuardBranch(
          target_id="closed",
          activities=(
            HsmCallableRef(
              module="tests.support.hsm_callable_fixtures",
              name="record_activity",
            ),
          ),
        ),
      ),
    ),
    internal_transitions=(
      HsmInternalTransition(
        id="closed_ping",
        source_id="closed",
        event_id="open_evt",
        activities=(
          HsmCallableRef(
            module="tests.support.hsm_callable_fixtures",
            name="record_activity",
          ),
        ),
      ),
    ),
  )

  validate_hsm_document(document)


def test_load_hsm_document_does_not_attach_runtime_handler_order_metadata():
  document = load_hsm_document(
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
          "external_transitions": [
            {
              "id": "closed_to_open",
              "target_id": "open",
              "event_id": "open_evt",
            }
          ],
          "internal_transitions": [
            {
              "id": "closed_ping",
              "event_id": "open_evt",
            }
          ],
        },
        {
          "id": "open",
          "states": [],
          "hooks": {"on_initial": [], "on_entry": [], "on_exit": []},
          "external_transitions": [],
          "internal_transitions": [],
        },
      ],
    }
  )

  assert not hasattr(document, "event_handler_collections")


def test_load_hsm_document_rejects_executable_initial_activities():
  payload = _minimal_hsm_payload()
  payload["initial_transition"] = {
    "id": "machine_init",
    "target_id": "closed",
    "activities": [_callable_ref("record_activity")],
  }

  with pytest.raises(HsmValidationError) as excinfo:
    load_hsm_document(payload)

  assert excinfo.value.code == "hsm_document.additional_property"
  assert excinfo.value.message == (
    "Unsupported property 'activities' at 'initial_transition'."
  )


def test_load_hsm_document_accepts_embedded_guards_with_true_false_branches():
  document = load_hsm_document(
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
                "guard": _callable_ref("guard_job_available"),
                "true_branch": {
                  "target_id": "processing",
                  "activities": [_callable_ref("trace_guard_true_branch")],
                },
                "false_branch": {
                  "target_id": "blocked",
                  "activities": [_callable_ref("trace_guard_false_branch")],
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
  )

  assert document.guard_nodes == (
    HsmGuardNode(
      id="idle_to_job_check_guard",
      guard=HsmCallableRef(
        module="tests.support.hsm_callable_fixtures",
        name="guard_job_available",
      ),
      true_branch=HsmGuardBranch(
        target_id="processing",
        activities=(
          HsmCallableRef(
            module="tests.support.hsm_callable_fixtures",
            name="trace_guard_true_branch",
          ),
        ),
      ),
      false_branch=HsmGuardBranch(
        target_id="blocked",
        activities=(
          HsmCallableRef(
            module="tests.support.hsm_callable_fixtures",
            name="trace_guard_false_branch",
          ),
        ),
      ),
    ),
  )


def test_load_hsm_document_rejects_guarded_external_transition_with_direct_target():
  payload = {
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
              "guard": _callable_ref("guard_job_available"),
              "true_branch": {"target_id": "processing"},
              "false_branch": {"target_id": "idle"},
            },
          },
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

  with pytest.raises(HsmValidationError) as excinfo:
    load_hsm_document(payload)

  assert excinfo.value.code == "hsm_document.schema_validation_error"
  assert "is not valid under any of the given schemas" in excinfo.value.message


def test_load_hsm_document_rejects_rootless_documents_semantically():
  payload = {
    **_minimal_hsm_payload(),
    "initial_transition": None,
  }

  with pytest.raises(HsmValidationError) as excinfo:
    load_hsm_document(payload)

  assert excinfo.value.code == "hsm_document.invalid_type"
  assert excinfo.value.message == "Expected object at 'initial_transition'."


def test_validate_hsm_document_allows_local_initial_to_target_descendant_state():
  document = load_hsm_document(
    {
      "schema_version": "hsm-v1",
      "document_id": "desc_target_machine",
      "variables": [],
      "events": [],
      "initial_transition": {"id": "machine_init", "target_id": "parent"},
      "states": [
        {
          "id": "parent",
          "states": [
            {
              "id": "child",
              "states": [
                {
                  "id": "leaf",
                  "states": [],
                  "hooks": {"on_initial": [], "on_entry": [], "on_exit": []},
                  "external_transitions": [],
                  "internal_transitions": [],
                }
              ],
              "hooks": {"on_initial": [], "on_entry": [], "on_exit": []},
              "external_transitions": [],
              "internal_transitions": [],
            }
          ],
          "hooks": {"on_initial": [], "on_entry": [], "on_exit": []},
          "initial_transition": {"id": "parent_init", "target_id": "leaf"},
          "external_transitions": [],
          "internal_transitions": [],
        },
      ],
    }
  )

  assert document.initial is not None
  assert document.states[0].initial is not None
  assert document.states[0].initial.target_id == "leaf"


def test_load_hsm_document_rejects_guard_on_initial_transition():
  payload = _minimal_hsm_payload()
  payload["states"] = [
    {
      "id": "closed",
      "states": [],
      "hooks": {"on_initial": [], "on_entry": [], "on_exit": []},
      "initial_transition": {
        "id": "closed_init",
        "target_id": "closed",
        "guard": {
          "guard": _callable_ref("allow_guard"),
          "true_branch": {"target_id": "closed"},
          "false_branch": {"target_id": "closed"},
        },
      },
      "external_transitions": [],
      "internal_transitions": [],
    }
  ]

  with pytest.raises(HsmValidationError) as excinfo:
    load_hsm_document(payload)

  assert excinfo.value.code == "hsm_document.additional_property"
  assert excinfo.value.message == (
    "Unsupported property 'guard' at 'states[0].initial_transition'."
  )


def test_load_hsm_document_rejects_guard_with_transition_activities():
  payload = {
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
            "activities": [_callable_ref("record_activity")],
            "guard": {
              "guard": _callable_ref("guard_job_available"),
              "true_branch": {"target_id": "processing"},
              "false_branch": {"target_id": "idle"},
            },
          }
        ],
        "internal_transitions": [],
      }
      ,{
        "id": "processing",
        "states": [],
        "hooks": {"on_initial": [], "on_entry": [], "on_exit": []},
        "external_transitions": [],
        "internal_transitions": [],
      }
    ],
  }

  with pytest.raises(HsmValidationError) as excinfo:
    load_hsm_document(payload)

  assert excinfo.value.code == "hsm_document.guard_transition_activity_conflict"
  assert excinfo.value.message == (
    "External transition 'idle_to_job_check' cannot declare activities when using "
    "guard branches; move them to true_branch/false_branch."
  )


def test_load_hsm_schema_accepts_minimal_hsm_v1_document():
  schema = load_hsm_schema()
  validator = Draft202012Validator(schema)

  errors = sorted(validator.iter_errors(_minimal_hsm_payload()), key=str)

  assert errors == []


def test_load_hsm_document_requires_variable_default() -> None:
  with pytest.raises(HsmValidationError) as excinfo:
    load_hsm_document(
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
    )

  assert excinfo.value.code == "hsm_document.missing_field"
  assert excinfo.value.message == "HSM document missing required field 'default'."


def test_load_hsm_document_rejects_duplicate_global_ids():
  with pytest.raises(HsmValidationError) as excinfo:
    load_hsm_document(
      {
        "schema_version": "hsm-v1",
        "document_id": "door_machine",
        "variables": [],
        "events": [{"id": "open_evt"}],
        "initial_transition": {"id": "machine_init", "target_id": "open_evt"},
        "states": [
          {
            "id": "open_evt",
            "states": [],
            "hooks": {"on_initial": [], "on_entry": [], "on_exit": []},
            "external_transitions": [],
            "internal_transitions": [],
          }
        ],
      }
    )

  assert excinfo.value.code == "hsm_document.duplicate_id"
  assert excinfo.value.message == "Duplicate HSM id 'open_evt'."


def test_load_hsm_document_rejects_unknown_state_or_event_references():
  with pytest.raises(HsmValidationError) as excinfo:
    load_hsm_document(
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
            "external_transitions": [
              {
                "id": "closed_to_open",
                "target_id": "open",
                "event_id": "missing_evt",
              }
            ],
            "internal_transitions": [],
          }
        ],
      }
    )

  assert excinfo.value.code == "hsm_document.unknown_state_reference"
  assert excinfo.value.message == (
    "External transition 'closed_to_open' references unknown target state 'open'."
  )


def test_load_hsm_document_rejects_missing_local_initial_target_reference():
  with pytest.raises(HsmValidationError) as excinfo:
    load_hsm_document(
      {
        "schema_version": "hsm-v1",
        "document_id": "door_machine",
        "variables": [],
        "events": [],
        "initial_transition": {"id": "machine_init", "target_id": "parent"},
        "states": [
          {
            "id": "parent",
            "states": [
              {
                "id": "child",
                "states": [],
                "hooks": {"on_initial": [], "on_entry": [], "on_exit": []},
                "external_transitions": [],
                "internal_transitions": [],
              }
            ],
            "hooks": {"on_initial": [], "on_entry": [], "on_exit": []},
            "initial_transition": {"id": "parent_init", "target_id": "outside"},
            "external_transitions": [],
            "internal_transitions": [],
          },
        ],
      }
    )

  assert excinfo.value.code == "hsm_document.unknown_state_reference"
  assert excinfo.value.message == (
    "State 'parent' initial transition references unknown target state 'outside'."
  )


def test_load_hsm_document_accepts_local_initial_targeting_descendant_state():
  document = load_hsm_document(
    {
      "schema_version": "hsm-v1",
      "document_id": "desc_initial_machine",
      "variables": [],
      "events": [],
      "initial_transition": {"id": "machine_init", "target_id": "parent"},
      "states": [
        {
          "id": "parent",
          "states": [
            {
              "id": "child",
              "states": [
                {
                  "id": "leaf",
                  "states": [],
                  "hooks": {"on_initial": [], "on_entry": [], "on_exit": []},
                  "external_transitions": [],
                  "internal_transitions": [],
                }
              ],
              "hooks": {"on_initial": [], "on_entry": [], "on_exit": []},
              "external_transitions": [],
              "internal_transitions": [],
            }
          ],
          "hooks": {"on_initial": [], "on_entry": [], "on_exit": []},
          "initial_transition": {"id": "parent_init", "target_id": "leaf"},
          "external_transitions": [],
          "internal_transitions": [],
        }
      ],
    }
  )

  assert document.states[0].initial == HsmInitialTransition(
    id="parent_init",
    target_id="leaf",
  )


def test_load_hsm_document_rejects_local_initial_target_outside_owner_subtree():
  with pytest.raises(HsmValidationError) as excinfo:
    load_hsm_document(
      {
        "schema_version": "hsm-v1",
        "document_id": "door_machine",
        "variables": [],
        "events": [],
        "initial_transition": {"id": "machine_init", "target_id": "parent"},
        "states": [
          {
            "id": "parent",
            "states": [
              {
                "id": "child",
                "states": [],
                "hooks": {"on_initial": [], "on_entry": [], "on_exit": []},
                "external_transitions": [],
                "internal_transitions": [],
              }
            ],
            "hooks": {"on_initial": [], "on_entry": [], "on_exit": []},
            "initial_transition": {"id": "parent_init", "target_id": "other"},
            "external_transitions": [],
            "internal_transitions": [],
          },
          {
            "id": "other",
            "states": [],
            "hooks": {"on_initial": [], "on_entry": [], "on_exit": []},
            "external_transitions": [],
            "internal_transitions": [],
          },
        ],
      }
    )

  assert excinfo.value.code == "hsm_document.invalid_local_initial_target"
  assert excinfo.value.message == (
    "State 'parent' initial transition target 'other' must reference a descendant state in its subtree."
  )


def test_load_hsm_document_rejects_runtime_like_fields():
  with pytest.raises(HsmValidationError) as excinfo:
    load_hsm_document(
      {
        "schema_version": "hsm-v1",
        "document_id": "door_machine",
        "variables": [],
        "events": [],
        "initial_transition": {"id": "machine_init", "target_id": "closed"},
        "states": [
          {
            "id": "closed",
            "history": "shallow",
            "states": [],
            "hooks": {"on_initial": [], "on_entry": [], "on_exit": []},
            "external_transitions": [],
            "internal_transitions": [],
          }
        ],
      }
    )

  assert excinfo.value.code == "hsm_document.additional_property"
  assert excinfo.value.message == (
    "Unsupported property 'history' at 'states[0]'."
  )


def test_load_hsm_document_rejects_transition_only_fields_on_internal_transition():
  payload = _minimal_hsm_payload()
  payload["events"] = [{"id": "open_evt"}]
  payload["states"] = [
    {
      "id": "closed",
      "states": [],
      "hooks": {"on_initial": [], "on_entry": [], "on_exit": []},
      "external_transitions": [],
      "internal_transitions": [
        {
          "id": "closed_ping",
          "event_id": "open_evt",
          "target_id": "closed",
        }
      ],
    }
  ]

  with pytest.raises(HsmValidationError) as excinfo:
    load_hsm_document(payload)

  assert excinfo.value.code == "hsm_document.additional_property"
  assert excinfo.value.message == (
    "Unsupported property 'target_id' at 'states[0].internal_transitions[0]'."
  )


def test_load_hsm_document_rejects_unknown_callable_refs():
  payload = _minimal_hsm_payload()
  payload["states"] = [
    {
      "id": "closed",
      "states": [],
      "hooks": {
        "on_initial": [],
        "on_entry": [_callable_ref("missing_activity")],
        "on_exit": [],
      },
      "external_transitions": [],
      "internal_transitions": [],
    }
  ]

  with pytest.raises(HsmValidationError) as excinfo:
    load_hsm_document(payload)

  assert excinfo.value.code == "hsm_document.callable_ref_not_found"
  assert excinfo.value.message == (
    "Callable ref 'tests.support.hsm_callable_fixtures.missing_activity' "
    "at 'states[0].hooks.on_entry[0]' could not be resolved."
  )


def test_load_hsm_document_rejects_invalid_callable_signatures():
  payload = _minimal_hsm_payload()
  payload["states"] = [
    {
      "id": "closed",
      "states": [],
      "hooks": {
        "on_initial": [],
        "on_entry": [_callable_ref("bad_activity_no_args")],
        "on_exit": [],
      },
      "external_transitions": [],
      "internal_transitions": [],
    }
  ]

  with pytest.raises(HsmValidationError) as excinfo:
    load_hsm_document(payload)

  assert excinfo.value.code == "hsm_document.invalid_callable_signature"
  assert excinfo.value.message == (
    "Activity ref 'tests.support.hsm_callable_fixtures.bad_activity_no_args' "
    "at 'states[0].hooks.on_entry[0]' must accept exactly one argument."
  )


def test_validate_hsm_document_reports_external_transition_activity_paths_precisely():
  with pytest.raises(HsmValidationError) as excinfo:
    validate_hsm_document(
      HsmDocument(
        schema_version="hsm-v1",
        document_id="door_machine",
        variables=(),
        events=(HsmEvent(id="open_evt"),),
        states=(HsmState(id="closed"),),
        initial=HsmInitialTransition(id="machine_init", target_id="closed"),
        external_transitions=(
          HsmExternalTransition(
            id="closed_to_open",
            source_id="closed",
            target_id="closed",
            event_id="open_evt",
            activities=(
              HsmCallableRef(
                module="tests.support.hsm_callable_fixtures",
                name="bad_activity_no_args",
              ),
            ),
          ),
        ),
      )
    )

  assert excinfo.value.code == "hsm_document.invalid_callable_signature"
  assert excinfo.value.message == (
    "Activity ref 'tests.support.hsm_callable_fixtures.bad_activity_no_args' "
    "at 'external transition 'closed_to_open' activities[0]' must accept exactly one argument."
  )


def test_validate_hsm_document_rejects_invalid_callable_signatures_on_typed_document():
  with pytest.raises(HsmValidationError) as excinfo:
    validate_hsm_document(
      HsmDocument(
        schema_version="hsm-v1",
        document_id="door_machine",
        variables=(),
        events=(),
        states=(
          HsmState(
            id="closed",
            on_entry=(
              HsmCallableRef(
                module="tests.support.hsm_callable_fixtures",
                name="bad_activity_no_args",
              ),
            ),
          ),
        ),
        initial=HsmInitialTransition(id="machine_init", target_id="closed"),
        external_transitions=(),
      )
    )

  assert excinfo.value.code == "hsm_document.invalid_callable_signature"
  assert excinfo.value.message == (
    "Activity ref 'tests.support.hsm_callable_fixtures.bad_activity_no_args' "
    "at 'state 'closed' on_entry[0]' must accept exactly one argument."
  )
