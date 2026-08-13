# DD-180 Seven-Volume Physical-Policy Longer-Trajectory Result

## Verdict

**DD-180 passes every frozen gate.** Both thirty-second paths complete all
`360` moving roots, all `120` shared-time comparisons pass, and duration-
scaled response agrees with integrated external flow. The seven-volume open-
loop dynamic formulation is now ready for structural terminal-inventory-
control design.

## Root Evidence

- coarse path: `120/120` roots at `0.25 s`;
- refined path: `240/240` roots at `0.125 s`;
- completed roots: `360`;
- worst scaled residual: `5.290149e-12`;
- rank: `54/54` at every root;
- worst Jacobian condition: `1.434628e7`;
- physicality, equilibrium, component/energy conservation, and exact discrete
  kinematics: passed at every root;
- DWSIM Peng-Robinson ownership: passed without fallback.

The coarse path requires four function evaluations at 119 roots and five at
one. The refined path uses four evaluations at 201 roots, five at 35, six at
three, and seven at one. Every root remains below the frozen maximum of 20.

## Response

| Metric | Coarse | Refined | Limit |
|---|---:|---:|---:|
| Actual accumulation, lbmol | `0.059524783239413` | `0.059524783238356` | positive |
| Integrated expected, lbmol | `0.059524783239006` | `0.059524783239005` | reference |
| Actual/expected relative error | `6.8323e-12` | `1.0908e-11` | `<1e-6` |
| Component identity, lbmol | `5.8418e-13` | `1.0211e-12` | `<1e-6` |

Both trajectories accumulate inventory monotonically. Their actual total
responses differ by `1.0569e-12 lbmol`, versus `<1e-9 lbmol`.

## Shared-Time Refinement

All 120 same-time comparisons pass:

| Worst metric | Result | Limit | Time of maximum |
|---|---:|---:|---:|
| Absolute component difference | `5.143323e-5 lbmol` | `<1.0e-4 lbmol` | `20.75 s` |
| `1 lbmol`-floor-relative difference | `1.227762e-6` | `<1.0e-5` | `7.00 s` |
| Volume-holdup-relative difference | `5.623436e-7` | `<1.0e-6` | `6.50 s` |
| Component-difference L1 | `1.658663e-4 lbmol` | `<2.0e-4 lbmol` | `21.25 s` |
| Absolute signed total difference | `2.509326e-12 lbmol` | `<1.0e-9 lbmol` | `27.75 s` |
| Rate-coordinate difference | `1.406931e-6` | `<1.0e-5` | `4.00 s` |
| Algebraic-coordinate difference | `2.011474e-6` | `<1.0e-5` | `6.50 s` |

The legacy unfloored component-relative diagnostic peaks at `1.227762e-6`
at `7.00 s` and remains diagnostic only. The physical maxima occur at
different intermediate times and do not show monotone growth through the
thirty-second endpoint.

## Efficiency

The campaign completes in `419.083 s` with `1,577,770` logical property
requests, below the frozen limits of `600 s` and `2,000,000`. Exact
memoization serves `1,266,710` requests and delegates `311,060`, an `80.3%`
hit fraction.

## Decision

Open-loop extension has supplied enough evidence for this stage. The next
authorized work is structural design of terminal inventory control. It shall
introduce no live controller, timestep, or trajectory until equation
ownership, manipulated variables, measurements, signs, limits, anti-windup,
and structural rank are independently frozen and audited.

## Artifacts

- `logs/dd180_core_v3_seven_volume_physical_longer_trajectory_contract_20260812.json`
- `logs/dd180_core_v3_seven_volume_physical_longer_trajectory_20260812.json`
- `logs/dd180_core_v3_seven_volume_physical_longer_trajectory_20260812.md`
- `tools/run_core_v3_seven_volume_physical_longer_trajectory.py`
