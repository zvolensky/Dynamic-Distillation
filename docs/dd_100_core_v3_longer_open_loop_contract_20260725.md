# DD-100 Core V3 Longer Open-Loop Contract

## Purpose

DD-100 is the one modest longer open-loop trajectory authorized by DD-099. It
tests whether the corrected governing-storage residual and validated 17-color
Jacobian remain reliable beyond the prior `2 s` window.

## Frozen campaign

All trajectories begin independently from the accepted DD-094 root.

- unchanged-input root hold: `5.0 s` at `dt=1.0 s`;
- `+0.1%` feed-throughput step: `10.0 s` at `dt=1.0 s`;
- independent `+0.1%` feed-throughput step: `10.0 s` at `dt=0.5 s`.

The forcing scales every feed component rate and total feed enthalpy by
`1.001`, preserving feed composition and specific enthalpy. Pressure, duties,
reflux, products, geometry, equations, residual scales, solver tolerances, and
provider ownership remain fixed. Every step uses the DD-099 17-color central
Jacobian and governing trial-state internal-energy storage.

The campaign contains exactly 35 endpoints. It permits no retry, substepping,
controller, pressure dynamics, vapor holdup, clipping, fallback, property
cache approximation, or post-result adjustment.

## Acceptance gates

Every endpoint must pass:

- scaled residual below `1e-8`;
- rank `38/38` and condition below `1e8`;
- equilibrium residual below `1e-10`;
- physicality and discrete component/energy conservation;
- governing provider ownership without fallback or nested bubble solve.

The root must remain stationary. Both feed trajectories must accumulate total
inventory monotonically and match the exact external balance within `1e-6`
relative. Their endpoints must satisfy the frozen inventory, algebraic,
temperature, and accumulation-refinement limits.

The full campaign must average fewer than `6,000` provider calls per endpoint
and complete in less than `180 s` wall time.

Failure stops the longer open-loop path without tuning. Passing authorizes only
the next explicit dynamic-scope decision; it is not production-model or
controller acceptance.
