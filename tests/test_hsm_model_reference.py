from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import ValidationError

from mbse.model.hsm.hsm_model import HsmModel


FIXTURE_PATH = Path(__file__).with_name("fixtures") / "reference_hsm_model.json"


def _load_fixture() -> dict[str, object]:
  with FIXTURE_PATH.open("r", encoding="utf-8") as fixture_file:
    return json.load(fixture_file)


def test_load_and_validate_reference_hsm_model() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)

  assert model.getDocumentId() == "reference_hsm"
  assert model.getSchemaVersion() == "mbse-hsm-model-v0"
  assert model.getRootInitialTargetId() == "s1"
  assert [event["id"] for event in model.getEvents()] == ["transition"]
  assert model.getVariableDefaultValue("self_transition") is False


def test_reference_hsm_model_exposes_expected_structure_queries() -> None:
  model = HsmModel.loadAndValidate(FIXTURE_PATH)

  assert [state["id"] for state in model.getStates()] == ["s1", "s2", "s3", "s4"]
  assert [state["id"] for state in model.getChildStates("s2")] == ["s21"]
  assert [state["id"] for state in model.getChildStates("s211")] == ["s2111", "s2112"]
  assert model.getParentStateId("s2112") == "s211"
  assert model.getParentStateId("s1") is None
  assert model.hasStateInitialTransition("s4") is True
  assert model.getStateInitialTargetId("s4") == "s41"
  assert model.getStateLabel("s311") == "S311"


def test_reference_hsm_model_iterators_and_finders_match_reference_machine() -> None:
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
  assert model.findExternalTransition("s41", "transition")["guard_condition"][
    "true_branch"
  ]["target_id"] == "s41"
  assert model.findInternalTransition("s41", "transition") is None
  assert model.getStateOnEntry("s41")[0]["name"] == "s41_entry"


def test_reference_hsm_model_rejects_invalid_schema_payload(tmp_path: Path) -> None:
  invalid_model = _load_fixture()
  invalid_model.pop("document_id")
  invalid_path = tmp_path / "invalid_reference_hsm.json"
  invalid_path.write_text(json.dumps(invalid_model), encoding="utf-8")

  with pytest.raises(ValidationError):
    HsmModel.loadAndValidate(invalid_path)
