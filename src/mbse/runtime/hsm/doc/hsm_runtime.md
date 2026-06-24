# HSM Runtime

This package executes a validated `HsmModel` as a hierarchical state machine with queued events, mutable variables, and execution tracing.

## Initialization semantics

Initialization is planned as a trace with `event_id = null`.

- The root `initial_transition` is planned first.
- Entry hooks run from outermost entered state to innermost entered state.
- For each entered composite state with a local `initial_transition`, its activities are recorded on that transition before descending to the target child.
- Nested initial descent repeats until the final active leaf is reached.

## Event resolution

For each event, the runtime starts at the current active leaf and walks upward until one state handles the event.

- Internal transitions do not change active state.
- External transitions may be direct or guard-based.
- If no state handles the event, the event still appears in the execution log with an empty trace.

## External transition order

For one chosen external transition branch, execution order is:

1. Record the external transition in the trace.
2. Run transition `activities` declared on the external transition.
3. Run branch-specific activities for the chosen guard outcome, if any.
4. Run `on_exit` hooks from the current active leaf up to the state that owns the transition.
5. Run `on_exit` hooks along the computed exit path toward the target.
6. Run `on_entry` hooks along the entry path toward the target.
7. If the target has local initial transitions, repeat initial transition activities, nested initial transition, and nested `on_entry` until the final leaf is reached.

## Guard semantics

- A guard is planned before execution as a pending decision with both branches precomputed.
- The guard callable is executed only when that pending node is stepped.
- The execution log stores the resolved boolean result and the chosen target.
- Guard callables must return `bool`.

## Callable context

Hooks, activities, and guards receive a mutable context object with:

- one attribute per runtime variable
- `variables`: the runtime variable dictionary
- `event_id`
- `event_parameters`
- `send_event(...)` to enqueue nested events

After each callable returns, any updated variable attributes are persisted back into runtime state.

## State updates and tracing

- `current_state_id` changes only when the runtime executes an explicit `change_active_state` step.
- `change_active_state` is planned only when one trace reaches a real new active state.
- This explicit state-change step closes one event trace before any later queued event starts.
- The execution log is append-only and preserves event reception order.
