# Energy/Vapor Closure Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_interior_liq_vapor_eq_align_smoke_20260707\column_profile_20260707_111634.csv`
Time: `0.2 s`
Stage rows: `20`

## Summary

| Check | Value |
|---|---:|
| max \|V_calc - V_used\| lbmol/h | 0 |
| max \|relative V gap\| | 0 |
| max \|adjacent vapor enthalpy gap\| BTU/lbmol | 110.197 |
| max \|P_from_holdup - P\| psia | 222.62 |
| max \|energy P used - logged P\| psia | 0.00805049 |
| max \|ln(K_state/K_thermo)\| | 0.71384 |
| max \|ln(K_state/K_eq_relax)\| | 0.71384 |
| max \|y_state - y_eq\| | 0.905668 |
| max \|y_state - y_target\| | 0.905668 |
| max \|y_state - y_target\| interior | 0.00348621 |
| max \|dT_energy_raw\| F/s | 1.43896e-07 |
| max \|energy residual / heat capacity\| F/s | 0.150596 |
| max \|dT raw - vapor-flow predicted dT\| F/s | 1.43896e-07 |
| max \|temp dE - vapor-flow residual\| BTU/s | 0.000165458 |

## Diagnostic Interpretation

- equilibrium K-state mismatch

This report uses logged RHS diagnostics only. It does not recompute thermo or change vapor-flow closure.

## Top Composite Interfaces

| vapor_source_stage_1based | vapor_receiver_stage_1based | interface_inconsistency_score | V_calc_minus_used_lbmolph | relative_V_calc_minus_used | vflow_energy_P_used_minus_source_P_psia | vflow_energy_pressure_basis_code | source_minus_receiver_HV_BTU_per_lbmol | vflow_energy_hV_in_source_code | vflow_energy_hV_out_source_code | source_dT_energy_raw_F_per_s | receiver_dT_energy_raw_F_per_s |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | nan | 22.262 | nan | nan | nan | nan | nan | nan | nan | 0 | nan |
| 19 | 18 | 0.3631 | 0 | 0 | -0.00053929 | 1 | 6.26432 | 2 | 2 | 0 | -1.21374e-15 |
| 18 | 17 | 0.349146 | 0 | 0 | -0.00148156 | 1 | 3.77216 | 2 | 2 | -1.21374e-15 | -1.19579e-15 |
| 17 | 16 | 0.32326 | 0 | 0 | -0.00257995 | 1 | 3.67521 | 2 | 2 | -1.19579e-15 | 0 |
| 20 | 19 | 0.321844 | nan | nan | nan | nan | -12.9685 | nan | nan | 0 | 0 |
| 2 | 1 | 0.301893 | 0 | 0 | -0.000550296 | 1 | 37.5427 | 2 | 2 | -1.43896e-07 | 0 |
| 16 | 15 | 0.28711 | 0 | 0 | -0.00385696 | 1 | 4.32753 | 2 | 2 | 0 | -1.50025e-15 |
| 3 | 2 | 0.261336 | 0 | 0 | -0.0013054 | 1 | 110.197 | 2 | 2 | 0 | -1.43896e-07 |

## Worst Temperature Rates

| stage_1based | dT_energy_raw_F_per_s | vflow_energy_predicted_dT_from_used_F_per_s | dT_raw_minus_vflow_predicted_F_per_s | stage_energy_balance_resid_BTUps | stage_energy_resid_over_heat_capacity_F_per_s | dominant_energy_term | dominant_energy_term_BTUps |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 | -1.43896e-07 | 0 | -1.43896e-07 | -297.225 | -0.150596 | vflow_energy_V_in_term_BTUps | 14151.8 |
| 11 | -2.46648e-15 | -1.6007e-15 | -8.65782e-16 | -39.6367 | -0.03488 | vflow_energy_numer_BTUps | 14540.3 |
| 9 | -2.4352e-15 | -1.57612e-15 | -8.59076e-16 | 3.70918 | 0.00321394 | vflow_energy_numer_BTUps | 14501.4 |
| 5 | 2.38029e-15 | 1.50833e-15 | 8.71955e-16 | 20.2288 | 0.016774 | vflow_energy_numer_BTUps | 14502.2 |
| 14 | -1.55436e-15 | -1.04819e-15 | -5.06174e-16 | 71.6766 | 0.0413034 | vflow_energy_numer_BTUps | 14766.3 |
| 15 | -1.50025e-15 | -1.02311e-15 | -4.77135e-16 | 94.5606 | 0.0531867 | vflow_energy_numer_BTUps | 14759.2 |
| 18 | -1.21374e-15 | -8.60514e-16 | -3.53228e-16 | 125.112 | 0.0591869 | vflow_energy_numer_BTUps | 14748.3 |
| 17 | -1.19579e-15 | -8.38051e-16 | -3.57737e-16 | 121.948 | 0.0561842 | vflow_energy_numer_BTUps | 14743.4 |

