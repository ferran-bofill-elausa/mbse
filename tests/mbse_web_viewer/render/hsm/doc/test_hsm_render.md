# HSM SVG Render Test

This test file validates that the HSM renderer produces SVG plus a stable highlight index from `HsmModel` alone.

- Confirms the reference HSM renders to valid SVG.
- Confirms states, transitions, guards, and text targets resolve to deterministic SVG ids.
- Confirms focused runtime-relevant structures such as internal transitions and event parameters remain highlightable.
