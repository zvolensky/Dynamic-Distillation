# DD-112 Conserved N/U Pressure Initializer Result

- Classification: `dd112_failed`
- Decision: `stop_conserved_nu_pressure_initializer`
- Wall clock: `57.127 s`
- Provider calls: `56057`
- Common-solution difference: `1.880119e-06`
- Colored/full difference: `0.000000e+00`

## Decision

DD-112 formally fails its frozen two-start common-solution gate. The allowed
normalized coordinate difference was `<1e-6`; the observed difference was
`1.880119e-6`. Per the precommitted hard stop, the campaign is retired without
a retry, tolerance change, alternate solver, changed objective, continuation,
timestep, or dynamic integration.

This is not evidence that the 52-equation constrained manifold is infeasible.
Both starts converged, satisfied every exact constraint, retained full rank,
and passed all physical, conservation, provider, and efficiency gates. It is
evidence that the frozen selection campaign did not demonstrate the required
two-start reproducibility.

## Start Results

| Start | Iterations | Objective evaluations | Final objective | Constraint infinity norm | KKT stationarity |
|---|---:|---:|---:|---:|---:|
| DD-094 storage and pressure profile | 18 | 23 | `2.290229077401` | `8.951615e-11` | `5.076666e-7` |
| DD-103 pressure endpoint and live storage | 21 | 37 | `2.290229077413` | `3.014353e-12` | `2.370156e-6` |

Both endpoints were strictly interior. Their minimum normalized bound
distances were `1.941556e-3` and `1.941557e-3`.

## Gate Results

The following gates passed:

- both SLSQP solves reported success;
- all 52 exact constraints were below `1e-8`;
- constraint rank was `52/52`;
- canonical condition number was approximately `2.0543e3`, below `1e8`;
- finite-difference spectrum, registry structure, and colored/full Jacobian
  agreement passed;
- KKT stationarity, interior bounds, pressure ordering, and physicality passed;
- component and energy conservation passed;
- direct DWSIM provider ownership passed;
- `56057` provider calls and `57.127 s` wall time passed their limits.

Only `common_solution` failed.

## Endpoint Difference

The largest normalized coordinate difference was
`1.880119e-6` in the reflux-drum n-Butane bubble-composition coordinate. Other
leading differences were also transformed reflux-drum or rectifying-volume
composition/storage coordinates. The physical endpoint differences were
small: maximum pressure difference `5.56e-8 psia`, temperature difference
`5.30e-5 F`, inventory difference `6.23e-5 lbmol`, liquid-flow difference
`1.76e-3 lbmol/h`, and vapor-flow difference `3.23e-3 lbmol/h`.

These small physical differences explain why the result is encouraging, but
they do not override the frozen acceptance rule.

## Authorization State

- DD-112 rerun or retuning: prohibited.
- Zero-time initializer acceptance audit: not authorized.
- Pressure-enabled timestep or trajectory: not authorized.
- Dynamic integration: not authorized.
- Next action: an explicit architecture/governance decision, not another
  variation of this campaign.
