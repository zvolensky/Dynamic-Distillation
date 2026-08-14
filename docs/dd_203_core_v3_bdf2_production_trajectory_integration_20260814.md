# DD-203 Core V3 BDF2 Production-Trajectory Integration

## Decision

The property-free production-orchestration gate passes. The accepted
constant-step BDF2 trajectory now exposes the same operational controls needed
by the established controlled trajectory workflow without changing any
physical or numerical equation.

## Implemented Contract

- The default path remains one backward-Euler startup followed by constant-step
  BDF2 roots.
- A caller may inject a separately qualified startup-step solver.
- A caller may inject a separately qualified BDF2-step solver.
- A finite monotonic deadline is checked before startup and before every BDF2
  root.
- A stopped trajectory reports `deadline` or `root_failure` explicitly.
- Requested duration, completed roots, method labels, and the final accepted
  outcome are available through one result object.
- Empty deadline-stopped results reject endpoint access instead of fabricating
  an endpoint.

The runner still rejects a nonpositive, nonintegral, or single-step BDF2 grid.
Changing the timestep still requires a new backward-Euler startup and a new
history chain.

## Verification

Fifteen focused tests pass. They cover:

- unchanged default startup/BDF2 sequencing;
- multi-root history chaining;
- explicit startup and BDF2 solver routing;
- deadline stop before startup;
- deadline stop after startup but before the first BDF2 root;
- startup and BDF2 root-failure reporting;
- endpoint and duration reporting;
- invalid-grid rejection;
- BDF2 kinematics/residual and DD-202 refinement compatibility.

Property, residual, Jacobian, nonlinear-solve, timestep, and trajectory calls
performed by this gate: `0`.

## Boundary

DD-203 authorizes one separately frozen live equivalence test that routes the
accepted BDF2 startup and BDF2 root through the existing qualified performance
machinery. That test must compare solver decisions, Jacobians, and endpoint
states against the serial implementation before accepting the performance
path.

DD-203 does not authorize a longer trajectory, controller tuning, a grid
change, fallback, clipping, projection, or a new physical owner.
