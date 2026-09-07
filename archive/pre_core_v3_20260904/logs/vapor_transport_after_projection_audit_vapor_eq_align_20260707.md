# Vapor Transport After Projection Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_vapor_eq_align_smoke_20260707\column_profile_20260707_105625.csv`
Window: `0` to `0.2` s

## Summary
| n_stages | max_abs_y_gap_final | max_abs_y_gap_final_interior | max_abs_ln_K_state_over_K_eq | max_abs_ln_x_over_x_eq | max_abs_ln_y_over_y_eq | max_abs_dy_dt_per_s |
|---|---|---|---|---|---|---|
| 20 | 0.0537173 | 0.00349631 | 0.587764 | 1.19567 | 1.71243 | 0.297915 |

## Interpretation
- If `max_abs_y_gap_final_interior` is small while `max_abs_ln_K_state_over_K_eq` is large, the remaining K mismatch is not mainly vapor composition drift; inspect liquid composition, K basis, or material transport.
- Interior vapor composition remains close to the live target after the first step.

## Top K-State Stages
| stage_1based | max_abs_ln_K_state_over_K_eq | max_abs_y_gap_final | max_abs_dy_dt_per_s | V_in_minus_out_lbmolph_est | eq_phase_change_lbmolps | dominant_ln_K_component | dominant_ln_K_state_over_K_eq | dominant_ln_x_component | dominant_ln_x_over_x_eq |
|---|---|---|---|---|---|---|---|---|---|
| 19 | 0.587764 | 0.000467921 | 0.0259249 | -47.0052 | 2.22045e-16 | n_Propane | -0.587764 | n_Propane | 0.58561 |
| 18 | 0.338936 | 0.00178099 | 0.0814742 | -8.24954 | -2.66454e-15 | n_Propane | -0.338936 | n_Propane | 0.330789 |
| 4 | 0.312907 | 0.00326777 | 0.239082 | -144.711 | -7.76289e-17 | n_Pentane | 0.312907 | n_Pentane | -0.305251 |
| 5 | 0.297727 | 0.00261282 | 0.170537 | -87.9069 | -1.06252e-15 | n_Pentane | 0.297727 | n_Pentane | -0.291625 |
| 2 | 0.278677 | 0.00227821 | 0.047541 | 64.243 | 2.07462e-14 | n_Pentane | -0.278677 | n_Pentane | 0.135186 |
| 6 | 0.24815 | 0.00186395 | 0.110318 | -49.4944 | -1.28196e-15 | n_Pentane | 0.24815 | n_Pentane | -0.237355 |
| 3 | 0.24381 | 0.00349631 | 0.291044 | -154.371 | -1.06382e-15 | n_Pentane | 0.24381 | n_Pentane | -0.222126 |
| 7 | 0.189368 | 0.00126887 | 0.0675597 | -28.9685 | -7.63278e-17 | n_Pentane | 0.189368 | n_Pentane | -0.17065 |
| 17 | 0.169719 | 0.00225538 | 0.119817 | -1.1014 | -1.77636e-15 | n_Propane | -0.169719 | n_Propane | 0.161464 |
| 8 | 0.131997 | 0.000829849 | 0.0415268 | -20.7331 | 1.65146e-15 | n_Pentane | 0.131997 | n_Pentane | -0.104762 |

