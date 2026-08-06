# DD-157 Production Exact-Memoization Proof Result

## Decision

DD-157 passes every frozen gate. The production provider's bounded exact-state caches and lazy per-Jacobian epoch mechanism reproduce two independent DD-151 Jacobians bit-for-bit and provide consistent speedup on both grids. A separately frozen short-trajectory integration proof is authorized; longer operation is not.

- Contract commit: `8de7d17`
- Contract payload SHA-256: `2d6ca789f7104609bab2f775a6bb34d09b8d2578739b637dcf724cfd0406fb30`
- Classification: `production_exact_memoization_proved`
- Decision: `authorize_separately_frozen_short_trajectory_memoization_proof`
- Analysis wall: `14.331 s`
- Logical governing calls: `4,704`
- Nonlinear solves, accepted timesteps, and trajectories: `0`

## Results

| Saved state | Uncached (s) | Memoized (s) | Speedup | Exact hits | Matrix difference |
|---|---:|---:|---:|---:|---:|
| Coarse root 180 | `0.334387` | `0.178123` | `1.877x` | `818 / 1,176` (`69.56%`) | `0.0` |
| Refined root 360 | `0.318647` | `0.171132` | `1.862x` | `818 / 1,176` (`69.56%`) | `0.0` |

Both memoized matrices start with a unique epoch. Each worker clears its local exact caches lazily when it receives its first task for that epoch. Therefore these are cold per-Jacobian results, not cross-root warm-cache results.

## Integrity

- Both uncached and both memoized matrices reproduce their saved DD-151 matrices exactly.
- Exact work passes: four matrices, 168 tasks, and 4,704 logical calls.
- Memo accounting passes at 1,176 calls per memoized matrix.
- Every matrix uses all four worker processes.
- Uncached coarse and refined timings are within the frozen fresh-reference range.
- Each path exceeds the `1.50x` speed requirement and `60%` hit-fraction requirement.
- Source, pool, call, memo, ownership, matrix, representativeness, performance, and wall gates all pass.

## Production Boundary

`ThermoProviderV1` memoization remains disabled by default. Parallel workers activate it only when a caller supplies a memo epoch. Caches use exact normalized float states, are bounded, return copied arrays, expose hit/miss/entry counters, and clear at each new epoch.

The next authorized step is a short captured trajectory that adds one unique memo epoch per Jacobian while retaining the accepted solver, grids, controller move, complete capture, and scientific gates. No multi-minute trajectory is authorized by DD-157 alone.
