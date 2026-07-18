# DD-075 Reduced-Column Feasibility Study

- Classification: `reduced_feasibility_solve_gate_failed`
- Accepted: `False`
- Numerical authorization gate: `True`
- Elapsed wall time: `218.323 s`
- Thermo: `DWSIM PR`

## Reduced Topology

| Reduced stage | Physical role | Source stage |
|---:|---|---:|
| 1 | reflux_drum | 1 |
| 2 | rectifying_tray | 6 |
| 3 | feed_tray | 12 |
| 4 | stripping_tray | 16 |
| 5 | combined_reboiler_sump | 20 |

## Structural Gate

- Unknowns/equations: `71 / 71`
- Structural rank/nullity: `71 / 0`
- Gate passed: `True`

## Initial Numerical Gate

| Seed/audit | Rank | Nullity | Condition | Empty rows | Empty columns |
|---|---:|---:|---:|---:|---:|
| chemsep | 71 | 0 | 2.47553e+07 | 0 | 0 |
| chemsep_half_step | 71 | 0 | 2.451e+07 | 0 | 0 |
| perturbed_chemsep | 71 | 0 | 2.92224e+07 | 0 | 0 |
| perturbed_chemsep_half_step | 71 | 0 | 2.752e+07 | 0 | 0 |

## Fixed Solver Attempts

| Method | Seed | Accepted | Residual inf | Rank | Condition | Iterations | Evaluations |
|---|---|---:|---:|---:|---:|---:|---:|
| trust_region | chemsep | False | 0.0349758 | 71 | 4.57126e+11 | 85 | 102 |
| trust_region | perturbed_chemsep | False | 0.0355033 | 70 | 1.68774e+14 | 29 | 43 |
| pseudo_transient | chemsep | False | 0.464495 | 71 | 1.74037e+07 | 13 | 838 |
| pseudo_transient | perturbed_chemsep | False | 0.46552 | 71 | 1.74186e+07 | 14 | 904 |

## Decision

The five-volume direct system did not pass both fixed solvers from both predefined seeds without safeguards. Retire the present conserved formulation; do not add topology or tuning variants.

This is the sole reduced topology and fixed solver recipe. A failed result does not authorize a tray-count ladder, equation-block removal, profile forcing, clipping, or post-run parameter tuning.
