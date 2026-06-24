# HSM Runtime Test

This test file validates the observable execution behavior of the shared HSM model fixture.

- Confirms initialization starts paused and reaches the expected active leaf when played or stepped.
- Confirms event processing reaches the expected sequence of active states.
- Confirms hooks, activities, and guard branches execute in the expected observable order.
- Confirms paused, running, queue, and pending-execution behavior stay aligned.
- Confirms events enqueued during one event are deferred until that event completes.
- Confirms `setState(...)` forces a runtime state without simulating a real transition.
