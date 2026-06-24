from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import ValidationError

from mbse.model.hsm.hsm_model import HsmModel


FIXTURE_PATH = (
  Path(__file__).resolve().parents[3] / "reference_model" / "hsm" / "reference_hsm_model.json"
)


def _write_model(tmp_path: Path, model: dict[str, object]) -> Path:
  model_path = tmp_path / "model.json"
  model_path.write_text(json.dumps(model), encoding="utf-8")
  return model_path


def _load_fixture() -> dict[str, object]:
  with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
    return json.load(fixture_file)


def test_load_and_validate_hsm_model() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)

  assert model.getDocumentId() == "reference_hsm"
  assert model.getSchemaVersion() == "mbse-hsm-model-v0"
  assert model.getRootInitialTargetId() == "s1"
  assert [event["id"] for event in model.getEvents()] == [
    "transition",
    "ping",
    "choose_transition",
    "set_mode",
  ]
  assert model.getVariableDefaultValue("last_ping_value") == 0
  assert model.getEnumValues("transition_mode") == ["normal", "forced"]


def test_hsm_model_exposes_expected_structure_queries() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)

  assert [state["id"] for state in model.getStates()] == ["s1", "s2", "s3", "s4"]
  assert [state["id"] for state in model.getChildStates("s2")] == ["s21"]
  assert [state["id"] for state in model.getChildStates("s211")] == ["s2111", "s2112"]
  assert model.getParentStateId("s2112") == "s211"
  assert model.getParentStateId("s1") is None
  assert model.hasStateInitialTransition("s4") is True
  assert model.getStateInitialTargetId("s4") == "s41"
  assert model.getStateInitialTransitionActivities("s4") == [
    {
      "module": "tests.reference_model.hsm.reference_hsm_callables",
      "name": "s4_initial",
    }
  ]
  assert model.getStateLabel("s311") == "S311"


def test_hsm_model_iterators_and_finders_match_fixture_structure() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)

  assert [state["id"] for state in model.iterStates()] == [
    "s1",
    "s11",
    "s111",
    "s1111",
    "s11111",
    "s2",
    "s21",
    "s211",
    "s2111",
    "s2112",
    "s3",
    "s31",
    "s311",
    "s4",
    "s41",
  ]
  assert model.findExternalTransition("s1", "transition")["target_id"] == "s211"
  assert model.findExternalTransition("s41", "choose_transition")["guard_condition"][
    "true_branch"
  ]["target_id"] == "s41"
  assert model.findInternalTransition("s41", "ping") is not None
  assert model.getStateOnEntry("s41")[0]["name"] == "s41_entry"


def test_get_parent_state_id_raises_for_unknown_state() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)

  with pytest.raises(KeyError, match="Unknown state_id 'missing'."):
    model.getParentStateId("missing")


def test_hsm_model_rejects_invalid_schema_payload(tmp_path: Path) -> None:
  invalid_model = _load_fixture()
  invalid_model.pop("document_id")
  invalid_path = tmp_path / "invalid_reference_hsm.json"
  invalid_path.write_text(json.dumps(invalid_model), encoding="utf-8")

  with pytest.raises(ValidationError):
    HsmModel.loadAndValidate(invalid_path)


def test_hsm_model_exposes_event_parameters() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)

  assert model.getEventParameters("transition") == []
  assert model.getRootInitialTransitionActivities() == []
  assert model.getEventParameters("ping") == [
    {
      "name": "value",
      "type": "signed",
      "min": -100,
      "max": 100,
    }
  ]


def test_hsm_model_allows_missing_optional_enums_and_variables(tmp_path: Path) -> None:
  model_path = _write_model(
    tmp_path,
    {
      "schema_version": "mbse-hsm-model-v0",
      "document_id": "minimal_model",
      "events": [],
      "initial_transition": {"target_id": "idle"},
      "states": [{"id": "idle", "label": "Idle"}],
    },
  )

  model = HsmModel.loadAndValidate(model_path)

  assert model.getEnums() == []
  assert model.getVariables() == []


def test_hsm_model_exposes_enum_queries() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)

  assert model.getEnums() == [
    {
      "id": "transition_mode",
      "values": ["normal", "forced"],
    }
  ]
  assert model.getEnumById("transition_mode") == {
    "id": "transition_mode",
    "values": ["normal", "forced"],
  }
  assert model.getEnumValues("transition_mode") == ["normal", "forced"]


