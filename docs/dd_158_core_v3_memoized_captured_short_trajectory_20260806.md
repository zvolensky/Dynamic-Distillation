# DD-158 Memoized Captured Short-Trajectory Result

## Decision

DD-158 passes every frozen gate. Production exact memoization integrates into the accepted 10-second captured trajectory without changing a solver decision, capture, accepted state, or endpoint. One separately frozen longer memoized trajectory is authorized; multi-minute operation remains unauthorized.

- Contract commit: `ae2bde8`
- Contract payload SHA-256: `c30cbbc4c64051a2a16085819785e487ad898e629c84103174427b58bde24210`
- Classification: `memoized_captured_short_trajectory_equivalent`
- Decision: `authorize_separately_frozen_longer_memoized_trajectory`
- Memoized trajectory wall: `5.337740 s`
- Governed total wall: `21.950154 s`
- Pool startup wall: `6.323153 s`

## Scientific Equivalence

- Both paths complete all `10/10` coarse and `20/20` refined roots.
- Complete captured-solver difference from DD-149: `0.0` on both paths.
- Accepted-state and endpoint difference from DD-149: `0.0` on both paths.
- Every inherited DD-149 scientific, physical, conservation, provider, rank, condition, globalization, work-count, ownership, and equivalence gate passes.
- No Jacobian rebuild, retry, fallback, clipping, projection, controller change, or grid change occurs.

## Memo Accounting

| Quantity | Result |
|---|---:|
| Roots | `30` |
| Logical thermo calls | `35,280` |
| Exact-cache hits | `24,540` |
| Delegate calls | `10,740` |
| Overall hit fraction | `69.56%` |
| Minimum root hit fraction | `69.56%` |
| Per-root accounting | `818` hits, `358` misses, `1,176` calls |

Every Jacobian receives a unique epoch derived from its colored-task state prefix. All four workers clear their exact caches lazily on their first task for that epoch, so no thermodynamic state crosses a Jacobian boundary.

## Performance

DD-149's non-memoized trajectory wall is `7.412999 s`. DD-158 completes the same trajectory work in `5.337740 s`, a ratio of `0.7201` or `1.389x` speedup. This passes the frozen `<=0.75` ratio.

Total wall improves only modestly because DWSIM pool startup is a fixed cost and dominates a 10-second simulation. The efficiency benefit should become more representative over a longer trajectory, which is why the authorized successor should repeat the accepted 60-second path before considering multi-minute work.

## Next Boundary

The next contract may repeat the exact DD-150/DD-146 60-second coarse/refined trajectory with one unique memo epoch per Jacobian. It must retain complete scientific equivalence, exact per-root memo accounting, and a meaningful trajectory-wall improvement. DD-158 does not authorize a five-minute rerun.
