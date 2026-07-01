# HSM Viewer Server Test

This test file validates the project-backed viewer server controller with an HSM entry model.

- Confirms the session exposes rendered SVG metadata and current runtime state.
- Confirms reset, event dispatch, and variable writes refresh the derived session.
- Confirms server-side highlight resolution stays aligned with runtime traces.
- Confirms the debugger session contract stays aligned with pre-step execution previews and queue draining.
