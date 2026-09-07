# Dynamic One-Step Initialization Score

Summary: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_liq_eq_vap_eq_blend075_rhs_terms_20260707\column_summary_20260707_160811.csv`
Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_liq_eq_vap_eq_blend075_rhs_terms_20260707\column_profile_20260707_160811.csv`
Objective: `27.2799`

## Terms
| metric | value | ref | weight | term |
|---|---|---|---|---|
| dynamic_score | 26.0764 | 1 | 1 | 26.0764 |
| rel_rate_per_s | 0.0782293 | 0.01 | 1 | 7.82293 |
| temp_rate_F_per_s | 0.108416 | 0.1 | 0.5 | 0.542079 |
| vapor_rhs_lbmolps | 0.161159 | 0.1 | 1 | 1.61159 |
| coverage_error | 0.615196 | 1 | 0.5 | 0.307598 |
| overcoverage | 0 | 1 | 0.5 | 0 |
| y_drift | 0.00348299 | 0.01 | 0.5 | 0.174149 |

## Coverage
| median_abs_cancellation_coverage_error | max_cancellation_overcoverage | max_cancellation_undercoverage | median_cancellation_coverage |
|---|---|---|---|
| 0.615196 | 0 | 0.904186 | 0.384804 |

## Top Vapor Conflicts
| stage_1based | stage_kind | component | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | equilibrium_transfer_lbmolps | cancellation_coverage | required_target_delta |
|---|---|---|---|---|---|---|---|
| 3 | interior | n_Propane | -0.161159 | -0.243762 | 0.0826029 | 0.338868 | 0.00679531 |
| 4 | interior | n_Propane | -0.147224 | -0.222924 | 0.0756999 | 0.339577 | 0.00631405 |
| 3 | interior | n_Butane | 0.120191 | 0.202733 | -0.0825425 | 0.407148 | -0.00506789 |
| 5 | interior | n_Propane | -0.108619 | -0.167537 | 0.0589179 | 0.351671 | 0.0047144 |
| 4 | interior | n_Butane | 0.103845 | 0.179392 | -0.0755476 | 0.42113 | -0.00445361 |
| 19 | interior | n_Propane | -0.0827556 | -0.135505 | 0.0527492 | 0.389279 | 0.00326901 |
| 16 | interior | n_Propane | -0.079104 | -0.12579 | 0.0466855 | 0.37114 | 0.00309718 |
| 5 | interior | n_Butane | 0.0789213 | 0.137509 | -0.0585881 | 0.426066 | -0.00342541 |
| 15 | interior | n_Propane | -0.0752344 | -0.121608 | 0.0463735 | 0.381336 | 0.00337122 |
| 6 | interior | n_Propane | -0.0741248 | -0.115455 | 0.0413299 | 0.357975 | 0.00324109 |
| 17 | interior | n_Propane | -0.0722637 | -0.120969 | 0.0487049 | 0.402625 | 0.00283761 |
| 16 | interior | n_Butane | 0.0710178 | 0.113278 | -0.0422601 | 0.373066 | -0.00278058 |

## Top Vapor Composition Drift
| stage_1based | component | y_initial | y_final | abs_y_drift |
|---|---|---|---|---|
| 3 | n_Propane | 0.864262 | 0.860779 | 0.00348299 |
| 3 | n_Butane | 0.135715 | 0.139195 | 0.00348044 |
| 4 | n_Propane | 0.775793 | 0.772555 | 0.00323764 |
| 4 | n_Butane | 0.224119 | 0.22735 | 0.00323108 |
| 5 | n_Propane | 0.693509 | 0.690954 | 0.00255517 |
| 5 | n_Butane | 0.306236 | 0.308777 | 0.00254085 |
| 19 | n_Propane | 0.172101 | 0.169879 | 0.0022228 |
| 15 | n_Propane | 0.383274 | 0.381142 | 0.00213234 |
| 15 | n_Butane | 0.578129 | 0.580107 | 0.00197803 |
| 16 | n_Propane | 0.32994 | 0.327967 | 0.00197222 |
| 17 | n_Propane | 0.273823 | 0.271905 | 0.00191801 |
| 14 | n_Propane | 0.430487 | 0.428605 | 0.0018822 |
