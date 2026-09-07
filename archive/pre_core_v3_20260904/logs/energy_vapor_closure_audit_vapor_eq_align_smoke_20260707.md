# Energy/Vapor Closure Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_vapor_eq_align_smoke_20260707\column_profile_20260707_105625.csv`
Time: `0.2 s`
Stage rows: `20`

## Summary

| Check | Value |
|---|---:|
| max \|V_calc - V_used\| lbmol/h | 0 |
| max \|relative V gap\| | 0 |
| max \|adjacent vapor enthalpy gap\| BTU/lbmol | 105.782 |
| max \|P_from_holdup - P\| psia | 222.62 |
| max \|energy P used - logged P\| psia | 0.00784263 |
| max \|ln(K_state/K_thermo)\| | 0.587764 |
| max \|ln(K_state/K_eq_relax)\| | 0.587764 |
| max \|y_state - y_eq\| | 0.905668 |
| max \|y_state - y_target\| | 0.905668 |
| max \|y_state - y_target\| interior | 0.00349631 |
| max \|dT_energy_raw\| F/s | 1.43795e-07 |
| max \|energy residual / heat capacity\| F/s | 1.5587 |
| max \|dT raw - vapor-flow predicted dT\| F/s | 1.43795e-07 |
| max \|temp dE - vapor-flow residual\| BTU/s | 0.000165458 |

## Diagnostic Interpretation

- equilibrium K-state mismatch

This report uses logged RHS diagnostics only. It does not recompute thermo or change vapor-flow closure.

## Top Composite Interfaces

| vapor_source_stage_1based | vapor_receiver_stage_1based | interface_inconsistency_score | V_calc_minus_used_lbmolph | relative_V_calc_minus_used | vflow_energy_P_used_minus_source_P_psia | vflow_energy_pressure_basis_code | source_minus_receiver_HV_BTU_per_lbmol | vflow_energy_hV_in_source_code | vflow_energy_hV_out_source_code | source_dT_energy_raw_F_per_s | receiver_dT_energy_raw_F_per_s |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | nan | 22.262 | nan | nan | nan | nan | nan | nan | nan | 0 | nan |
| 19 | 18 | 0.367663 | 0 | 0 | -0.00053929 | 1 | 6.15429 | 2 | 2 | 0 | 1.21378e-15 |
| 18 | 17 | 0.348525 | 0 | 0 | -0.00138486 | 1 | 3.62693 | 2 | 2 | 1.21378e-15 | -1.19596e-15 |
| 20 | 19 | 0.321837 | nan | nan | nan | nan | -12.9021 | nan | nan | 0 | 0 |
| 17 | 16 | 0.321316 | 0 | 0 | -0.00238002 | 1 | 3.60778 | 2 | 2 | -1.19596e-15 | 0 |
| 16 | 15 | 0.280906 | 0 | 0 | -0.00356349 | 1 | 4.27334 | 2 | 2 | 0 | 1.5006e-15 |
| 3 | 2 | 0.262593 | 0 | 0 | -0.00128634 | 1 | 105.782 | 2 | 2 | 0 | -1.43795e-07 |
| 2 | 1 | 0.260657 | 0 | 0 | -0.000550296 | 1 | 41.9608 | 2 | 2 | -1.43795e-07 | 0 |

## Worst Temperature Rates

| stage_1based | dT_energy_raw_F_per_s | vflow_energy_predicted_dT_from_used_F_per_s | dT_raw_minus_vflow_predicted_F_per_s | stage_energy_balance_resid_BTUps | stage_energy_resid_over_heat_capacity_F_per_s | dominant_energy_term | dominant_energy_term_BTUps |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 | -1.43795e-07 | 0 | -1.43795e-07 | 3076.41 | 1.5587 | vflow_energy_V_in_term_BTUps | 14038.2 |
| 8 | 2.42574e-15 | 1.5662e-15 | 8.5954e-16 | 68.6575 | 0.0591162 | vflow_energy_numer_BTUps | 14369.5 |
| 7 | 2.41629e-15 | 1.55339e-15 | 8.62899e-16 | 147.935 | 0.126335 | vflow_energy_numer_BTUps | 14367.7 |
| 5 | 2.38033e-15 | 1.50833e-15 | 8.71998e-16 | 309.042 | 0.256262 | vflow_energy_numer_BTUps | 14390.3 |
| 4 | -2.33748e-15 | -1.47001e-15 | -8.67475e-16 | 392.528 | 0.31722 | vflow_energy_numer_BTUps | 14398.1 |
| 12 | 1.55873e-15 | 1.03566e-15 | 5.23071e-16 | -598.611 | -0.340825 | vflow_energy_numer_BTUps | 14652.2 |
| 14 | -1.55474e-15 | -1.04817e-15 | -5.06571e-16 | -211.489 | -0.121868 | vflow_energy_V_in_term_BTUps | 14593.7 |
| 15 | 1.5006e-15 | 1.02308e-15 | 4.77528e-16 | -155.277 | -0.0873342 | vflow_energy_V_in_term_BTUps | 14634.4 |

