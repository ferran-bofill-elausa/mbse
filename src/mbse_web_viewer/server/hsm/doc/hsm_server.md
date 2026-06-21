# HSM Server

This package serves one rendered HSM viewer session over HTTP.

It connects:

- a validated `HsmModel`
- one mutable `HsmRuntime`
- one rendered SVG from `HsmRender`
- the static browser viewer

The session contract is intentionally small:

- current runtime state
- declared model data needed by the browser controls
- execution trace data needed by the browser inspection view
- pre-resolved SVG ids needed by browser highlighting and focus
