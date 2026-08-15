# DD-222 Full C3/C4 Live-Readiness Audit

## Decision

DD-222 passes every frozen gate and authorizes one separately frozen full-C3/C4
stationary-root campaign. It does not authorize a timestep or dynamic run.

## Scope

- Source: tracked 20-stage C3/C4 workbook with feed on stage 12.
- Topology: reflux drum, ten rectifying volumes, feed volume, seven stripping
  volumes, and combined reboiler/sump.
- Governing properties: DWSIM Peng-Robinson through declared phase interfaces.
- Numerical work: one residual and two colored central-difference Jacobians.
- Prohibited work: nonlinear solve, controller execution, timestep, and dynamic
  integration.

The workbook profile is an audit point, not an accepted Core V3 root.

## Results

| Measure | Result | Gate |
|---|---:|---:|
| Unknowns / residuals | 160 / 160 | square |
| Numerical rank | 160 / 160 | 160 |
| Condenser local rank | 3 / 3 | 3 |
| Worst condition | 3.080727e6 | < 1e8 |
| Spectrum relative change | 2.186122e-9 | < 0.25 |
| Colored/direct sentinel difference | 0.0 | < 1e-6 relative |
| Component telescoping error | 8.594582e-17 | < 1e-12 |
| Energy telescoping error | 2.766423e-17 | < 1e-10 |
| Bubble residual | 3.330669e-15 | < 1e-10 |
| DWSIM calls | 9,634 | < 100,000 |
| Audited wall time | 7.593 s | < 900 s |

Total process wall including provider startup and reporting was approximately
`18.4 s`.

The independently implemented PR bubble calculation differs from the DWSIM
result by only `3.6042e-5 F` and `1.3452e-9` maximum vapor mole fraction.
The source condenser reconstruction gives `118.616654 F` and
`Q_C = -49.640294 MMBTU/h`.

## Efficiency

The full structural pattern requires only 15 colors. Two colored matrices and
17 direct-column cross-checks require 97 residual evaluations, compared with
643 for two uncolored matrices. The cross-checks span every coordinate family
and match the colored result exactly.

## Source Residual

The source profile has scaled residual infinity norm `0.547063`. The dominant
terms are Francis liquid-hydraulic mismatches in the lower column, followed by
smaller upper-column pentane fugacity mismatches. This is not a readiness-gate
failure because the source was never claimed to solve the Core V3 equations.
It identifies the work the stationary-root solve must perform.

## Next Boundary

Freeze one bounded stationary-root campaign before executing it. The campaign
must preserve this pressure profile, topology, equations, DWSIM PR ownership,
scales, physical bounds, colored Jacobian, and hard stops. Root reproducibility,
residual closure, conservation, physicality, phase status, bound activity,
provider provenance, calls, and wall time must be decided in advance. Dynamic
work remains prohibited until a root passes and receives its own DAE audit.
