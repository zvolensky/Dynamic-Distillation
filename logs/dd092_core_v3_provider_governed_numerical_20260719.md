# DD-092 Core V3 Provider-Governed Numerical Audit

- Classification: `dd092_core_v3_provider_governed_numerical_passed`
- Decision: `authorize_drafting_one_bounded_three_start_core_v3_root_contract`
- Contract commit: `1ffa504beda0df0c805260401c9d7a5f70cf98cb`
- Structural rank: `40/40`
- Provider provenance pass: `True`
- Wall clock: `11.034 s`
- Full nonlinear solve attempted: `False`
- Dynamic integration attempted: `False`

## Numerical States

| State | Residual inf (diagnostic) | Rank h / h/2 | Bubble rank | Worst condition | Beta | Pass |
|---|---:|---:|---:|---:|---:|---|
| canonical_core_v3_state | 3.978625e-01 | 40 / 40 | 3 / 3 | 2.732091e+06 | 4.459380e-04 | True |
| deterministic_combined_perturbation | 3.966443e-01 | 40 / 40 | 3 / 3 | 2.733414e+06 | 4.456931e-04 | True |

## Authorization

DD-092 passes. One bounded three-start Core V3 steady-root campaign may be drafted and committed under a separate frozen contract. Execution, mass-matrix work, and dynamics remain unauthorized.
