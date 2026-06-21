# HSM Runtime Test

This test file validates the observable execution behavior of the shared HSM model fixture.

- Confirms initialization reaches the expected active leaf.
- Confirms event processing reaches the expected sequence of active states.
- Confirms hooks, activities, and guard branches execute in the expected observable order.
- Confirms `rtc` and `step` modes converge to the same runtime state progression.
