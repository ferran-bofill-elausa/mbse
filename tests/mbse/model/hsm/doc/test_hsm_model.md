# HSM Model Test

This test file validates the shared HSM model fixture as authored data.

- Confirms the JSON fixture loads and validates against the HSM schema.
- Confirms structural queries return the expected states, parents, hooks, and transitions.
- Confirms unknown state lookups fail explicitly instead of returning ambiguous results.