## Worst Temperature Equation Gaps

| stage_1based | dT_raw_minus_vflow_predicted_F_per_s | dT_energy_raw_F_per_s | vflow_energy_predicted_dT_from_used_F_per_s | vflow_energy_dT_target_F_per_s | vflow_energy_resid_after_used_BTUps |
|---:|---:|---:|---:|---:|---:|
| 2 | -1.43896e-07 | -1.43896e-07 | 0 | 0 | 0 |
| 5 | 8.71955e-16 | 2.38029e-15 | 1.50833e-15 | 0 | 1.81899e-12 |
| 11 | -8.65782e-16 | -2.46648e-15 | -1.6007e-15 | 0 | -1.81899e-12 |
| 9 | -8.59076e-16 | -2.4352e-15 | -1.57612e-15 | 0 | -1.81899e-12 |
| 14 | -5.06174e-16 | -1.55436e-15 | -1.04819e-15 | 0 | -1.81899e-12 |
| 15 | -4.77135e-16 | -1.50025e-15 | -1.02311e-15 | 0 | -1.81899e-12 |
| 17 | -3.57737e-16 | -1.19579e-15 | -8.38051e-16 | 0 | -1.81899e-12 |
| 18 | -3.53228e-16 | -1.21374e-15 | -8.60514e-16 | 0 | -1.81899e-12 |

## Worst Temperature/Vapor-Flow Term Gaps

| stage_1based | temp_energy_dE_minus_vflow_resid_BTUps | temp_energy_dE_BTUps | vflow_energy_resid_after_used_BTUps | temp_energy_L_in_term_BTUps | vflow_energy_L_in_term_BTUps | temp_energy_V_in_term_BTUps | vflow_energy_V_in_term_BTUps | temp_energy_V_out_term_BTUps | vflow_energy_numer_BTUps |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 | -0.000165458 | -0.000165458 | 0 | -329.12 | -329.12 | 14151.8 | 14151.8 | 13822.6 | 13822.6 |
| 3 | 0 | 0 | 0 | 140.377 | 140.377 | 14224.5 | 14224.5 | 14364.8 | 14364.8 |
| 4 | 0 | 0 | 0 | 182.567 | 182.567 | 14325.8 | 14325.8 | 14508.3 | 14508.3 |
| 5 | 0 | 1.81899e-12 | 1.81899e-12 | 112.396 | 112.396 | 14389.8 | 14389.8 | 14502.2 | 14502.2 |
| 6 | 0 | 0 | 0 | 63.0561 | 63.0561 | 14425.9 | 14425.9 | 14489 | 14489 |
| 7 | 0 | 0 | 0 | 36.4016 | 36.4016 | 14446.8 | 14446.8 | 14483.2 | 14483.2 |
| 8 | 0 | 0 | 0 | 25.595 | 25.595 | 14461.4 | 14461.4 | 14487 | 14487 |
| 9 | 0 | -1.81899e-12 | -1.81899e-12 | 25.457 | 25.457 | 14475.9 | 14475.9 | 14501.4 | 14501.4 |

## Top K Mismatches