## Top Component K Mismatches
| stage_1based | component | ln_K_state_over_K_eq_relax | ln_x_over_x_eq | ln_y_over_y_eq | y_gap_final | dy_dt_per_s | estimated_convective_pull_y_in_minus_y |
|---|---|---|---|---|---|---|---|
| 19 | n_Propane | -0.587764 | 0.58561 | -0.00215392 | -0.000369743 | 0.0154865 | -0.0136561 |
| 19 | n_Pentane | 0.529229 | -0.522911 | 0.00631848 | 0.000467921 | -0.0259249 | 0.0112783 |
| 18 | n_Propane | -0.338936 | 0.330789 | -0.00814712 | -0.00178099 | 0.0814742 | -0.0462385 |
| 4 | n_Pentane | 0.312907 | -0.305251 | 0.007656 | 7.507e-07 | 0.000119921 | 0.000178901 |
| 5 | n_Pentane | 0.297727 | -0.291625 | 0.00610213 | 1.68715e-06 | 0.000377789 | 0.000383811 |
| 2 | n_Pentane | -0.278677 | 0.135186 | -0.143491 | -2.95846e-06 | 5.98647e-05 | 8.07387e-06 |
| 18 | n_Pentane | 0.2629 | -0.252932 | 0.00996802 | 0.000569385 | -0.0451635 | 0.016884 |
| 6 | n_Pentane | 0.24815 | -0.237355 | 0.0107952 | 7.09878e-06 | 0.000825854 | 0.000764146 |
| 3 | n_Pentane | 0.24381 | -0.222126 | 0.0216837 | 5.84471e-07 | 1.62118e-05 | 7.11819e-05 |
| 7 | n_Pentane | 0.189368 | -0.17065 | 0.0187186 | 2.64313e-05 | 0.00136003 | 0.00148299 |

## Top Interior Component K Mismatches
| stage_1based | component | ln_K_state_over_K_eq_relax | ln_x_over_x_eq | ln_y_over_y_eq | y_gap_final | dy_dt_per_s | estimated_convective_pull_y_in_minus_y |
|---|---|---|---|---|---|---|---|
| 19 | n_Propane | -0.587764 | 0.58561 | -0.00215392 | -0.000369743 | 0.0154865 | -0.0136561 |
| 19 | n_Pentane | 0.529229 | -0.522911 | 0.00631848 | 0.000467921 | -0.0259249 | 0.0112783 |
| 18 | n_Propane | -0.338936 | 0.330789 | -0.00814712 | -0.00178099 | 0.0814742 | -0.0462385 |
| 4 | n_Pentane | 0.312907 | -0.305251 | 0.007656 | 7.507e-07 | 0.000119921 | 0.000178901 |
| 5 | n_Pentane | 0.297727 | -0.291625 | 0.00610213 | 1.68715e-06 | 0.000377789 | 0.000383811 |
| 2 | n_Pentane | -0.278677 | 0.135186 | -0.143491 | -2.95846e-06 | 5.98647e-05 | 8.07387e-06 |
| 18 | n_Pentane | 0.2629 | -0.252932 | 0.00996802 | 0.000569385 | -0.0451635 | 0.016884 |
| 6 | n_Pentane | 0.24815 | -0.237355 | 0.0107952 | 7.09878e-06 | 0.000825854 | 0.000764146 |
| 3 | n_Pentane | 0.24381 | -0.222126 | 0.0216837 | 5.84471e-07 | 1.62118e-05 | 7.11819e-05 |
| 7 | n_Pentane | 0.189368 | -0.17065 | 0.0187186 | 2.64313e-05 | 0.00136003 | 0.00148299 |

## Top Vapor Composition Interfaces
| vapor_source_stage_1based | vapor_receiver_stage_1based | V_source_lbmolph | max_abs_y_source_minus_receiver | dominant_component | dominant_y_source_minus_receiver |
|---|---|---|---|---|---|
| 2 | 1 | 8543.03 | 0.519223 | n_Propane | 0.519223 |
| 4 | 3 | 8452.9 | 0.0882176 | n_Propane | -0.0882176 |
| 5 | 4 | 8308.19 | 0.0815901 | n_Propane | -0.0815901 |
| 6 | 5 | 8220.28 | 0.064101 | n_Propane | -0.064101 |
| 17 | 16 | 8086.38 | 0.056146 | n_Propane | -0.056146 |
| 18 | 17 | 8085.28 | 0.0543877 | n_Propane | -0.0543877 |
| 16 | 15 | 8027.72 | 0.0532482 | n_Propane | -0.0532482 |
| 15 | 14 | 7970.86 | 0.0474597 | n_Propane | -0.0474597 |
| 19 | 18 | 8077.03 | 0.0462385 | n_Propane | -0.0462385 |
| 7 | 6 | 8170.79 | 0.0451285 | n_Propane | -0.0451285 |
