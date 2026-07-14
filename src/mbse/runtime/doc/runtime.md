# Runtime Layer

The runtime layer executes authored models as mutable runtime instances.

It is responsible for state progression, event queuing, variable mutation, hook and activity execution, and execution tracing.

See the [Model Layer](../../model/doc/model.md) for project loading and
validation.

## Runtime

[`Runtime`](../runtime.py) is the top-level public execution facade. It
consumes a `ProjectRegistry` or one loaded executable model, initializes the
entrypoint HSM or activity runtime, and owns the global execution log.

`Runtime` owns executable resolution. Local HSM and Activity runtimes decide when an executable step must run, but do not resolve executable references themselves.

Supported executable kinds:

- `kind: "action_language"`: executes the referenced action-language function with the current runtime context.
- `kind: "model"`: resolves `model_id` through the project registry and runs that model to completion.

Model executables synchronize shared runtime variables with their caller. If a model executable is used where a value is required, such as a guard or decision condition, the callee's shared `result` variable is used as the return value. The owning slot still validates the value type, so guards and decision conditions require `result` to be `bool`.

`getNextStep()` returns:

- `runtime`: active runtime kind, currently `hsm` or `activity`.
- `model_id`: `document_id` of the active model.
- `step`: native runtime step.

`getExecutionLog()` returns global traces collected by `Runtime`:

- `runtime`: runtime kind.
- `model_id`: model document id.
- `trace`: native runtime trace.

Local HSM and activity runtime logs are not modified. Their native traces are stored under `trace` before a local runtime instance can be discarded.

## Execution API

Initialize with `init(registry)` for a whole project or `initModel(model,
context)` for one already-loaded executable model.

- `play()`, `pause()`, and `isPaused()` control automatic execution.
- `stepInto()`, `stepOver()`, and `stepOut()` support deterministic debugging,
  including nested model calls.
- `sendEvent(event_id, parameters)` queues an event for an HSM root runtime.
- `getState()` and `getEventQueue()` inspect an HSM root runtime.
- `getVariable(name)`, `setVariable(name, value)`, `getNextStep()`,
  `getCallStack()`, `getActiveFrame()`, and `getExecutionLog()` support test
  assertions and diagnostics.

Action-language executable references import Python functions from the active
environment. Model executable references run a discovered HSM or Activity as a
nested runtime frame and synchronize same-named variables with their caller.

## Runtime Semantics

- [HSM Runtime](../hsm/doc/hsm_runtime.md)
- [Activity Runtime](../activity/doc/activity_runtime.md)
