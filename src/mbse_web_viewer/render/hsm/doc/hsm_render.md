# HSM Render

This package renders `HsmModel` instances to SVG and exposes stable lookup methods for states, transitions, guards, and relevant text fragments.

The renderer consumes only the `HsmModel` query API. It does not read authored JSON directly.

## Output contract

`HsmRender` is the public API:

```python
rendered = HsmRender()
rendered.render(model)
```

After rendering, it exposes:

- `getSvgText()`: rendered SVG document
- `getDotSource()`: DOT source used to produce the SVG
- Get methods from HSM structure to SVG ids

## Highlight categories

- states
- root and local initial transitions
- external transitions
- guard nodes and guard branches
- internal transitions
- state-hook text for `on_entry`, `on_exit`.
- external and internal transition text fragments

## Id derivation

SVG ids are derived deterministically from HSM structure using `_` separators.

Examples:

- `state_s41`
- `initial_transition_s4_to_s41`
- `external_transition_s1_transition_to_s211`
- `guard_branch_s41_transition_true_to_s41`
- `internal_transition_idle_tick`

If a structural base id would collide, a numeric suffix is appended deterministically.
