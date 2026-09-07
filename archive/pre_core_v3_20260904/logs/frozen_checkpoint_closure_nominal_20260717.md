# Frozen Checkpoint Closure Audit

- Classification: `local_uv_passed_global_hydraulics_failed_or_unverified`
- Checkpoint run: `20260717_111627` at `2400 s`
- Thermo: `dwsim`
- Terminal mapping complete: `False`

## Local UV Closure

| Metric | Value | Gate |
|---|---:|---:|
| All stages converged | True | True |
| Component reconstruction relative max | 5.78096e-11 | <1e-8 |
| Energy relative max | 4.72619e-12 | <1e-7 |
| Volume relative max | 1.15074e-10 | <1e-7 |
| Equilibrium beta residual max | 6.19017e-11 | <1e-6 |
| Negative phase count | 0 | 0 |
| Solver projection count | 0 | 0 |
| Rejected/attempted projection count | 8 | diagnostic |
| Fugacity residual available | False | True |

The DWSIM provider protocol currently returns a TP-flash result but not phase fugacity coefficients. The beta/flash consistency result is reported, but the requested fugacity gate remains explicitly unverified.

## Column Hydraulic Closure

| Metric | Value | Gate |
|---|---:|---:|
| Nominal simultaneous solve converged | False | True |
| Liquid-flow scaled residual | 1.05454 | <1e-5 |
| Vapor/pressure-drop scaled residual | 6.81537 | <1e-5 |
| Local UV vs global pressure max, psi | 86.7781 | <0.1 |
| Active liquid profile/previous-flow limiters | 18 | 0 |
| Active vapor profile/previous-flow limiters | 18 | 0 |
| Solver projection count | 5 | 0 |
| Rejected/attempted projection count | 29 | diagnostic |
| +/-10% perturbations run | False | True |
| +/-10% pressure spread, psi | not run | <0.1 |
| +/-10% flow relative spread | not run | <1e-4 |

## Mapping Notes

- Interior tray totals and U are frozen; checkpoint liquid/vapor splits are guesses only.
- Top and bottom vessel nodes use checkpoint liquid inventory and reconstructed liquid internal energy.
- The current sandbox represents terminal equipment algebraically and does not conserve virtual terminal-stage inventory.
- Excluded terminal-stage inventory is 12.686165 lbmol; top-vessel vapor=107.728968 lbmol and bottom-vessel vapor=1e-08 lbmol.

## Decision

Do not begin the production DAE rewrite. Local closure and global hydraulic closure are not yet both demonstrated under the strict gates.
