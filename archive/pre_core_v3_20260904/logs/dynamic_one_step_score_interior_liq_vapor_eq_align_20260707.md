# Dynamic One-Step Initialization Score

Summary: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_interior_liq_vapor_eq_align_rhs_terms_20260707\column_summary_20260707_153257.csv`
Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_interior_liq_vapor_eq_align_rhs_terms_20260707\column_profile_20260707_153257.csv`
Objective: `27.2837`

## Terms
| metric | value | ref | weight | term |
|---|---|---|---|---|
| dynamic_score | 26.0816 | 1 | 1 | 26.0816 |
| rel_rate_per_s | 0.0782449 | 0.01 | 1 | 7.82449 |
| temp_rate_F_per_s | 0.0833453 | 0.1 | 0.5 | 0.416727 |
| vapor_rhs_lbmolps | 0.161902 | 0.1 | 1 | 1.61902 |
| coverage_error | 0.629222 | 1 | 0.5 | 0.314611 |
| overcoverage | 0 | 1 | 0.5 | 0 |
| y_drift | 0.00348109 | 0.01 | 0.5 | 0.174055 |

## Coverage
| median_abs_cancellation_coverage_error | max_cancellation_overcoverage | max_cancellation_undercoverage | median_cancellation_coverage |
|---|---|---|---|
| 0.629222 | 0 | 5.13267 | 0.370778 |

## Top Vapor Conflicts
| stage_1based | stage_kind | component | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | equilibrium_transfer_lbmolps | cancellation_coverage | required_target_delta |
|---|---|---|---|---|---|---|---|
| 2 | interior | n_Propane | 0.161902 | 0.0767185 | 0.0851839 | -1.11034 | -0.00195668 |
| 3 | interior | n_Propane | -0.159965 | -0.242647 | 0.0826817 | 0.340749 | 0.00674483 |
| 4 | interior | n_Propane | -0.147161 | -0.22307 | 0.0759095 | 0.340294 | 0.00631132 |
| 3 | interior | n_Butane | 0.120286 | 0.202942 | -0.0826568 | 0.407292 | -0.00507175 |
| 2 | interior | n_Butane | -0.108519 | -0.0232203 | -0.0852984 | -3.67344 | 0.00131151 |
| 5 | interior | n_Propane | -0.108324 | -0.167681 | 0.059357 | 0.353988 | 0.00470158 |
| 4 | interior | n_Butane | 0.10355 | 0.179402 | -0.0758519 | 0.422805 | -0.00444096 |
| 19 | interior | n_Propane | -0.0865203 | -0.135882 | 0.049362 | 0.36327 | 0.00341772 |
| 5 | interior | n_Butane | 0.0782924 | 0.137523 | -0.0592302 | 0.430694 | -0.00339812 |
| 6 | interior | n_Propane | -0.0734991 | -0.115586 | 0.0420871 | 0.364119 | 0.00321373 |
| 16 | interior | n_Propane | -0.069553 | -0.125524 | 0.0559711 | 0.445899 | 0.00272322 |
| 17 | interior | n_Propane | -0.0655761 | -0.120452 | 0.054876 | 0.455584 | 0.00257501 |

## Top Vapor Composition Drift
| stage_1based | component | y_initial | y_final | abs_y_drift |
|---|---|---|---|---|
| 3 | n_Propane | 0.864256 | 0.860775 | 0.00348109 |
| 3 | n_Butane | 0.135723 | 0.1392 | 0.00347783 |
| 4 | n_Propane | 0.775778 | 0.772545 | 0.00323264 |
| 4 | n_Butane | 0.224141 | 0.227365 | 0.00322391 |
| 5 | n_Propane | 0.693476 | 0.690932 | 0.00254399 |
| 5 | n_Butane | 0.306285 | 0.308809 | 0.0025246 |
| 19 | n_Propane | 0.172386 | 0.170058 | 0.00232795 |
| 15 | n_Propane | 0.382402 | 0.380586 | 0.00181624 |
| 6 | n_Propane | 0.628584 | 0.6268 | 0.00178399 |
| 6 | n_Butane | 0.370826 | 0.372571 | 0.00174564 |
| 17 | n_Propane | 0.27334 | 0.271605 | 0.0017347 |
| 16 | n_Propane | 0.32924 | 0.327523 | 0.00171731 |
