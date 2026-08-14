# DD-204 Controlled BDF2 Serial/Parallel Equivalence Result

- Classification: `controlled_bdf2_parallel_equivalence_passed`
- Decision: `authorize_persistent_parallel_bdf2_trajectory_path`
- Completed serial/parallel roots: `2` / `2`
- Matrix maximum difference: `0.000000e+00`
- Endpoint maximum difference: `0.000000e+00`
- Serial/parallel trajectory wall: `9.543881` / `7.369045 s`
- Solve speedup excluding startup: `1.295x`
- Adjusted worker startup / governed wall: `2.036` / `25.378 s`
- Logical provider calls: `17068`
- Retry, tuning, alternate step, or longer trajectory: `False`

## Numerical Result

The serial and persistent-parallel paths each complete exactly two roots: one
`0.125 s` backward-Euler startup and one `0.125 s` BDF2 advance. Both retain
rank `58`; worst scaled residual is `1.868842e-12`, and worst condition is
`3.172741e7`.

All seven paired colored Jacobians differ by exactly `0.0`. Solver statuses,
messages, function/Jacobian counts, costs, optimality, coordinates, residuals,
inventories, rates, energies, controller memories, algebraic states, levels,
and products also differ by exactly `0.0` at both roots.

Every actual Jacobian uses all four workers. Each worker rebuilds the root basis
exactly once for the startup root and exactly once for the BDF2 root. Provider
ownership passes with no fallback.

## Decision

The persistent four-worker Jacobian path is accepted for controlled BDF2
trajectory execution. Its warm-pool trajectory time is `7.369045 s` versus
`9.543881 s` serial, a `1.295x` speedup. Adjusted worker startup is `2.035537 s`.

This result authorizes one separately frozen longer BDF2 trajectory using the
accepted worker path. It does not authorize controller tuning, a timestep
change, fallback, clipping, projection, or an unrestricted production run.
