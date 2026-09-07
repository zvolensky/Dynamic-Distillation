# Dynamic One-Step Initialization Score

Summary: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_vapor_material_reconciled_trial1_smoke_20260707\column_summary_20260707_154658.csv`
Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_vapor_material_reconciled_trial1_smoke_20260707\column_profile_20260707_154658.csv`
Objective: `59.7687`

## Terms
| metric | value | ref | weight | term |
|---|---|---|---|---|
| dynamic_score | 56.3592 | 1 | 1 | 56.3592 |
| rel_rate_per_s | 0.169078 | 0.01 | 1 | 16.9078 |
| temp_rate_F_per_s | 0 | 0.1 | 0.5 | 0 |
| vapor_rhs_lbmolps | 0.324984 | 0.1 | 1 | 3.24984 |
| coverage_error | 2.41035 | 1 | 0.5 | 1.20518 |
| overcoverage | 19.7812 | 1 | 0.5 | 9.89061 |
| y_drift | 0.00940514 | 0.01 | 0.5 | 0.470257 |

## Coverage
| median_abs_cancellation_coverage_error | max_cancellation_overcoverage | max_cancellation_undercoverage | median_cancellation_coverage |
|---|---|---|---|
| 2.41035 | 19.7812 | 8.57308 | 3.25876 |

## Top Vapor Conflicts
| stage_1based | stage_kind | component | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | equilibrium_transfer_lbmolps | cancellation_coverage | required_target_delta |
|---|---|---|---|---|---|---|---|
| 7 | interior | n_Butane | -0.324984 | 0.0587067 | -0.383691 | 6.53573 | 0.0142694 |
| 6 | interior | n_Butane | -0.3238 | 0.0939048 | -0.417705 | 4.44817 | 0.0141577 |
| 8 | interior | n_Butane | -0.319698 | 0.0323023 | -0.352 | 10.8971 | 0.014071 |
| 7 | interior | n_Propane | 0.315673 | -0.0724752 | 0.388149 | 5.35561 | -0.0138606 |
| 5 | interior | n_Butane | -0.315449 | 0.136665 | -0.452114 | 3.30819 | 0.0136908 |
| 8 | interior | n_Propane | 0.313045 | -0.0485604 | 0.361605 | 7.44651 | -0.0137782 |
| 6 | interior | n_Propane | 0.310143 | -0.109324 | 0.419467 | 3.83692 | -0.0135605 |
| 9 | interior | n_Butane | -0.307853 | 0.0167609 | -0.324614 | 19.3673 | 0.0135729 |
| 9 | interior | n_Propane | 0.303653 | -0.0377164 | 0.34137 | 9.05097 | -0.0133878 |
| 4 | interior | n_Butane | -0.298311 | 0.179111 | -0.477423 | 2.66551 | 0.012793 |
| 5 | interior | n_Propane | 0.293804 | -0.15902 | 0.452823 | 2.84759 | -0.0127514 |
| 10 | interior | n_Butane | -0.2908 | 0.0147008 | -0.305501 | 20.7812 | 0.0128427 |

## Top Vapor Composition Drift
| stage_1based | component | y_initial | y_final | abs_y_drift |
|---|---|---|---|---|
| 7 | n_Propane | 0.579966 | 0.589371 | 0.00940514 |
| 7 | n_Butane | 0.418618 | 0.409237 | 0.00938076 |
| 8 | n_Propane | 0.550824 | 0.560173 | 0.00934942 |
| 6 | n_Butane | 0.375209 | 0.365939 | 0.00927051 |
| 6 | n_Propane | 0.62418 | 0.633448 | 0.00926862 |
| 8 | n_Butane | 0.446155 | 0.436898 | 0.00925711 |
| 9 | n_Propane | 0.532119 | 0.541244 | 0.00912529 |
| 9 | n_Butane | 0.462 | 0.453083 | 0.0089167 |
| 5 | n_Butane | 0.312577 | 0.303675 | 0.00890238 |
| 5 | n_Propane | 0.68718 | 0.696079 | 0.00889849 |
| 10 | n_Propane | 0.518619 | 0.527379 | 0.00875941 |
| 11 | n_Propane | 0.503928 | 0.512437 | 0.00850909 |
