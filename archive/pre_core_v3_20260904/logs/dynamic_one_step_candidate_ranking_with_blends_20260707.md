# Dynamic One-Step Candidate Ranking

Best: `c3c4_stage2_liq_eq_vap_eq_blend075_rhs_terms_20260707` objective `27.2799`
Baseline: `c3c4_stage2_interior_liq_vapor_eq_align_rhs_terms_20260707` objective `27.2837`
Best beats baseline: `True`
Objective improvement vs baseline: `0.00375919`

| label | scorable | objective | dynamic_score | rel_rate_per_s | vapor_rhs_lbmolps | overcoverage | y_drift | median_coverage | error |
|---|---|---|---|---|---|---|---|---|---|
| c3c4_stage2_liq_eq_vap_eq_blend075_rhs_terms_20260707 | 1 | 27.2799 | 26.0764 | 0.0782293 | 0.161159 | 0 | 0.00348299 | 0.384804 |  |
| c3c4_stage2_liq_eq_vap_eq_blend050_rhs_terms_20260707 | 1 | 27.2799 | 26.0764 | 0.0782293 | 0.161159 | 0 | 0.00348299 | 0.384804 |  |
| c3c4_stage2_interior_liq_vapor_eq_align_rhs_terms_20260707 | 1 | 27.2837 | 26.0816 | 0.0782449 | 0.161902 | 0 | 0.00348109 | 0.370778 |  |
| c3c4_vapor_material_reconciled_trial1_smoke_20260707 | 1 | 59.7687 | 56.3592 | 0.169078 | 0.324984 | 19.7812 | 0.00940514 | 3.25876 |  |
| c3c4_vapor_material_reconciled_trial1_no_reprojection_smoke_20260707 | 1 | 261.382 | 249.824 | 0.749472 | 1.32547 | 20.9886 | 0.0403167 | 3.3328 |  |
