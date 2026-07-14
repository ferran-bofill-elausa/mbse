# MBSE

Python runtime and local web viewer for MBSE JSON models.

## Install

```bash
pip install mbse
```

The web viewer requires [Graphviz](https://graphviz.org/) and its `dot`
command on `PATH`.

```bash
# Ubuntu/Debian
sudo apt install graphviz

# macOS
brew install graphviz
```

On Windows, install Graphviz from its [download page](https://graphviz.org/download/)
and add its `bin` directory to `PATH`.

## Model Validation And Discovery

Load a project to validate its project document and every recognized MBSE JSON
model below `project_root`. The registry rejects duplicate model ids, multiple
contexts, and invalid entrypoints.

```python
from mbse.model.project.project_registry import ProjectRegistry

registry = ProjectRegistry.load("project.json")
models = registry.iterExecutableModels()
print([model.getDocumentId() for model in models])
```

The registry validates JSON shape. Action-language handlers are normal Python
imports and must be available in the active environment when the runtime
executes them.

## Automated Runtime Tests

```python
from mbse.model.project.project_registry import ProjectRegistry
from mbse.runtime.runtime import Runtime

registry = ProjectRegistry.load("project.json")
runtime = Runtime()
runtime.init(registry)
runtime.play()
runtime.sendEvent("start")  # A declared HSM event.

assert runtime.getState()["id"] == "running"
```

Use `getExecutionLog()`, `getVariable()`, and `getState()` for assertions.
`sendEvent()` and `getState()` require an HSM project entrypoint. See the
[Runtime Layer](src/mbse/runtime/doc/runtime.md) for stepping and inspection.

## Web Viewer

```bash
mbse-view project.json --open-browser
```

The viewer lists every executable model, renders its diagram, and provides
events, typed variables, execution logs, model-call stepping, and breakpoints.
It is a local debugging tool that listens on `127.0.0.1` by default.

The viewer requires an HSM project entrypoint. Activity models can be rendered,
listed, and debugged when called from that entrypoint.

## Documentation

- [Model Layer](src/mbse/model/doc/model.md): JSON schemas, validation, and
  project discovery.
- [Context Model](src/mbse/model/context/doc/context_model.md),
  [HSM Model](src/mbse/model/hsm/doc/hsm_model.md),
  [Activity Model](src/mbse/model/activity/doc/activity_model.md), and
  [Project Model](src/mbse/model/project/doc/project_model.md): authoring
  formats.
- [Runtime Layer](src/mbse/runtime/doc/runtime.md): execution and test API.
- [HSM Runtime](src/mbse/runtime/hsm/doc/hsm_runtime.md) and
  [Activity Runtime](src/mbse/runtime/activity/doc/activity_runtime.md):
  execution semantics.
- [Viewer Server](src/mbse_web_viewer/server/doc/server.md),
  [Render Layer](src/mbse_web_viewer/render/doc/render.md), and
  [Browser Viewer](src/mbse_web_viewer/static/doc/static.md): local visual
  debugging architecture.
- [Reference Project](tests/reference_model/project/doc/reference_project.md):
  runnable multi-model fixture used by the test suite.
- [Test Suite](tests/): executable coverage and fixture documentation.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[test]"
ruff check .
pytest
```

VS Code users can run the `✅ Run CI` status-bar button to create `.venv` when
needed and execute the same validation steps as CI locally.

## Releases

### One-Time Setup

Configure a branch protection rule for `main` that requires pull requests and
the `CI / test` status check before merging. Do not push directly to `main`.

Configure a PyPI pending publisher with:

- Project name: `mbse`
- GitHub owner: `<owner>`
- Repository: `<repository>`
- Workflow: `release.yml`
- Environment: `pypi`

### Change Flow

1. Create a branch and open a pull request against `main`.
2. Merge only after `CI / test` passes.

### Release Flow

1. After the release changes are merged, create and push a version tag:

```bash
git tag v0.1.0
git push origin v0.1.0
```

The publish workflow validates, builds, and uploads the package to PyPI. A
failed workflow never uploads a package, but does not remove the pushed tag.
