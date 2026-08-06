# DD-156 Exact-State Thermo Memoization Result

## Decision

DD-156 passes every frozen gate. Exact-state memoization produces a `3.069x` warm-Jacobian speedup while preserving the saved DD-151 Jacobian bit-for-bit. A bounded production implementation and separately frozen saved-state equivalence benchmark are authorized; a trajectory is not yet authorized.

- Contract commit: `37ffd8b`
- Contract payload SHA-256: `d1092cfb8d6cac10993fafed274d7a903d5ba55a5b858d6d5c62dab1ef56eed2`
- Classification: `exact_thermo_memoization_effective`
- Decision: `authorize_bounded_production_memoization_and_saved_state_proof`
- Analysis wall: `12.437 s`
- Logical governing calls: `3,528`
- Nonlinear solves, accepted timesteps, and trajectories: `0`

## Performance

| Stage | Jacobian wall (s) | Speedup vs uncached | Exact cache hits | Hit fraction |
|---|---:|---:|---:|---:|
| Uncached pass-through | `0.190101` | `1.000x` | `0 / 1,176` | `0.00%` |
| Cold exact memo | `0.083330` | `2.281x` | `818 / 1,176` | `69.56%` |
| Warm exact memo | `0.061935` | `3.069x` | `979 / 1,176` | `83.25%` |

The uncached matrix is `0.828x` the independent DD-153 fresh reference, within the frozen `0.65..1.35` representativeness band.

## Warm-Cache Accounting

| Property family | Logical calls | Hits | Delegate calls | Hit fraction |
|---|---:|---:|---:|---:|
| Direct fugacity | 420 | 351 | 69 | `83.57%` |
| Phase enthalpy | 378 | 314 | 64 | `83.07%` |
| Liquid density | 210 | 170 | 40 | `80.95%` |
| Vapor compressibility | 168 | 144 | 24 | `85.71%` |
| **Total** | **1,176** | **979** | **197** | **83.25%** |

The cold matrix also achieves a `69.56%` hit fraction within a single colored-Jacobian construction. This matters because it shows that most savings do not depend on retaining states across roots; repeated unchanged volume states inside the 42 perturbation evaluations are the dominant opportunity.

## Scientific Integrity

- Uncached, cold-cache, and warm-cache matrices each reproduce the saved DD-151 matrix with maximum difference `0.0`.
- Exact work passes: three matrices, 126 tasks, and 3,528 logical provider calls.
- Every matrix and control operation uses all four expected workers.
- Cache accounting telescopes exactly for every property family and stage.
- Keys use the exact phase label, float temperature, float pressure, and full float composition tuple. No rounding, tolerance, interpolation, or approximate matching occurs.
- All source, pool, call, ownership, matrix, representativeness, speed, hit-fraction, and wall gates pass.

## Next Boundary

The diagnostic wrapper is not production code. The authorized successor should implement a bounded exact-state memoization layer with explicit lifecycle control, immutable/copy-safe array returns, exact keys, per-property hit/miss counters, and regression tests proving neighboring finite-difference states never collide. A separate saved-state benchmark must then reproduce the uncached matrices and demonstrate the expected reduction in delegate calls before any trajectory uses it.