| stage_1based | component | ln_K_state_over_K_thermo | K_state | K_thermo | y_state | y_eq |
|---:|---:|---:|---:|---:|---:|---:|
| 20 | n_Propane | 0.71384 | 2.04182 | 1 | 0.10908 | 0.110223 |
| 20 | n_Pentane | -0.5904 | 0.554106 | 1 | 0.111002 | 0.0840153 |
| 2 | n_Pentane | -0.200228 | 0.818544 | 1 | 1.30066e-05 | 1.43909e-05 |
| 11 | n_Pentane | 0.0708633 | 0.384098 | 0.357822 | 0.0149864 | 0.0140932 |
| 3 | n_Pentane | 0.0469636 | 0.229502 | 0.218973 | 2.4248e-05 | 2.31997e-05 |
| 20 | n_Butane | 0.0441277 | 1.04512 | 1 | 0.779919 | 0.805762 |
| 9 | n_Pentane | 0.0388827 | 0.355028 | 0.341489 | 0.00565203 | 0.0054605 |
| 10 | n_Pentane | 0.0362597 | 0.361987 | 0.349097 | 0.00987314 | 0.00956249 |

## Top K Eq-Relax Mismatches

| stage_1based | component | ln_K_state_over_K_eq_relax | K_state | K_eq_relax | y_state | y_eq |
|---:|---:|---:|---:|---:|---:|---:|
| 20 | n_Propane | 0.71384 | 2.04182 | 1 | 0.10908 | 0.110223 |
| 20 | n_Pentane | -0.5904 | 0.554106 | 1 | 0.111002 | 0.0840153 |
| 2 | n_Pentane | -0.200228 | 0.818544 | 1 | 1.30066e-05 | 1.43909e-05 |
| 11 | n_Pentane | 0.0708633 | 0.384098 | 0.357822 | 0.0149864 | 0.0140932 |
| 3 | n_Pentane | 0.0469636 | 0.229502 | 0.218973 | 2.4248e-05 | 2.31997e-05 |
| 20 | n_Butane | 0.0441277 | 1.04512 | 1 | 0.779919 | 0.805762 |
| 9 | n_Pentane | 0.0388827 | 0.355028 | 0.341489 | 0.00565203 | 0.0054605 |
| 10 | n_Pentane | 0.0362597 | 0.361987 | 0.349097 | 0.00987314 | 0.00956249 |

## Top Vapor Target Mismatches

| stage_1based | component | y_state_minus_y_target | y_state | y_target | y_eq |
|---:|---:|---:|---:|---:|---:|
| 1 | n_Propane | -0.905668 | 0 | 0.905668 | 0.905668 |
| 1 | n_Butane | -0.0943265 | 0 | 0.0943265 | 0.0943265 |
| 20 | n_Pentane | 0.0269866 | 0.111002 | 0.0840153 | 0.0840153 |
| 20 | n_Butane | -0.0258431 | 0.779919 | 0.805762 | 0.805762 |
| 3 | n_Propane | -0.00348621 | 0.860775 | 0.864262 | 0.864262 |
| 3 | n_Butane | 0.00348516 | 0.1392 | 0.135715 | 0.135715 |
| 4 | n_Propane | -0.00325554 | 0.772545 | 0.7758 | 0.7758 |
| 4 | n_Butane | 0.00325308 | 0.227365 | 0.224112 | 0.224112 |

## Top Interior Vapor Target Mismatches

| stage_1based | component | y_state_minus_y_target | y_state | y_target | y_eq |
|---:|---:|---:|---:|---:|---:|
| 3 | n_Propane | -0.00348621 | 0.860775 | 0.864262 | 0.864262 |
| 3 | n_Butane | 0.00348516 | 0.1392 | 0.135715 | 0.135715 |
| 4 | n_Propane | -0.00325554 | 0.772545 | 0.7758 | 0.7758 |
| 4 | n_Butane | 0.00325308 | 0.227365 | 0.224112 | 0.224112 |
| 15 | n_Butane | 0.00261335 | 0.580945 | 0.578332 | 0.578332 |
| 5 | n_Propane | -0.00257627 | 0.690932 | 0.693508 | 0.693508 |
| 5 | n_Butane | 0.00257077 | 0.308809 | 0.306239 | 0.306239 |
| 15 | n_Propane | -0.00253611 | 0.380586 | 0.383122 | 0.383122 |

