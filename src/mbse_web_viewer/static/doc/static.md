# Static Viewer

The static viewer contains the browser UI for the MBSE web viewer.

`viewer.js` bootstraps the page, wires UI events, submits runtime actions, and coordinates session rendering.

Shared browser modules are split by responsibility:

- `viewer_state.js`: constants and mutable viewer UI state.
- `viewer_api.js`: HTTP fetch helpers.
- `viewer_utils.js`: HTML and CSS escaping helpers.
- `viewer_declared_values.js`: typed variable and event-parameter rendering, collection, and draft comparison.
- `viewer_viewport.js`: SVG viewport zoom, pan, fit, and centering helpers.
- `viewer_models.js`: project-declared model lookup, SVG loading, model selector rendering, and per-model viewport state.
- `viewer_highlights.js`: applying session highlights, HSM focus modes, and auto-centering focus ids.
- `viewer_breakpoints.js`: breakpoint list rendering, SVG breakpoint markers, drag ordering, and breakpoint centering.
- `viewer_debugger.js`: debugger summary panel rendering.

The static viewer is project-session only. It expects the server payload to provide `models`, `active_model_id`, and per-model `svg_url` values. Model-specific SVG semantics are provided by the server session payload. The browser loads the active model SVG, allows navigation across session-declared models, and applies highlights, focus ids, debugger state, variables, and breakpoints from that payload without executing MBSE model semantics.

The browser is served by the [Viewer Server](../../server/doc/server.md). It
does not execute model code and has no build-time JavaScript dependencies.
