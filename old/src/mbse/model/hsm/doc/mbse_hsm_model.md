# MBSE HSM model

MBSE HSM JSON is authored as a state-owned tree.

## Document shape

Required root fields:

- `schema_version` — must be `hsm-v1`
- `document_id`
- `variables[]`
- `events[]`
- `initial_transition`
- `states[]`

## State shape

Each state contains:

- `id`
- `label` (optional, unchanged)
- `states[]`
- `hooks { on_entry[], on_initial[], on_exit[] }`
- `initial_transition` (optional)
- `external_transitions[]`
- `internal_transitions[]`

## Transition rules

### Initial transitions

- Root `initial_transition` is required.
- State `initial_transition` is optional.
- Root `initial_transition` may target any declared state in the model.
- State `initial_transition` must target a descendant state contained in that state's subtree.
- Guards are not allowed on initial transitions.

Entry semantics:

- Taking an initial transition runs the owner's `on_initial[]` first.
- If the target is a deep descendant, the runtime enters every state on the path from owner to target in order.
- Example: if `A.initial_transition -> C` and `A` contains `B` which contains `C`, the runtime runs `B.on_entry[]` and then `C.on_entry[]`.
- Intermediate states entered this way do not run `on_initial[]` unless they are later reached as the owner of their own declared `initial_transition`.

### External transitions

Each external transition is owned by its source state, so `source_id` is not authored.

- Direct form: `{ id, event_id?, target_id, activities[]? }`
- Guarded form: `{ id, event_id?, guard }`

Guarded transitions embed the decision:

```json
{
  "id": "idle_to_job_check",
  "event_id": "start_evt",
  "guard": {
    "guard": { "module": "pkg.activities", "name": "can_start" },
    "true_branch": { "target_id": "active" },
    "false_branch": { "target_id": "idle" }
  }
}
```

Rules:

- external transitions may use `target_id` or `guard`, never both
- guarded external transitions must not also declare transition-level `activities`
- branch activities belong on `true_branch` / `false_branch`

`guard.id` is optional. If omitted, the loader derives a stable internal guard-node id from the transition id.

### Internal transitions

Internal transitions are also state-owned, so `source_id` is not authored.

```json
{ "id": "idle_ping", "event_id": "ping_evt", "activities": [] }
```

Guards and targets are not allowed on internal transitions.

## Validation highlights

- all IDs are document-global and unique
- IDs must match `^[a-z][a-z0-9_]*$`
- event parameter names must be unique per event
- unknown properties are rejected
- root initial targets must reference declared states
- state initial targets must reference descendant states in the owner's subtree
- external and internal transition targets/sources must reference declared states as required
- guard branch targets must reference declared states
- callable refs must resolve to importable Python callables with the expected signature

## Notes

- `json_schema/hsm_schema_v1.json` is the authoritative contract.
