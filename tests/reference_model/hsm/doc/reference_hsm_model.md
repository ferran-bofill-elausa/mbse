# Reference HSM Model

This folder contains the canonical HSM test fixture for one representative HSM model.

- `reference_hsm_model.json` is the HSM model.
- `reference_hsm_executables.py` HSM model activities used by the tests.

The `reset_model` event is available from `S41`. It captures the `full_reset`
parameter, calls the reference Activity model, and transitions back to `S1`.
