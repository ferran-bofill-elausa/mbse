# MBSE HSM runtime layer

The HSM runtime turns a validated HSM model into an executable machine and
exposes the **upper-layer API** for runtime consumers.

## Public API

`mbse.runtime.hsm` is intentionally small. Upper layers should import only:

- `build_hsm_runtime`
- `HsmRuntime`
- `HsmRuntimeSnapshot`
- `HsmRuntimeLastEvent`
- `HsmExecutedActivity`

Everything else under `mbse.runtime.hsm` is internal implementation detail,
even if it lives in importable submodules.

## How upper layers use it

Typical usage stays at the runtime boundary:

1. Call `build_hsm_runtime()` with a raw HSM payload or validated `HsmDocument`.
2. Call `runtime.init()` once.
3. Drive behavior with `runtime.send_event(event_id)`.
4. Inspect state through `runtime.get_snapshot()`.

Use `HsmRuntimeSnapshot`, `HsmRuntimeLastEvent`, and
`HsmExecutedActivity` as read models for viewers, automated tests, and bridge
code. Do not couple those callers to generator or preparation internals.

## Responsibility boundaries

The runtime owns execution concerns:

- building an executable runtime from a validated HSM model
- dispatching events, evaluating guards, and applying transitions
- exposing deterministic snapshots for inspection-oriented consumers

It does **not** own:

- model authoring, parsing, or semantic validation
- render/view preparation for SVG, DOM, or browser UX
- transport/session concerns such as HTTP, websocket, or persistence

## Internal structure

The public API above is backed by internal preparation and generation steps.
Those internals are relevant when working inside the runtime layer itself, not
for its consumers:

- `runtime_builder.py` bridges model input to a ready `HsmRuntime`
- `runtime.py` implements execution semantics
- `runtime_state_types.py` defines the snapshot DTOs returned publicly
- `runtime_model/` prepares generated runtime metadata for code generation
- `generator/` renders and loads the generated dispatch module

Generated runtime source persists by default under `build/mbse_runtime/` at the
project root so emitted artifacts stay visible and out of `src/`.
