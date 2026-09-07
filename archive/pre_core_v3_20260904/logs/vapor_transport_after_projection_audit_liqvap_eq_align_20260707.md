# Vapor Transport After Projection Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_liqvap_eq_align_smoke_20260707\column_profile_20260707_110130.csv`
Window: `0` to `0.2` s

## Summary
| n_stages | max_abs_y_gap_final | max_abs_y_gap_final_interior | max_abs_ln_K_state_over_K_eq | max_abs_ln_x_over_x_eq | max_abs_ln_y_over_y_eq | max_abs_dy_dt_per_s |
|---|---|---|---|---|---|---|
| 20 | 0.0537173 | 0.00348621 | 0.71384 | 0.868949 | 1.71243 | 0.291039 |

## Interpretation
- If `max_abs_y_gap_final_interior` is small while `max_abs_ln_K_state_over_K_eq` is large, the remaining K mismatch is not mainly vapor composition drift; inspect liquid composition, K basis, or material transport.
- Interior vapor composition remains close to the live target after the first step.

## Top K-State Stages
| stage_1based | max_abs_ln_K_state_over_K_eq | max_abs_y_gap_final | max_abs_dy_dt_per_s | V_in_minus_out_lbmolph_est | eq_phase_change_lbmolps | dominant_ln_K_component | dominant_ln_K_state_over_K_eq | dominant_ln_x_component | dominant_ln_x_over_x_eq |
|---|---|---|---|---|---|---|---|---|---|
| 20 | 0.71384 | 0.0269866 | 0.111543 | 0 | 0 | n_Propane | 0.71384 | n_Pentane | 0.868949 |
| 2 | 0.200228 | 0.00103088 | 0.0234102 | 40.0316 | 9.86841e-16 | n_Pentane | -0.200228 | n_Pentane | 0.0990868 |
| 11 | 0.0708633 | 0.00128891 | 0.0443658 | -37.0077 | -3.66374e-15 | n_Pentane | 0.0708633 | n_Pentane | -0.00941031 |
| 3 | 0.0469636 | 0.00348621 | 0.291039 | -141.713 | 4.27653e-15 | n_Pentane | 0.0469636 | n_Butane | -0.0040746 |
| 9 | 0.0388827 | 0.000469378 | 0.0323846 | -22.1855 | -5.70377e-15 | n_Pentane | 0.0388827 | n_Pentane | -0.00440763 |
| 10 | 0.0362597 | 0.000353924 | 0.0402626 | -24.9717 | -5.19029e-15 | n_Pentane | 0.0362597 | n_Pentane | -0.00428951 |
| 8 | 0.0346597 | 0.000800869 | 0.0409231 | -22.2928 | -4.38538e-15 | n_Pentane | 0.0346597 | n_Pentane | -0.00368805 |
| 4 | 0.0304301 | 0.00325554 | 0.238986 | -146.597 | 2.69012e-15 | n_Pentane | 0.0304301 | n_Butane | -0.00293925 |
| 7 | 0.0281935 | 0.00124199 | 0.0668624 | -30.2895 | 4.24313e-15 | n_Pentane | 0.0281935 | n_Pentane | -0.00282263 |
| 5 | 0.0236352 | 0.00257627 | 0.170275 | -89.2185 | -1.63498e-15 | n_Pentane | 0.0236352 | n_Pentane | -0.00214674 |

