# Vapor Transport After Projection Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_vapor_material_reconciled_trial1_smoke_20260707\column_profile_20260707_154658.csv`
Window: `0` to `0.2` s

## Summary
| n_stages | max_abs_y_gap_final | max_abs_y_gap_final_interior | max_abs_ln_K_state_over_K_eq | max_abs_ln_x_over_x_eq | max_abs_ln_y_over_y_eq | max_abs_dy_dt_per_s |
|---|---|---|---|---|---|---|
| 20 | 0.519464 | 0.0204868 | 0.188343 | 0.115754 | 10.2549 | 0.0471201 |

## Interpretation
- If `max_abs_y_gap_final_interior` is small while `max_abs_ln_K_state_over_K_eq` is large, the remaining K mismatch is not mainly vapor composition drift; inspect liquid composition, K basis, or material transport.

## Top K-State Stages
| stage_1based | max_abs_ln_K_state_over_K_eq | max_abs_y_gap_final | max_abs_dy_dt_per_s | V_in_minus_out_lbmolph_est | eq_phase_change_lbmolps | dominant_ln_K_component | dominant_ln_K_state_over_K_eq | dominant_ln_x_component | dominant_ln_x_over_x_eq |
|---|---|---|---|---|---|---|---|---|---|
| 3 | 0.188343 | 0.0201438 | 0.0378508 | -81.454 | 1.69829e-15 | n_Pentane | 0.188343 | n_Pentane | 0.0613186 |
| 11 | 0.155439 | 0.0132392 | 0.0425454 | -38.924 | 2.83107e-15 | n_Pentane | 0.155439 | n_Propane | -0.00940882 |
| 8 | 0.144079 | 0.0159155 | 0.0467471 | -25.2691 | -9.64506e-16 | n_Pentane | 0.144079 | n_Pentane | 0.0118166 |
| 7 | 0.136679 | 0.0170428 | 0.0470257 | -34.4832 | 2.0782e-15 | n_Pentane | 0.136679 | n_Pentane | 0.0148906 |
| 4 | 0.133608 | 0.0204868 | 0.0414585 | -144.58 | 3.50609e-15 | n_Pentane | 0.133608 | n_Pentane | 0.0299886 |
| 9 | 0.127527 | 0.0150506 | 0.0456264 | -24.1871 | 2.59515e-15 | n_Pentane | 0.127527 | n_Pentane | 0.0119948 |
| 6 | 0.114258 | 0.0183405 | 0.0463526 | -56.68 | -1.95503e-15 | n_Pentane | 0.114258 | n_Pentane | 0.0201601 |
| 5 | 0.10879 | 0.019653 | 0.0445119 | -97.8622 | 7.2338e-16 | n_Pentane | 0.10879 | n_Pentane | 0.0248292 |
| 10 | 0.108088 | 0.0146056 | 0.0437971 | -26.741 | -5.55112e-16 | n_Pentane | 0.108088 | n_Pentane | 0.012998 |
| 2 | 0.106898 | 0.000288739 | 0.000766413 | -0.212143 | -7.89646e-15 | n_Pentane | -0.106898 | n_Pentane | 0.0541538 |