## Worst Temperature Equation Gaps

| stage_1based | dT_raw_minus_vflow_predicted_F_per_s | dT_energy_raw_F_per_s | vflow_energy_predicted_dT_from_used_F_per_s | vflow_energy_dT_target_F_per_s | vflow_energy_resid_after_used_BTUps |
|---:|---:|---:|---:|---:|---:|
| 2 | -1.43795e-07 | -1.43795e-07 | 0 | 0 | 0 |
| 5 | 8.71998e-16 | 2.38033e-15 | 1.50833e-15 | 0 | 1.81899e-12 |
| 4 | -8.67475e-16 | -2.33748e-15 | -1.47001e-15 | 0 | -1.81899e-12 |
| 7 | 8.62899e-16 | 2.41629e-15 | 1.55339e-15 | 0 | 1.81899e-12 |
| 8 | 8.5954e-16 | 2.42574e-15 | 1.5662e-15 | 0 | 1.81899e-12 |
| 12 | 5.23071e-16 | 1.55873e-15 | 1.03566e-15 | 0 | 1.81899e-12 |
| 14 | -5.06571e-16 | -1.55474e-15 | -1.04817e-15 | 0 | -1.81899e-12 |
| 15 | 4.77528e-16 | 1.5006e-15 | 1.02308e-15 | 0 | 1.81899e-12 |

## Worst Temperature/Vapor-Flow Term Gaps

| stage_1based | temp_energy_dE_minus_vflow_resid_BTUps | temp_energy_dE_BTUps | vflow_energy_resid_after_used_BTUps | temp_energy_L_in_term_BTUps | vflow_energy_L_in_term_BTUps | temp_energy_V_in_term_BTUps | vflow_energy_V_in_term_BTUps | temp_energy_V_out_term_BTUps | vflow_energy_numer_BTUps |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 | -0.000165458 | -0.000165458 | 0 | -355.805 | -355.805 | 14038.2 | 14038.2 | 13682.4 | 13682.4 |
| 3 | 0 | 0 | 0 | 161.924 | 161.924 | 14120.7 | 14120.7 | 14282.6 | 14282.6 |
| 4 | 0 | -1.81899e-12 | -1.81899e-12 | 179.61 | 179.61 | 14218.5 | 14218.5 | 14398.1 | 14398.1 |
| 5 | 0 | 1.81899e-12 | 1.81899e-12 | 110.236 | 110.236 | 14280.1 | 14280.1 | 14390.3 | 14390.3 |
| 6 | 0 | 0 | 0 | 60.9621 | 60.9621 | 14314.4 | 14314.4 | 14375.4 | 14375.4 |
| 7 | 0 | 1.81899e-12 | 1.81899e-12 | 34.1225 | 34.1225 | 14333.6 | 14333.6 | 14367.7 | 14367.7 |
| 8 | 0 | 1.81899e-12 | 1.81899e-12 | 23.0081 | 23.0081 | 14346.5 | 14346.5 | 14369.5 | 14369.5 |
| 9 | 0 | 0 | 0 | 21.9821 | 21.9821 | 14358.8 | 14358.8 | 14380.8 | 14380.8 |

## Top K Mismatches

