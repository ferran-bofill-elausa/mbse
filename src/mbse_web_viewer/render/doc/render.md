# Render Layer

The render layer transforms authored models into SVG artifacts with stable structural ids and lookup helpers.

Model-specific renderers live under `render/hsm` and `render/activity`.

Rendering requires Graphviz `dot`. It is used by the local viewer to render
every executable model when the viewer starts.

- [HSM Render](hsm/doc/hsm_render.md) and [source](hsm/hsm_render.py)
- [Activity Render](activity/doc/activity_render.md) and [source](activity/activity_render.py)
- [Viewer Server](../../server/doc/server.md): serves rendered SVG artifacts.
