from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import ValidationError

from mbse.model.activity.activity_model import ActivityModel
from mbse.model.context.context_model import ContextModel
from mbse.model.hsm.hsm_model import HsmModel
from mbse.model.project.project_model import ProjectModel
from mbse.model.project.project_registry import ProjectRegistry


REFERENCE_PROJECT_PATH = (
  Path(__file__).resolve().parents[3]
  / "reference_model"
  / "project"
  / "reference_project.json"
)


def _write_json(path: Path, payload: dict[str, object]) -> Path:
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(json.dumps(payload), encoding="utf-8")
  return path


def _project_payload(entrypoint: str = "main_hsm") -> dict[str, object]:
  return {
    "schema_version": "mbse-project-model-v0",
    "document_id": "test_project",
    "project_root": "models",
    "entrypoint": entrypoint,
  }


def _context_payload(document_id: str = "shared_context") -> dict[str, object]:
  return {
    "schema_version": "mbse-context-model-v0",
    "document_id": document_id,
    "enums": [],
    "variables": [],
  }


def _hsm_payload(document_id: str = "main_hsm") -> dict[str, object]:
  return {
    "schema_version": "mbse-hsm-model-v0",
    "document_id": document_id,
    "events": [],
    "initial_transition": {"target_id": "idle"},
    "states": [{"id": "idle", "label": "Idle"}],
  }


def _activity_payload(document_id: str = "prepare_order") -> dict[str, object]:
  return {
    "schema_version": "mbse-activity-model-v0",
    "document_id": document_id,
    "initial": {"target_id": "done"},
    "actions": [],
    "decisions": [],
    "finals": [{"id": "done", "label": "Done"}],
  }


def _write_project_with_models(
  tmp_path: Path,
  *models: dict[str, object],
  entrypoint: str = "main_hsm",
) -> Path:
  project_path = _write_json(tmp_path / "project.json", _project_payload(entrypoint))
  for index, model in enumerate(models):
    _write_json(tmp_path / "models" / f"model_{index}.json", model)
  return project_path


def test_project_model_loads_minimal_valid_payload(tmp_path: Path) -> None:
  project_path = _write_json(tmp_path / "project.json", _project_payload())

  model = ProjectModel.loadAndValidate(project_path)

  assert model.getDocumentId() == "test_project"
  assert model.getSchemaVersion() == "mbse-project-model-v0"
  assert model.getProjectRoot() == "models"
  assert model.getEntrypoint() == "main_hsm"


def test_project_model_rejects_invalid_schema_payload(tmp_path: Path) -> None:
  invalid_project = _project_payload()
  invalid_project.pop("entrypoint")

  with pytest.raises(ValidationError):
    ProjectModel.loadAndValidate(
      _write_json(tmp_path / "project.json", invalid_project)
    )


def test_project_registry_resolves_project_root_relative_to_project_file(
  tmp_path: Path,
) -> None:
  nested_path = tmp_path / "nested" / "project.json"
  _write_json(nested_path, _project_payload())
  _write_json(tmp_path / "nested" / "models" / "main_hsm.json", _hsm_payload())

  registry = ProjectRegistry.load(nested_path)

  assert registry.getProjectRootPath() == (
    tmp_path / "nested" / "models"
  ).resolve()


def test_project_registry_discovers_known_mbse_models(tmp_path: Path) -> None:
  project_path = _write_project_with_models(
    tmp_path,
    _context_payload(),
    _hsm_payload(),
    _activity_payload(),
  )
  _write_json(tmp_path / "models" / "ignored.json", {"not": "mbse"})

  registry = ProjectRegistry.load(project_path)

  assert isinstance(registry.getContext(), ContextModel)
  assert isinstance(registry.getEntrypointModel(), HsmModel)
  assert isinstance(registry.getModel("main_hsm"), HsmModel)
  assert isinstance(registry.getActivityModel("prepare_order"), ActivityModel)


def test_project_registry_iterates_executable_models(tmp_path: Path) -> None:
  project_path = _write_project_with_models(
    tmp_path,
    _context_payload(),
    _hsm_payload(),
    _activity_payload(),
  )

  registry = ProjectRegistry.load(project_path)

  assert [model.getDocumentId() for model in registry.iterExecutableModels()] == [
    "main_hsm",
    "prepare_order",
  ]


def test_project_registry_loads_reference_project() -> None:
  registry = ProjectRegistry.load(REFERENCE_PROJECT_PATH)

  assert registry.getEntrypointModel().getDocumentId() == "reference_hsm"
  assert registry.getContext().getDocumentId() == "reference_context"
  assert [model.getDocumentId() for model in registry.iterExecutableModels()] == [
    "reference_activity",
    "reference_hsm",
  ]


def test_project_registry_fails_for_duplicate_document_id(tmp_path: Path) -> None:
  project_path = _write_project_with_models(
    tmp_path,
    _hsm_payload("main_hsm"),
    _activity_payload("main_hsm"),
  )

  with pytest.raises(ValueError, match="Duplicate document_id 'main_hsm'."):
    ProjectRegistry.load(project_path)


def test_project_registry_fails_for_multiple_context_models(tmp_path: Path) -> None:
  project_path = _write_project_with_models(
    tmp_path,
    _hsm_payload(),
    _context_payload("context_one"),
    _context_payload("context_two"),
  )

  with pytest.raises(ValueError, match="more than one ContextModel"):
    ProjectRegistry.load(project_path)


def test_project_registry_fails_for_unknown_entrypoint(tmp_path: Path) -> None:
  project_path = _write_project_with_models(
    tmp_path,
    _activity_payload(),
    entrypoint="missing_model",
  )

  with pytest.raises(KeyError, match="Unknown entrypoint model_id 'missing_model'."):
    ProjectRegistry.load(project_path)


def test_project_registry_resolves_activity_entrypoint(tmp_path: Path) -> None:
  project_path = _write_project_with_models(
    tmp_path,
    _activity_payload(),
    entrypoint="prepare_order",
  )

  registry = ProjectRegistry.load(project_path)

  assert isinstance(registry.getEntrypointModel(), ActivityModel)


def test_project_registry_resolve_model_id_errors_are_explicit(
  tmp_path: Path,
) -> None:
  project_path = _write_project_with_models(tmp_path, _hsm_payload())
  registry = ProjectRegistry.load(project_path)

  with pytest.raises(KeyError, match="Unknown model_id 'missing'."):
    registry.getModel("missing")

  with pytest.raises(
    TypeError,
    match="Model_id 'main_hsm' is not an Activity model.",
  ):
    registry.getActivityModel("main_hsm")
