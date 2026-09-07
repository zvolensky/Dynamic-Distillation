# Frozen Checkpoint Closure Audit

- Classification: `local_uv_passed_global_hydraulics_failed_or_unverified`
- Checkpoint run: `20260717_111627` at `2400 s`
- Thermo: `dwsim`
- Terminal mapping complete: `True`
- Terminal algebraic coupling complete: `False`

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

## Terminal Conserved Inventory

| Metric | Value | Gate |
|---|---:|---:|
| All expected source blocks mapped | True | True |
| Component accounting max error, lbmol | 2.27374e-13 | numerical zero |
| Internal-energy accounting error, BTU | 1.86265e-09 | numerical zero |
| Algebraic coupling complete | False | True |

| Node | Topology role | Conserved | Inventory, lbmol | Volume, ft3 | T guess, F | P guess, psia |
|---|---|---:|---:|---:|---:|---:|
| condenser_stage | eliminated_algebraic_total_condenser_stage | False | 1.31855e-14 | 0 | 113.432 | 223.112 |
| reflux_drum | reflux_drum | True | 1516.27 | 4330.14 | 113.432 | 223.112 |
| reboiler_stage | partial_reboiler_stage | True | 12.6862 | 291.9 | 218.697 | 232.184 |
| bottoms_sump | bottoms_sump | True | 791.927 | 3113.6 | 214.471 | 232.184 |

## Terminal UV Assemblies

| Metric | Value | Gate |
|---|---:|---:|
| Both assemblies converged | True | True |
| Component reconstruction relative max | 2.03988e-12 | <1e-8 |
| Energy relative max | 1.0048e-13 | <1e-7 |
| Volume relative max | 4.99513e-12 | <1e-7 |
| Equilibrium beta residual max | 1.74342e-11 | <1e-6 |
| Accepted projections | 0 | 0 |
| Bottom minus top pressure, psi | -13.9476 | >0 |

| Assembly | T, F | P, psia | Vapor fraction |
|---|---:|---:|---:|
| top_terminal | 114.838 | 213.564 | 0.06358 |
| bottom_terminal | 205.237 | 199.616 | 0.0869588 |

## Mapping Notes

- Interior tray totals and U are frozen; checkpoint liquid/vapor splits are guesses only.
- Condenser stage, reflux drum, reboiler stage, and bottoms sump now have explicit inventory ownership and volume mappings.
- An empty total-condenser stage is eliminated as an algebraic topology placeholder instead of assigning -P*V energy to an empty vessel.
- Terminal inventory accounting includes 12.686165 lbmol in virtual terminal stages, top-vessel vapor=107.728968 lbmol, and bottom-vessel vapor=1e-08 lbmol.
- The current simultaneous algebraic residual still couples liquid-only terminal nodes; terminal conserved nodes are not yet unknowns in that solve.

## Decision

Do not begin the production DAE rewrite. Local closure and global hydraulic closure are not yet both demonstrated under the strict gates.
