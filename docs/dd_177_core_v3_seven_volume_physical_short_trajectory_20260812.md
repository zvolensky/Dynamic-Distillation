# DD-177 Seven-Volume Physical-Policy Short-Trajectory Result

## Verdict

**DD-177 passes every frozen gate.** Both open-loop paths complete the full
two-second horizon, all 24 moving roots converge, and all eight same-time
physical refinement comparisons pass. This is the first accepted
seven-volume moving trajectory under the corrected Core V3 accuracy policy.

## Root Evidence

- coarse path: `8/8` roots at `0.25 s`;
- refined path: `16/16` roots at `0.125 s`;
- function evaluations: 4 for every root except one refined root requiring 5;
- worst scaled residual: `4.140815e-12`;
- rank: `54/54` at every root;
- worst Jacobian condition: `1.434601e7`;
- physicality, equilibrium, component/energy conservation, and exact discrete
  kinematics: passed at every root;
- property provider: DWSIM Peng-Robinson, with no fallback.

## Dynamic Response

The imposed `+0.1%` feed-rate and feed-enthalpy change produces the expected
positive monotone accumulation:

| Path | Total accumulation, lbmol | Component identity error, lbmol |
|---|---:|---:|
| `8 x 0.25 s` | `0.003968318883174` | `6.11e-13` |
| `16 x 0.125 s` | `0.003968318882690` | `4.10e-13` |

The two total accumulations differ by `4.84e-13 lbmol`.

## Shared-Time Refinement

All eight comparisons at `0.25, 0.50, ..., 2.00 s` pass:

| Worst metric | Result | Limit |
|---|---:|---:|
| Absolute component difference | `1.558675e-5 lbmol` | `<1.0e-4 lbmol` |
| `1 lbmol`-floor-relative difference | `7.258663e-7` | `<1.0e-5` |
| Volume-holdup-relative difference | `3.428178e-7` | `<1.0e-6` |
| Component-difference L1 | `5.535587e-5 lbmol` | `<2.0e-4 lbmol` |
| Absolute signed total difference | `5.834222e-13 lbmol` | `<1.0e-9 lbmol` |
| Rate-coordinate difference | `1.127481e-6` | `<1.0e-5` |
| Algebraic-coordinate difference | `1.234961e-6` | `<1.0e-5` |

The legacy unfloored component-relative diagnostic reaches `7.258663e-7` at
`t=2.0 s`. It would have failed the retired `<1e-7` standalone gate despite
all physical scales, roots, and conservation checks passing. DD-177 therefore
provides direct operational validation of the DD-176 policy correction.

## Efficiency

The campaign completes in `28.494 s` with `103,190` logical property requests,
below the frozen limits of `180 s` and `150,000`. Exact memoization serves
`83,318` requests and delegates `19,872`, an `80.7%` hit fraction.

## Decision

One separately frozen modest open-loop extension may be drafted under the
same physical policy. Controllers remain unauthorized. DD-177 may not be
rerun, tuned, or extended without a new committed contract.

## Artifacts

- `logs/dd177_core_v3_seven_volume_physical_short_trajectory_contract_20260812.json`
- `logs/dd177_core_v3_seven_volume_physical_short_trajectory_20260812.json`
- `logs/dd177_core_v3_seven_volume_physical_short_trajectory_20260812.md`
- `tools/run_core_v3_seven_volume_physical_short_trajectory.py`
