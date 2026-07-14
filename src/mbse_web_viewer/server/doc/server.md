# Server Layer

The server layer serves the static viewer by using the runtime API.

## Launch

```bash
mbse-view project.json --open-browser
```

The default host is `127.0.0.1`; the default port is ephemeral. The viewer is
for local use and has no authentication. It requires Graphviz `dot` and an HSM
project entrypoint.

Python callers can use `startProjectViewerServer(registry)` or
`startProjectViewerServerFromProjectPath(project_path)` from
[`viewer_app`](../viewer_app.py).

## Debugging Session

At startup the server renders every discovered executable model. The browser
model selector lists those models and receives `models`, `active_model_id`,
SVG URLs, state, variables, execution log, highlights, and breakpoints through
`GET /api/session.json`.

The UI can reset, send declared HSM events, edit declared variables, pause,
play, step into/over/out, and manage breakpoints. Activity models are visible
and debugged when reached through an HSM project entrypoint.

## HTTP API

- `GET /`: browser UI.
- `GET /api/session.json`: current `ViewerSession`.
- `GET /artifacts/models/<model_id>/diagram.svg`: one rendered model.
- `POST /api/runtime/reset`, `/play`, `/pause`, `/step-into`, `/step-over`,
  `/step-out`: runtime controls.
- `POST /api/runtime/events`: `{"event_id": "...", "parameters": {...}}`.
- `POST /api/runtime/variables`: `{"variable_id": "...", "value": ...}`.
- `POST /api/debugger/breakpoints/toggle`, `/remove`, `/enabled`, `/order`:
  breakpoint management.

[`http_server`](../http_server.py) contains the reusable HTTP transport, static asset serving, and runtime/debugger API endpoint wiring.

[`viewer_app`](../viewer_app.py) contains the project viewer CLI and startup API.

[`session`](../session.py) contains shared viewer session payload dataclasses.

[`controller`](../controller.py) owns project session orchestration.

[`model_catalog`](../model_catalog.py) renders and serves executable project model SVGs.

`mbse_web_viewer.server.highlighting` maps runtime traces and current steps to viewer highlights.

`mbse_web_viewer.server.debugging` defines model-specific debugger breakpoint targets and matching.

Project-backed controllers may serve SVG artifacts for multiple executable models and declare those models in the session payload. The active viewer session remains model-specific; cross-model execution logs are filtered by the controller before model-specific highlight logic runs.

Related layers: [Render](../../render/doc/render.md) and
[Browser Viewer](../../static/doc/static.md).
