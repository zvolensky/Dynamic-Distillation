# DD-087 Saturated-Liquid Condenser Numerical Audit

- Classification: `dd087_condenser_saturated_liquid_numerical_passed`
- Decision: `authorize_drafting_one_bounded_40x40_root_contract`
- Contract commit: `69101d16a43198c372fff8bc8c96be528f6ee1f8`
- Structural rank: `40/40`
- Runtime: `7.155 s`
- Full nonlinear solve attempted: `False`
- Dynamic integration attempted: `False`

## Numerical States

| State | Residual inf | Rank h / h/2 | Bubble rank | Worst condition | Pass |
|---|---:|---:|---:|---:|---|
| canonical_saturated_liquid_seed | 3.978625e-01 | 40 / 40 | 3 / 3 | 2.447311e+06 | True |
| deterministic_combined_perturbation | 3.891215e-01 | 40 / 40 | 3 / 3 | 2.442431e+06 | True |

## Canonical Phase Gate

- `sum(x*K)-1`: `1.467850e-05`
- vapor fraction: `4.459380e-04`
- `max|y_bubble-normalize(K*x)|`: `1.219063e-06`
- Pass: `True`

## Decision

DD-087 passes. Drafting and precommitting one bounded 40 x 40 steady-root campaign is authorized. Execution, dynamic integration, and DAE work remain unauthorized.
