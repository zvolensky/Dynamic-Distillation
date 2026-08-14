# DD-207 Persistent-Parallel BDF2 Production Integration

## Decision

The property-free production integration passes. The persistent-parallel
colored-Jacobian machinery proven by DD-204 through DD-206 is now available as
reusable Core V3 code rather than campaign-local closures.

## Implementation

`PersistentParallelColoredJacobian` coordinates a caller-owned persistent
executor. It constructs deterministic central-difference color tasks,
dispatches them with fixed `chunksize=1`, validates method and root identity,
assembles the matrix in task order, and records immutable per-matrix evidence.

The coordinator enforces during execution:

- complete task/result cardinality;
- participation by every configured worker;
- exactly one basis rebuild per worker on the first matrix of each root;
- no repeated basis rebuild on later matrices of the same root;
- provider-ownership success and no fallback;
- deterministic matrix assembly independent of completion order.

`TerminalInventoryControlBDF2ParallelStepSolvers` supplies the existing
backward-Euler startup and BDF2 solvers with method-aware Jacobian builders.
The startup worker basis contains the previous inventory, PI memory, initial
coordinates, and physical template. The BDF2 basis contains the complete
two-level inventory, provider-derived energy, PI-memory history, rate scales,
and physical template.

The production trajectory accepts this pair through one `step_solver_backend`
argument. It rejects mixing that backend with individual solver overrides.
The default serial sequence is unchanged, and the DD-203 deadline remains in
the main trajectory loop before every root.

## Verification

Fourteen focused tests cover exact matrix assembly, multi-matrix root-basis
lifecycle, provider and worker-participation failures, payload completeness,
backend routing, override conflict rejection, and existing deadline/root-stop
behavior. The complete Core V3 suite passes `450` tests.

Property, residual, Jacobian, nonlinear-solve, timestep, and trajectory calls
performed by this gate: `0`.

## Boundary

DD-207 changes orchestration only. It does not alter equations, DWSIM provider
authority, controllers, tolerances, grids, or accepted states. One separately
frozen short live replay through the reusable source backend is required before
campaign-local parallel closures can be retired. A longer trajectory remains
unauthorized by this increment.
