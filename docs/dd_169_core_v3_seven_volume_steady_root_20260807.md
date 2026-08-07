# DD-169 Seven-Volume Stationary-Root Campaign

## Verdict

**DD-169 passes every frozen gate.** Both precommitted, materially independent
starts converge to the same positive, interior, conservative, phase-valid
seven-volume stationary root.

The normalized physical difference between endpoints is `1.918327e-12`, far
below the `1e-7` common-root limit. No retry, continuation, fallback, clipping,
projection, alternate solver, timestep, or dynamic integration occurred.

## Campaign Results

| Metric | Source-mapped start | Independent smooth start | Gate |
|---|---:|---:|---:|
| Function evaluations | 50 | 51 | `<=500` |
| Solve wall, s | 21.532 | 22.395 | Reported |
| Scaled residual infinity norm | `4.98e-13` | `5.55e-15` | `<1e-8` |
| Minimum transformed bound distance | `0.175877` | `0.175877` | `>1e-6` |
| Worst Jacobian condition | `3.5130e3` | `3.5130e3` | `<1e8` |
| Spectrum relative change | `8.31e-10` | `7.02e-10` | `<0.25` |
| Memo hits | 162,499 | 169,693 | Reported |
| Memo misses | 10,697 | 11,153 | Reported |
| Start accepted | Yes | Yes | Required |

Both endpoint Jacobians retain rank `56/56` and local condenser rank `3/3` at
both finite-difference steps. No zero rows, zero columns, unexpected couplings,
or active bounds occur. Component and energy telescoping remain at machine
precision. TP-flash and independent-PR validation pass for both endpoints.

The full campaign records `354,104` logical provider requests and completes in
`49.436 s`. Exact-state memoization serves `332,192` repeated requests and
leaves `21,850` cache misses across both solves, demonstrating that the larger
model remains computationally manageable without changing its equations.

## Accepted Root

Values below are from the source-mapped endpoint; the independent endpoint is
materially identical.

| Volume | Temperature F | Liquid amount lbmol | Liquid C3 | Liquid C4 | Liquid C5 |
|---|---:|---:|---:|---:|---:|
| Reflux drum | 127.5877 | 1388.9000 | 0.776700 | 0.217484 | 0.005817 |
| Rectifying volume 1 | 144.0804 | 35.7751 | 0.594345 | 0.385816 | 0.019839 |
| Rectifying volume 2 | 161.6778 | 31.9776 | 0.440178 | 0.514260 | 0.045562 |
| Feed volume | 175.5270 | 45.4666 | 0.334919 | 0.578922 | 0.086159 |
| Stripping volume 1 | 183.7706 | 54.3455 | 0.276517 | 0.630008 | 0.093475 |
| Stripping volume 2 | 193.7955 | 53.5564 | 0.206947 | 0.681215 | 0.111838 |
| Reboiler/sump | 206.5344 | 794.0000 | 0.133274 | 0.708103 | 0.158623 |

Interior liquid flows are `5599.02`, `5435.71`, `12626.96`, `12700.51`, and
`12746.86 lbmol/h`. Vapor links from bottom to top are `7824.84`, `7778.49`,
`7704.94`, `7656.67`, `7819.97`, and `8173.43 lbmol/h`.

Products are `D=2220.952` and `B=4922.022 lbmol/h`; their sum matches the feed.
Solved condenser duty is `Q_C=-51.776179 MMBTU/h`. Reboiler duty remains the
frozen prescribed operating input.

## Meaning

DD-169 establishes that the Core V3 architecture scales beyond the original
five-volume feasibility model without losing a reachable, reproducible
physical stationary solution. The larger model has smooth composition and
temperature profiles, physically responsive interior liquid hydraulics, and
energy-owned vapor traffic.

This does not yet establish a dynamic model. The next authorized increment is
only a structural seven-volume conserved dynamic-DAE contract defining states,
rates, algebraic variables, controller exclusions, mass-matrix ownership, and
consistent-initialization requirements.

## Artifacts

- `logs/dd169_core_v3_seven_volume_steady_root_contract_20260807.json`
- `logs/dd169_core_v3_seven_volume_steady_root_20260807.json`
- `logs/dd169_core_v3_seven_volume_steady_root_20260807.md`
- `tools/run_core_v3_seven_volume_steady_root.py`
