# DD-173 Seven-Volume Open-Loop Moving-Step Result

## Verdict

**DD-173 formally fails one frozen refinement gate and stops before a
trajectory.** The physical response, all three nonlinear roots, and every
other gate pass. No retry or alternate timestep was attempted.

## Passing Evidence

| Metric | Full 1.0 s | Half 1 | Half 2 |
|---|---:|---:|---:|
| Function evaluations | 4 | 4 | 4 |
| Scaled residual | `1.5390e-13` | `2.9676e-13` | `4.4889e-13` |
| Jacobian rank | 54 | 54 | 54 |
| Jacobian condition | `2.2467e5` | `8.9740e5` | `8.9740e5` |
| Maximum component rate, lbmol/h | `3.419` | `3.672` | `3.401` |
| Maximum equilibrium residual | `3.11e-15` | `3.77e-15` | `4.11e-15` |

Every endpoint is positive, finite, pressure and temperature ordered,
hydraulically valid, conservative, and exactly consistent with the discrete
component and energy kinematics. DWSIM provider ownership passes without
fallback.

The imposed feed increment produces the expected positive response:

- full-step total inventory increase: `0.001984159441 lbmol`;
- refined total inventory increase: `0.001984159442 lbmol`;
- full/refined total-inventory difference: `5.7465e-13 lbmol`;
- global component-inventory identity error: below `2.12e-13 lbmol`.

## Failed Gate

The frozen full/refined maximum relative component-inventory difference was:

`1.522960e-6`, against a required value below `1e-7`.

The worst absolute component difference is only `5.9660e-6 lbmol`, on an
initial component inventory of `3.91737 lbmol`. The largest absolute
component difference anywhere is `3.27535e-5 lbmol`. Rate-coordinate and
algebraic refinement pass at `2.43915e-6` and `2.59810e-6`, both below their
`1e-5` limits.

## Assessment

This is not evidence of solver divergence or a wrong global response. It is a
formal failure of a stringent local per-component refinement metric under a
first-order one-second backward-Euler comparison. The result cannot authorize
a trajectory because that limit was frozen before execution.

The appropriate next action is a zero-call physical-scale adjudication of the
saved endpoints. It should determine whether the failed normalized metric is
an appropriate moving-step acceptance measure before any smaller-timestep
campaign is proposed. DD-173 itself must not be rerun or reclassified.

## Efficiency

The campaign uses `13,328` logical provider requests and completes in
`6.798 s`. Exact-state memoization serves `10,546` requests and delegates
`2,782` misses, an approximately `79.1%` hit fraction.

## Artifacts

- `logs/dd173_core_v3_seven_volume_moving_step_contract_20260812.json`
- `logs/dd173_core_v3_seven_volume_moving_step_20260812.json`
- `logs/dd173_core_v3_seven_volume_moving_step_20260812.md`
- `tools/run_core_v3_seven_volume_moving_step.py`