## Top Component K Mismatches
| stage_1based | component | ln_K_state_over_K_eq_relax | ln_x_over_x_eq | ln_y_over_y_eq | y_gap_final | dy_dt_per_s | estimated_convective_pull_y_in_minus_y |
|---|---|---|---|---|---|---|---|
| 20 | n_Propane | 0.71384 | -0.724269 | -0.0104288 | -0.00114352 | 0.0542127 | 0 |
| 20 | n_Pentane | -0.5904 | 0.868949 | 0.278549 | 0.0269866 | 0.0573302 | 0 |
| 2 | n_Pentane | -0.200228 | 0.0990868 | -0.101142 | -1.38433e-06 | 2.90282e-05 | 1.12415e-05 |
| 11 | n_Pentane | 0.0708633 | -0.00941031 | 0.061453 | 0.000893234 | -0.0260964 | 0.0163127 |
| 3 | n_Pentane | 0.0469636 | -0.00276801 | 0.0441955 | 1.04832e-06 | 1.21321e-06 | 6.56837e-05 |
| 20 | n_Butane | 0.0441277 | -0.0767262 | -0.0325985 | -0.0258431 | -0.111543 | 0 |
| 9 | n_Pentane | 0.0388827 | -0.00440763 | 0.034475 | 0.000191533 | -0.00275907 | 0.00422111 |
| 10 | n_Pentane | 0.0362597 | -0.00428951 | 0.0319702 | 0.000310654 | -0.0120997 | 0.00511329 |
| 8 | n_Pentane | 0.0346597 | -0.00368805 | 0.0309716 | 8.74748e-05 | 0.0010127 | 0.00278371 |
| 4 | n_Pentane | 0.0304301 | -0.00261212 | 0.027818 | 2.46724e-06 | 7.74318e-05 | 0.000168817 |

## Top Interior Component K Mismatches
| stage_1based | component | ln_K_state_over_K_eq_relax | ln_x_over_x_eq | ln_y_over_y_eq | y_gap_final | dy_dt_per_s | estimated_convective_pull_y_in_minus_y |
|---|---|---|---|---|---|---|---|
| 2 | n_Pentane | -0.200228 | 0.0990868 | -0.101142 | -1.38433e-06 | 2.90282e-05 | 1.12415e-05 |
| 11 | n_Pentane | 0.0708633 | -0.00941031 | 0.061453 | 0.000893234 | -0.0260964 | 0.0163127 |
| 3 | n_Pentane | 0.0469636 | -0.00276801 | 0.0441955 | 1.04832e-06 | 1.21321e-06 | 6.56837e-05 |
| 9 | n_Pentane | 0.0388827 | -0.00440763 | 0.034475 | 0.000191533 | -0.00275907 | 0.00422111 |
| 10 | n_Pentane | 0.0362597 | -0.00428951 | 0.0319702 | 0.000310654 | -0.0120997 | 0.00511329 |
| 8 | n_Pentane | 0.0346597 | -0.00368805 | 0.0309716 | 8.74748e-05 | 0.0010127 | 0.00278371 |
| 4 | n_Pentane | 0.0304301 | -0.00261212 | 0.027818 | 2.46724e-06 | 7.74318e-05 | 0.000168817 |
| 3 | n_Butane | 0.0294304 | -0.0040746 | 0.0253558 | 0.00348516 | -0.291039 | 0.0881648 |
| 7 | n_Pentane | 0.0281935 | -0.00282263 | 0.0253709 | 3.45528e-05 | 0.00112988 | 0.00148906 |
| 5 | n_Pentane | 0.0236352 | -0.00214674 | 0.0214885 | 5.50081e-06 | 0.000284881 | 0.000369814 |

## Top Vapor Composition Interfaces
| vapor_source_stage_1based | vapor_receiver_stage_1based | V_source_lbmolph | max_abs_y_source_minus_receiver | dominant_component | dominant_y_source_minus_receiver |
|---|---|---|---|---|---|
| 2 | 1 | 8613.15 | 0.514403 | n_Propane | 0.514403 |
| 4 | 3 | 8511.47 | 0.0882305 | n_Propane | -0.0882305 |
| 5 | 4 | 8364.87 | 0.0816131 | n_Propane | -0.0816131 |
| 6 | 5 | 8275.65 | 0.0641318 | n_Propane | -0.0641318 |
| 20 | 19 | 8030.03 | 0.0609782 | n_Propane | -0.0609782 |
| 17 | 16 | 8079.08 | 0.0559175 | n_Propane | -0.0559175 |
| 18 | 17 | 8069.84 | 0.05397 | n_Propane | -0.05397 |
| 16 | 15 | 8088.59 | 0.0530631 | n_Propane | -0.0530631 |
| 19 | 18 | 8050.71 | 0.0475774 | n_Propane | -0.0475774 |
| 15 | 14 | 8103.81 | 0.0474674 | n_Propane | -0.0474674 |