def test_hsm_model_exposes_typed_variables_and_event_parameters() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)

  assert model.getVariableByName("last_ping_value") == {
    "name": "last_ping_value",
    "type": "signed",
    "min": -100,
    "max": 100,
    "default_value": 0,
  }
  assert model.getVariableDefaultValue("current_mode") == "normal"
  assert model.getEventParameters("choose_transition") == [
    {
      "name": "self_transition",
      "type": "bool",
    },
  ]
  assert model.getEventParameters("set_mode") == [
    {
      "name": "target_mode",
      "type": "enum",
      "enum_id": "transition_mode",
    },
  ]
  assert model.getEventParameterByName("set_mode", "target_mode") == {
    "name": "target_mode",
    "type": "enum",
    "enum_id": "transition_mode",
  }


def test_hsm_model_rejects_invalid_typed_variable_and_parameter_shapes(tmp_path: Path) -> None:
  invalid_variable_path = _write_model(
    tmp_path,
    {
      "schema_version": "mbse-hsm-model-v0",
      "document_id": "invalid_variable_model",
      "variables": [
        {
          "name": "counter",
          "type": "unsigned",
          "min": 0,
          "max": 10,
        }
      ],
      "events": [],
      "initial_transition": {"target_id": "idle"},
      "states": [{"id": "idle", "label": "Idle"}],
    },
  )

  with pytest.raises(ValidationError):
    HsmModel.loadAndValidate(invalid_variable_path)

  invalid_parameter_path = _write_model(
    tmp_path,
    {
      "schema_version": "mbse-hsm-model-v0",
      "document_id": "invalid_parameter_model",
      "events": [
        {
          "id": "tick",
          "label": "Tick",
          "parameters": [{"name": "value", "type": "unsigned", "min": 0}],
        }
      ],
      "initial_transition": {"target_id": "idle"},
      "states": [{"id": "idle", "label": "Idle"}],
    },
  )

  with pytest.raises(ValidationError):
    HsmModel.loadAndValidate(invalid_parameter_path)


def test_hsm_model_rejects_legacy_on_initial_hook_shape(tmp_path: Path) -> None:
  invalid_model = _load_fixture()
  invalid_model["states"][0]["hooks"]["on_initial"] = [
    {
      "module": "tests.reference_model.hsm.reference_hsm_callables",
      "name": "legacy_initial",
    }
  ]

  invalid_path = _write_model(tmp_path, invalid_model)

  with pytest.raises(ValidationError):
    HsmModel.loadAndValidate(invalid_path)


def test_hsm_model_exposes_internal_transition_declarations() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)

  assert model.findInternalTransition("s41", "ping") == {
    "event_id": "ping",
    "activities": [
      {
        "module": "tests.reference_model.hsm.reference_hsm_callables",
        "name": "trace_ping_value",
      }
    ],
  }
  assert model.findInternalTransition("s1", "ping") == {
    "event_id": "ping",
    "activities": [
      {
        "module": "tests.reference_model.hsm.reference_hsm_callables",
        "name": "trace_ping_value",
      }
    ],
  }
  assert model.findInternalTransition("s2", "ping") == {
    "event_id": "ping",
    "activities": [
      {
        "module": "tests.reference_model.hsm.reference_hsm_callables",
        "name": "trace_ping_value",
      }
    ],
  }
  assert model.findInternalTransition("s211", "ping") == {
    "event_id": "ping",
    "activities": [
      {
        "module": "tests.reference_model.hsm.reference_hsm_callables",
        "name": "trace_ping_value",
      },
      {
        "module": "tests.reference_model.hsm.reference_hsm_callables",
        "name": "enqueue_transition",
      },
    ],
  }
  assert model.findInternalTransition("s3", "ping") == {
    "event_id": "ping",
    "activities": [
      {
        "module": "tests.reference_model.hsm.reference_hsm_callables",
        "name": "trace_ping_value",
      }
    ],
  }
  assert model.findInternalTransition("s41", "set_mode") == {
    "event_id": "set_mode",
    "activities": [
      {
        "module": "tests.reference_model.hsm.reference_hsm_callables",
        "name": "apply_target_mode",
      }
    ],
  }
