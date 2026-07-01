# Server Layer

The server layer serves the static viewer by using the runtime API.

`mbse_web_viewer.server.http_server` contains the reusable HTTP transport, static asset serving, and runtime/debugger API endpoint wiring.

`mbse_web_viewer.server.viewer_app` contains the project viewer CLI and startup API.

`mbse_web_viewer.server.session` contains shared viewer session payload dataclasses.

`mbse_web_viewer.server.controller` owns project session orchestration.

`mbse_web_viewer.server.model_catalog` renders and serves executable project model SVGs.

`mbse_web_viewer.server.highlighting` maps runtime traces and current steps to viewer highlights.

`mbse_web_viewer.server.debugging` defines model-specific debugger breakpoint targets and matching.

Project-backed controllers may serve SVG artifacts for multiple executable models and declare those models in the session payload. The active viewer session remains model-specific; cross-model execution logs are filtered by the controller before model-specific highlight logic runs.