## Top Component K Mismatches
| stage_1based | component | ln_K_state_over_K_eq_relax | ln_x_over_x_eq | ln_y_over_y_eq | y_gap_final | dy_dt_per_s | estimated_convective_pull_y_in_minus_y |
|---|---|---|---|---|---|---|---|
| 3 | n_Pentane | 0.188343 | 0.0613186 | 0.249662 | 4.92787e-06 | 3.8293e-06 | 6.20641e-05 |
| 11 | n_Pentane | 0.155439 | 0.00447808 | 0.159917 | 0.0022525 | -0.0023716 | 0.0153775 |
| 8 | n_Pentane | 0.144079 | 0.0118166 | 0.155895 | 0.000422759 | -0.000461562 | 0.00274405 |
| 7 | n_Pentane | 0.136679 | 0.0148906 | 0.15157 | 0.000195725 | -0.000121869 | 0.00153703 |
| 3 | n_Butane | 0.135087 | 0.0241146 | 0.159202 | 0.0201389 | -0.0378508 | 0.087001 |
| 4 | n_Pentane | 0.133608 | 0.0299886 | 0.163597 | 1.27325e-05 | 1.04823e-05 | 0.000161679 |
| 9 | n_Pentane | 0.127527 | 0.0119948 | 0.139522 | 0.000738739 | -0.00104291 | 0.00409299 |
| 6 | n_Pentane | 0.114258 | 0.0201601 | 0.134418 | 7.70477e-05 | 9.48798e-06 | 0.000779072 |
| 5 | n_Pentane | 0.10879 | 0.0248292 | 0.13362 | 3.07749e-05 | 1.94342e-05 | 0.000366535 |
| 10 | n_Pentane | 0.108088 | 0.012998 | 0.121086 | 0.00111371 | -0.00183328 | 0.00547596 |

## Top Interior Component K Mismatches
| stage_1based | component | ln_K_state_over_K_eq_relax | ln_x_over_x_eq | ln_y_over_y_eq | y_gap_final | dy_dt_per_s | estimated_convective_pull_y_in_minus_y |
|---|---|---|---|---|---|---|---|
| 3 | n_Pentane | 0.188343 | 0.0613186 | 0.249662 | 4.92787e-06 | 3.8293e-06 | 6.20641e-05 |
| 11 | n_Pentane | 0.155439 | 0.00447808 | 0.159917 | 0.0022525 | -0.0023716 | 0.0153775 |
| 8 | n_Pentane | 0.144079 | 0.0118166 | 0.155895 | 0.000422759 | -0.000461562 | 0.00274405 |
| 7 | n_Pentane | 0.136679 | 0.0148906 | 0.15157 | 0.000195725 | -0.000121869 | 0.00153703 |
| 3 | n_Butane | 0.135087 | 0.0241146 | 0.159202 | 0.0201389 | -0.0378508 | 0.087001 |
| 4 | n_Pentane | 0.133608 | 0.0299886 | 0.163597 | 1.27325e-05 | 1.04823e-05 | 0.000161679 |
| 9 | n_Pentane | 0.127527 | 0.0119948 | 0.139522 | 0.000738739 | -0.00104291 | 0.00409299 |
| 6 | n_Pentane | 0.114258 | 0.0201601 | 0.134418 | 7.70477e-05 | 9.48798e-06 | 0.000779072 |
| 5 | n_Pentane | 0.10879 | 0.0248292 | 0.13362 | 3.07749e-05 | 1.94342e-05 | 0.000366535 |
| 10 | n_Pentane | 0.108088 | 0.012998 | 0.121086 | 0.00111371 | -0.00183328 | 0.00547596 |

## Top Vapor Composition Interfaces
| vapor_source_stage_1based | vapor_receiver_stage_1based | V_source_lbmolph | max_abs_y_source_minus_receiver | dominant_component | dominant_y_source_minus_receiver |
|---|---|---|---|---|---|
| 2 | 1 | 8603.67 | 0.51931 | n_Propane | 0.51931 |
| 4 | 3 | 8522 | 0.087063 | n_Propane | -0.087063 |
| 5 | 4 | 8377.42 | 0.0800001 | n_Propane | -0.0800001 |
| 6 | 5 | 8279.56 | 0.0626304 | n_Propane | -0.0626304 |
| 17 | 16 | 8113.76 | 0.0561726 | n_Propane | -0.0561726 |
| 20 | 19 | 8030.03 | 0.0545877 | n_Propane | -0.0545877 |
| 18 | 17 | 8099.89 | 0.0543705 | n_Propane | -0.0543705 |
| 16 | 15 | 8128.78 | 0.0530381 | n_Propane | -0.0530381 |
| 19 | 18 | 8076.84 | 0.0486637 | n_Propane | -0.0486637 |
| 15 | 14 | 8149.22 | 0.0477619 | n_Propane | -0.0477619 |
