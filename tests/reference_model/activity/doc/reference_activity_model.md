# Reference Activity Model

This folder contains the canonical activity test fixture for one representative activity model.

- `reference_activity_model.json` is the activity model.
- `reference_activity_executables.py` activity model executables used by the tests.

The reference Activity models reset behavior. Partial reset goes directly to a
final node; full reset executes `reset_context_variables` before completing.
