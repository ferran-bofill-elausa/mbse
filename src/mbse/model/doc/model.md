# Model Layer

The model layer defines authored model data structure and exposes read-only structural queries over a model.

It also contains shared schema definitions and loading helpers used by concrete model types.

## Validation

Each concrete model supports [`loadAndValidate(path)`](../mbse_model.py). It
validates one JSON document against its schema.

[`ProjectRegistry.load(project_path)`](../project/project_registry.py) validates the project, recursively
discovers recognized MBSE JSON documents below `project_root`, and validates
each one. It rejects duplicate `document_id` values, multiple context models,
and invalid entrypoints. Use `iterExecutableModels()` to list discovered HSM
and Activity models in deterministic document-id order.

## Authoring Documentation

- [Context Model](../context/doc/context_model.md)
- [HSM Model](../hsm/doc/hsm_model.md)
- [Activity Model](../activity/doc/activity_model.md)
- [Project Model](../project/doc/project_model.md)

The JSON schemas are the authoritative format definitions:

- [Shared schema](../mbse_model.json)
- [Context schema](../context/context_model.json)
- [HSM schema](../hsm/hsm_model.json)
- [Activity schema](../activity/activity_model.json)
- [Project schema](../project/project_model.json)

See the [reference project](../../../../tests/reference_model/project/reference_project.json)
for a complete project layout.
