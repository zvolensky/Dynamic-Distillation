# DD-210 Four-Versus-Eight Worker Scaling Result

- Classification: `controlled_bdf2_eight_worker_scaling_passed`
- Decision: `adopt_eight_worker_production_jacobian_backend`
- Four/eight-worker trajectory wall: `8.253709` / `5.376950 s`
- Eight-worker speedup: `1.535x`
- Matrix/report maximum differences: `0.000000e+00` / `0.000000e+00`
- Matrix counts: `7` / `7`
- Logical provider calls / governed wall: `17340` / `31.265 s`
- Retry, tuning, alternate worker count, or fallback: `False`

## Evidence

- Both paths completed one backward-Euler startup and one BDF2 root.
- Every root passed residual, rank, conditioning, physicality, equilibrium,
  conservation, controller, and provider gates.
- All seven four-worker matrices used four workers; all seven eight-worker
  matrices used eight workers.
- Each root rebuilt exactly one basis per configured worker.
- Four/eight-worker adjusted startup wall: `1.784917/2.421944 s`.
- Four/eight-worker logical provider calls: `8,602/8,738`.
- Provider fallback attempted: `False`.

## Decision

Eight workers are adopted as the production colored-Jacobian default for this
machine and Core V3 workload. The gain is real but below the theoretical
`1.8x` task-wave limit, as expected from process, property, and scheduling
overhead. The four-worker path remains a qualified fallback for machines with
fewer physical cores; this result does not authorize oversubscription beyond
the available eight physical cores.

Applied to DD-209's measured `219.115 s` trajectory wall, the short-proof
speedup projects to roughly `143 s` for the same two 30-second paths. This is a
useful reduction, but finite-difference Jacobian count remains the dominant
cost. The next performance increment may test a default-off, linear
accepted-coordinate predictor under a separately frozen unchanged-science
contract. Jacobian reuse, forward differences, provider approximation, and
equation changes remain unauthorized.