| stage_1based | component | ln_K_state_over_K_thermo | K_state | K_thermo | y_state | y_eq |
|---:|---:|---:|---:|---:|---:|---:|
| 19 | n_Propane | -0.587764 | 1.08653 | 1.95571 | 0.171476 | 0.171846 |
| 19 | n_Pentane | 0.529229 | 0.868195 | 0.511418 | 0.0742902 | 0.0738223 |
| 18 | n_Propane | -0.338936 | 1.35404 | 1.90034 | 0.217715 | 0.219496 |
| 4 | n_Pentane | 0.312907 | 0.342518 | 0.25049 | 9.84296e-05 | 9.76789e-05 |
| 5 | n_Pentane | 0.297727 | 0.377292 | 0.280141 | 0.000277331 | 0.000275643 |
| 2 | n_Pentane | -0.278677 | 0.756785 | 1 | 1.91739e-05 | 2.21323e-05 |
| 18 | n_Pentane | 0.2629 | 0.630761 | 0.484941 | 0.0574063 | 0.0568369 |
| 6 | n_Pentane | 0.24815 | 0.389327 | 0.303769 | 0.000661142 | 0.000654043 |

## Top K Eq-Relax Mismatches

| stage_1based | component | ln_K_state_over_K_eq_relax | K_state | K_eq_relax | y_state | y_eq |
|---:|---:|---:|---:|---:|---:|---:|
| 19 | n_Propane | -0.587764 | 1.08653 | 1.95571 | 0.171476 | 0.171846 |
| 19 | n_Pentane | 0.529229 | 0.868195 | 0.511418 | 0.0742902 | 0.0738223 |
| 18 | n_Propane | -0.338936 | 1.35404 | 1.90034 | 0.217715 | 0.219496 |
| 4 | n_Pentane | 0.312907 | 0.342518 | 0.25049 | 9.84296e-05 | 9.76789e-05 |
| 5 | n_Pentane | 0.297727 | 0.377292 | 0.280141 | 0.000277331 | 0.000275643 |
| 2 | n_Pentane | -0.278677 | 0.756785 | 1 | 1.91739e-05 | 2.21323e-05 |
| 18 | n_Pentane | 0.2629 | 0.630761 | 0.484941 | 0.0574063 | 0.0568369 |
| 6 | n_Pentane | 0.24815 | 0.389327 | 0.303769 | 0.000661142 | 0.000654043 |

## Top Vapor Target Mismatches

| stage_1based | component | y_state_minus_y_target | y_state | y_target | y_eq |
|---:|---:|---:|---:|---:|---:|
| 1 | n_Propane | -0.905668 | 0 | 0.905668 | 0.905668 |
| 1 | n_Butane | -0.0943265 | 0 | 0.0943265 | 0.0943265 |
| 20 | n_Butane | -0.0491503 | 0.756611 | 0.805762 | 0.805762 |
| 20 | n_Propane | 0.047597 | 0.15782 | 0.110223 | 0.110223 |
| 3 | n_Propane | -0.00349631 | 0.860773 | 0.86427 | 0.86427 |
| 3 | n_Butane | 0.00349572 | 0.139199 | 0.135704 | 0.135704 |
| 4 | n_Propane | -0.00326777 | 0.772556 | 0.775823 | 0.775823 |
| 4 | n_Butane | 0.00326702 | 0.227346 | 0.224079 | 0.224079 |

## Top Interior Vapor Target Mismatches

| stage_1based | component | y_state_minus_y_target | y_state | y_target | y_eq |
|---:|---:|---:|---:|---:|---:|
| 3 | n_Propane | -0.00349631 | 0.860773 | 0.86427 | 0.86427 |
| 3 | n_Butane | 0.00349572 | 0.139199 | 0.135704 | 0.135704 |
| 4 | n_Propane | -0.00326777 | 0.772556 | 0.775823 | 0.775823 |
| 4 | n_Butane | 0.00326702 | 0.227346 | 0.224079 | 0.224079 |
| 15 | n_Butane | 0.00277422 | 0.579574 | 0.5768 | 0.5768 |
| 15 | n_Propane | -0.00267145 | 0.381497 | 0.384168 | 0.384168 |
| 5 | n_Propane | -0.00261282 | 0.690966 | 0.693578 | 0.693578 |
| 5 | n_Butane | 0.00261113 | 0.308757 | 0.306146 | 0.306146 |

