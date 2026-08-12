# DD-175 Seven-Volume Smaller Moving-Step Result

## Verdict

**DD-175 formally fails the retained DD-173 relative-inventory refinement
gate and stops before a trajectory.** Every nonlinear, structural, physical,
conservation, response, provider, performance, and DD-174 physical-scale gate
passes. No retry or alternate timestep was attempted.

## Root Evidence

| Metric | Full `0.25 s` | Half 1 `0.125 s` | Half 2 `0.125 s` |
|---|---:|---:|---:|
| Function evaluations | 4 | 4 | 5 |
| Scaled residual | `1.1922e-12` | `2.2951e-12` | `3.7113e-12` |
| Jacobian rank | 54 | 54 | 54 |
| Jacobian condition | `3.5875e6` | `1.4346e7` | `1.4346e7` |

All endpoints are finite, positive, pressure and temperature ordered,
hydraulically valid, conservative, and exactly consistent with the discrete
component and energy kinematics. Equilibrium closure and DWSIM provider
ownership pass without fallback.

The full and refined paths both accumulate `0.000496039861 lbmol`. Their
total-inventory difference is `8.13e-14 lbmol`, and their global component
accumulation errors remain below `2.40e-13 lbmol`.

## Sole Failed Gate

The maximum component-inventory refinement difference relative to the initial
component inventory is:

`1.172326e-7`, against the frozen requirement `<1.0e-7`.

The miss is about `17.2%` above the threshold. Every other refinement gate
passes:

- maximum rate-coordinate difference: `2.072440e-7` versus `<1e-5`;
- maximum algebraic-coordinate difference: `2.018495e-7` versus `<1e-5`;
- total-inventory difference: `8.13e-14 lbmol` versus `<1e-6 lbmol`.

All DD-174 physical-scale gates pass. Maximum absolute component difference
is `2.535865e-6 lbmol`, maximum volume-holdup-relative difference is
`5.577428e-8`, and component-difference L1 is `9.051805e-6 lbmol`.

## Interpretation

Reducing the full timestep from `1.0 s` to `0.25 s` reduces the strict
relative-inventory discrepancy by `12.99x`. The absolute maximum and L1
differences fall by `12.92x` and `12.87x`. Rate and algebraic differences
fall by `11.77x` and `12.87x`. This is strong refinement behavior and not a
numerical floor, rank loss, conservation defect, or unstable physical
response.

Nevertheless, DD-175 retained the original strict gate specifically to avoid
post-result rationalization. Its contract states that any failed gate stops
the moving path. DD-175 therefore cannot authorize a trajectory, cannot be
rerun, and cannot be followed by an automatically smaller timestep under the
current authorization ladder.

## Efficiency

The campaign uses `13,362` logical provider requests and completes in
`6.727 s`. Exact memoization serves `10,570` requests and delegates `2,792`.

## Artifacts

- `logs/dd175_core_v3_seven_volume_smaller_moving_step_contract_20260812.json`
- `logs/dd175_core_v3_seven_volume_smaller_moving_step_20260812.json`
- `logs/dd175_core_v3_seven_volume_smaller_moving_step_20260812.md`
- `tools/run_core_v3_seven_volume_smaller_moving_step.py`
