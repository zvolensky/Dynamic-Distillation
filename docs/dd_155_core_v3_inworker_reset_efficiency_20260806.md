# DD-155 In-Worker Thermo Reset Efficiency Result

## Decision

DD-155 reproduces persistent-worker aging but none of the three in-worker reset layers restores fresh-worker performance. The result therefore rejects a production reset API and retains the existing persistent-worker implementation without another trajectory extension.

- Contract commit: `22f3ba3`
- Contract payload SHA-256: `9527e2487218312d3d4edf30f8c38b22ed7a1ce82f7282f3b5f25956f6efa7af`
- Classification: `inworker_reset_probe_failed`
- Decision: `retain_persistent_workers_and_stop_reset_implementation`
- Analysis wall: `79.171 s`
- Governed provider calls: `220,260`
- Worker processes: `4`
- Nonlinear solves, accepted timesteps, and trajectories: `0`

## Timing Result

The frozen DD-153 fresh reference for coarse root 180 is `0.229702 s` per Jacobian.

| Stage | Median Jacobian (s) | Ratio to fresh | Speedup over aged | Result |
|---|---:|---:|---:|---|
| Aged, no reset | `0.315279` | `1.373x` | `1.000x` | Aging reproduced |
| Clear Python provider caches | `0.321494` | `1.400x` | `0.981x` | No recovery |
| Rebuild provider object | `0.302529` | `1.317x` | `1.042x` | Small, insufficient recovery |
| Reinitialize DWSIM backend objects | `0.322175` | `1.403x` | `0.979x` | No recovery |

Recovery required both reset/fresh `<=1.15x` and no-reset/reset speedup `>=1.20x`. No intervention approached both thresholds.

## Reset Cost

| Reset | Group wall (s) | Reset provider calls | Observation |
|---|---:|---:|---|
| Python cache clear | `0.253` | `0` | Cleared roughly 1,060 exact density entries per worker |
| Provider reconstruction | `0.673` | `116` | Backend process state remained resident |
| DWSIM backend reinitialization | `4.614` | `116` | Calculator/property-package objects rebuilt in place |

The backend intervention explicitly released the Python references to the DWSIM calculator, property package, and compound array, ran Python garbage collection, and reconstructed the objects. It did not restart the Python process or CLR runtime.

## Integrity

- All `179` aging matrices and `8` diagnostic matrices reproduced DD-151 exactly (`0.0` maximum difference).
- Exact work passed: `7,854` tasks and `219,912` worker-evaluation calls.
- Reset calls passed exactly at `232`; startup calls passed exactly at `116`.
- Every matrix and reset used all four expected workers.
- The aging, source, matrix, call-count, ownership, and wall gates passed.
- Only the reset-recovery gate failed.

## Meaning

DD-153 showed that fresh processes are fast. DD-155 now shows that clearing Python caches, replacing `ThermoProviderV1`, or rebuilding DWSIM calculator/property-package objects inside the same process does not recreate that fresh-process performance. The remaining lifetime state is therefore associated with the longer-lived Python/CLR process environment or another state layer not reset by object reconstruction.

Further reset variants are not justified. A more promising efficiency direction is reducing repeated backend work within each Jacobian, such as a separately frozen exact-state memoization benchmark for direct fugacity, enthalpy, density, and compressibility calls. That can be tested on saved Jacobians before any trajectory or solver change.
