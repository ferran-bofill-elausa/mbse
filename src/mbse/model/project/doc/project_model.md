# Project Model

This package defines the JSON authoring format for MBSE projects and a minimal registry for discovered MBSE model documents.

## Document shape

A project model document contains:

- `schema_version`: must be `mbse-project-model-v0`.
- `document_id`: stable identifier for the project document.
- `project_root`: root path for model discovery, relative to the project file.
- `entrypoint`: `document_id` of the initial execution model.

## Registry

`ProjectRegistry` loads a project file, searches recursively for JSON documents under `project_root`, loads known MBSE model schema versions, and indexes them by `document_id`.

Known model schema versions are context, HSM, and activity models. JSON files without a known MBSE model schema version are ignored.

The registry fails explicitly for duplicate `document_id` values, more than one context model, an unknown entrypoint, and unknown requested model ids.

Executable references remain explicit. `action_language` references are normal Python imports resolved by the active Python environment. Model references use `model_id` values resolved through the registry.
