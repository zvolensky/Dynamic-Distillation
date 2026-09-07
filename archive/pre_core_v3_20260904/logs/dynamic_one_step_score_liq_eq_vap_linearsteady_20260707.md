# Dynamic One-Step Initialization Score

Summary: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_liq_eq_vap_linearsteady_rhs_terms_20260707\column_summary_20260707_171150.csv`
Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_liq_eq_vap_linearsteady_rhs_terms_20260707\column_profile_20260707_171150.csv`
Objective: `6.18033`

## Terms
| metric | value | ref | weight | term |
|---|---|---|---|---|
| dynamic_score | 5.84169 | 1 | 1 | 5.84169 |
| rel_rate_per_s | 0.0175251 | 0.01 | 1 | 1.75251 |
| temp_rate_F_per_s | 0.107584 | 0.1 | 0.5 | 0.537921 |
| vapor_rhs_lbmolps | 0.0478449 | 0.1 | 1 | 0.478449 |
| coverage_error | 0.11586 | 1 | 0.5 | 0.0579302 |
| overcoverage | 1.38281 | 1 | 0.5 | 0.691407 |
| y_drift | 0.000289987 | 0.01 | 0.5 | 0.0144993 |

## Coverage
| median_abs_cancellation_coverage_error | max_cancellation_overcoverage | max_cancellation_undercoverage | median_cancellation_coverage |
|---|---|---|---|
| 0.11586 | 1.38281 | 0.783877 | 0.905385 |

## Top Vapor Conflicts
| stage_1based | stage_kind | component | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | equilibrium_transfer_lbmolps | cancellation_coverage | required_target_delta |
|---|---|---|---|---|---|---|---|
| 3 | interior | n_Propane | -0.0478449 | -0.242751 | 0.194906 | 0.802905 | 0.0020174 |
| 4 | interior | n_Propane | -0.0431271 | -0.220542 | 0.177414 | 0.804449 | 0.0018496 |
| 2 | interior | n_Propane | 0.040918 | 0.0521996 | -0.0112816 | 0.216123 | -0.000494512 |
| 5 | interior | n_Propane | -0.0272317 | -0.165092 | 0.13786 | 0.835051 | 0.00118194 |
| 6 | interior | n_Propane | -0.016921 | -0.113515 | 0.0965938 | 0.850936 | 0.000739866 |
| 11 | interior | n_Butane | -0.0140298 | -0.0361738 | 0.022144 | 0.612156 | 0.000620865 |
| 14 | interior | n_Propane | -0.0135788 | -0.110822 | 0.0972436 | 0.877472 | 0.000606728 |
| 13 | interior | n_Propane | -0.0134171 | -0.0963099 | 0.0828928 | 0.860689 | 0.000598026 |
| 15 | interior | n_Propane | -0.0123036 | -0.121157 | 0.108854 | 0.898449 | 0.000551322 |
| 16 | interior | n_Propane | -0.0119617 | -0.125575 | 0.113613 | 0.904744 | 0.000468341 |
| 12 | interior | n_Butane | 0.0118075 | 0.0757481 | -0.0639406 | 0.844121 | -0.000525105 |
| 16 | interior | n_Butane | 0.0117864 | 0.112684 | -0.100897 | 0.895403 | -0.000461477 |

## Top Vapor Composition Drift
| stage_1based | component | y_initial | y_final | abs_y_drift |
|---|---|---|---|---|
| 3 | n_Propane | 0.856334 | 0.856044 | 0.000289987 |
| 3 | n_Butane | 0.143637 | 0.143926 | 0.000289377 |
| 15 | n_Butane | 0.582629 | 0.582894 | 0.000264877 |
| 14 | n_Butane | 0.538132 | 0.538393 | 0.0002611 |
| 15 | n_Propane | 0.378423 | 0.378175 | 0.000248545 |
| 14 | n_Propane | 0.426204 | 0.425956 | 0.000247875 |
| 4 | n_Propane | 0.768422 | 0.768194 | 0.000228525 |
| 16 | n_Butane | 0.631696 | 0.631924 | 0.000227897 |
| 4 | n_Butane | 0.231475 | 0.231702 | 0.000227123 |
| 13 | n_Butane | 0.499725 | 0.499949 | 0.000224732 |
| 18 | n_Propane | 0.215523 | 0.215301 | 0.00022155 |
| 16 | n_Propane | 0.325405 | 0.325185 | 0.000219778 |
