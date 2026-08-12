# DD-172 Seven-Volume Stationary Implicit-Step Result

## Verdict

**DD-172 passes every frozen gate.** One `1.0 s` backward-Euler step and two
successive `0.5 s` steps preserve the accepted seven-volume stationary root
without an artificial startup transient.

## Root Results

| Metric | Full 1.0 s | Half 1 | Half 2 |
|---|---:|---:|---:|
| Function evaluations | 2 | 2 | 2 |
| Scaled residual | `1.0051e-13` | `3.8107e-13` | `2.9513e-13` |
| Jacobian rank | 54 | 54 | 54 |
| Jacobian condition | `2.2467e5` | `8.9740e5` | `8.9740e5` |
| Maximum component rate, lbmol/h | `6.44e-9` | `8.19e-9` | `6.42e-9` |
| Relative inventory motion | `1.0280e-12` | `5.3199e-13` | `1.0383e-12` |
| Algebraic-coordinate motion | `1.3852e-12` | `1.5625e-12` | `1.0738e-12` |
| Maximum equilibrium residual | `3.22e-15` | `2.89e-15` | `5.66e-15` |

Component and energy discrete kinematic identities are exactly zero in the
saved arithmetic. Every endpoint remains positive, finite, temperature and
pressure ordered, hydraulically valid, and conservative.

## Refinement

The full-step and second-half-step endpoints agree within:

- relative component inventory: `1.032387e-14`;
- rate coordinates: `2.245103e-13`;
- algebraic coordinates: `6.593615e-13`.

These are far below the frozen `1e-9` / `1e-7` / `1e-7` limits.

## Efficiency

The three roots use `7,344` logical provider calls and complete in `4.447 s`.
Exact-state memoization serves `6,077` requests and delegates `1,267` misses,
an approximately `82.8%` hit fraction. The compact result stores provider
counts and violations rather than tens of thousands of individual call
records.

## Meaning

DD-172 is the first evidence that the seven-volume DAE can take an actual
implicit timestep while remaining exactly where a stationary model should
remain. This removes artificial startup motion as an immediate architectural
concern for the accepted root.

It does not establish moving dynamics. The next authorized increment is one
separately frozen small open-loop moving-step contract, again comparing a full
step with two half steps. Controllers and trajectories remain unauthorized.

## Artifacts

- `logs/dd172_core_v3_seven_volume_stationary_step_contract_20260812.json`
- `logs/dd172_core_v3_seven_volume_stationary_step_20260812.json`
- `logs/dd172_core_v3_seven_volume_stationary_step_20260812.md`
- `tools/run_core_v3_seven_volume_stationary_step.py`
