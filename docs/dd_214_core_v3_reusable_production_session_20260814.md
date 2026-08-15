# DD-214 Reusable Core V3 Production Session

## Decision

The property-free production-session implementation passes. Core V3 now has a
first-class lifecycle that keeps one caller-owned parallel Jacobian executor
alive across multiple controlled BDF2 trajectory segments and shuts it down
only when the application explicitly closes the session.

## Implementation

`TerminalInventoryControlBDF2ProductionSession` composes the already accepted:

- `PersistentParallelColoredJacobian`;
- `TerminalInventoryControlBDF2ParallelStepSolvers`;
- `run_terminal_inventory_control_bdf2_trajectory`.

The session does not introduce another residual, solver, Jacobian, provider,
controller, or integration method. It owns only lifecycle and routing:

- build the caller-supplied executor once;
- optionally warm workers and record the process identities reached;
- retain the accepted backend across uniquely named trajectory calls;
- reject caller attempts to replace the backend;
- reserve failed trajectory names to prevent root-epoch reuse;
- record per-segment wall time;
- measure executor shutdown explicitly and exactly once;
- reject use or restart after closure.

Startup warm-up participation is diagnostic. DD-213 showed that equal-count
startup pings can reach fewer than all configured workers even though every
subsequent Jacobian uses all eight. Mandatory all-worker participation remains
enforced by `PersistentParallelColoredJacobian` on every matrix.

## Scope And Evidence

Seven new property-free tests cover multi-segment reuse, context-managed and
explicit close, duplicate-name and backend-override rejection, failed-segment
reservation, startup failure cleanup, partial warm-up scheduling, closed
backend rejection, and validation before executor construction. Together with
the existing backend and trajectory tests, 24 focused tests pass.

No DWSIM process, property call, residual, Jacobian, nonlinear solve, timestep,
or trajectory is executed by DD-214. DD-213 remains formally failed on its
frozen wall gate and is not reclassified.

## Next Gate

One separately frozen short live session proof may execute two independently
named controlled BDF2 trajectories through one eight-worker session. It must
show:

- no executor shutdown between trajectories;
- exactly one measured final shutdown;
- all eight workers on every Jacobian and one basis rebuild per worker/root;
- unchanged root, physical, conservation, response, and provider results;
- unique root epochs across both trajectories;
- no fallback, retry, tuning, alternate grid, or equation change.

Longer integration remains unauthorized.
