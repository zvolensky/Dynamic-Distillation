# DD-178 Seven-Volume Physical-Policy Modest-Trajectory Result

## Verdict

**DD-178 formally fails one duration-inappropriate inherited response ceiling.**
All 120 roots, all 40 shared-time comparisons, and every physical, numerical,
conservation, provider, call, and wall gate pass. DD-178 remains failed and
cannot be rerun.

## Passing Evidence

- coarse path: `40/40` roots at `0.25 s`;
- refined path: `80/80` roots at `0.125 s`;
- worst scaled residual: `4.740065e-12`;
- rank: `54/54` at every root;
- worst condition: `1.434602e7`;
- physicality, equilibrium, component/energy conservation, and exact discrete
  kinematics: passed at every root;
- all 40 physical-refinement comparisons: passed;
- DWSIM Peng-Robinson ownership: passed without fallback;
- logical calls: `520,676` versus `<650,000`;
- wall time: `136.773 s` versus `<240 s`.

Worst shared-time refinement remains inside every frozen limit:

| Metric | Result | Limit |
|---|---:|---:|
| Absolute component difference | `2.747674e-5 lbmol` | `<1.0e-4 lbmol` |
| Volume-holdup-relative difference | `5.623436e-7` | `<1.0e-6` |
| Component-difference L1 | `1.216876e-4 lbmol` | `<2.0e-4 lbmol` |
| Rate-coordinate difference | `1.406931e-6` | `<1.0e-5` |
| Algebraic-coordinate difference | `2.011474e-6` | `<1.0e-5` |

## Sole Failed Gate

The DD-178 contract inherited DD-175's absolute maximum total response of
`0.01 lbmol`, which was designed for a subsecond step. The unchanged net feed
increment over ten seconds requires approximately:

`0.019841594413 lbmol`.

The paths produced:

| Path | Actual, lbmol | Integrated expected, lbmol | Error, lbmol |
|---|---:|---:|---:|
| Coarse | `0.019841594414340` | `0.019841594413002` | `1.34e-12` |
| Refined | `0.019841594413359` | `0.019841594413002` | `3.57e-13` |

Both response gates therefore fail only `bounded` because correct ten-second
accumulation exceeds the inherited `0.01 lbmol` ceiling. Accumulation is
positive, monotone, conservative, and agrees between grids within
`9.82e-13 lbmol`.

## Interpretation

The failed ceiling was knowably incompatible with the frozen duration and
disturbance. It should have been scaled to integrated expected external flow
before the contract was committed. This is a contract-design defect, not a
dynamic-model defect.

DD-178 remains formally failed. No rerun or changed live trajectory is
permitted. A separately frozen zero-call adjudication may inspect only the
immutable actual and expected response evidence and decide whether a
duration-scaled response policy can govern future contracts.

## Artifacts

- `logs/dd178_core_v3_seven_volume_physical_modest_trajectory_contract_20260812.json`
- `logs/dd178_core_v3_seven_volume_physical_modest_trajectory_20260812.json`
- `logs/dd178_core_v3_seven_volume_physical_modest_trajectory_20260812.md`
- `tools/run_core_v3_seven_volume_physical_modest_trajectory.py`
