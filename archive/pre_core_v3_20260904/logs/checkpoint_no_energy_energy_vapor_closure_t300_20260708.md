# Energy/Vapor Closure Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\checkpoint_no_energy_reload_300s_20260708\column_profile_20260708_181150.csv`
Time: `300 s`
Stage rows: `20`

## Summary

| Check | Value |
|---|---:|
| max \|V_calc - V_used\| lbmol/h | 0 |
| max \|relative V gap\| | 0 |
| max \|adjacent vapor enthalpy gap\| BTU/lbmol | 333.158 |
| max \|P_from_holdup - P\| psia | 548.837 |
| max \|energy P used - logged P\| psia | 3.78429e-05 |
| max \|ln(K_state/K_thermo)\| | 1.65014 |
| max \|ln(K_state/K_eq_relax)\| | nan |
| max \|y_state - y_eq\| | nan |
| max \|y_state - y_target\| | nan |
| max \|y_state - y_target\| interior | nan |
| max \|dT_energy_raw\| F/s | 7.41596e-10 |
| max \|energy residual / heat capacity\| F/s | nan |
| max \|dT raw - vapor-flow predicted dT\| F/s | 7.41596e-10 |
| max \|temp dE - vapor-flow residual\| BTU/s | 2.35194e-06 |

## Diagnostic Interpretation

- adjacent vapor enthalpy discontinuity
- equilibrium K-state mismatch

This report uses logged RHS diagnostics only. It does not recompute thermo or change vapor-flow closure.

## Top Composite Interfaces

| vapor_source_stage_1based | vapor_receiver_stage_1based | interface_inconsistency_score | V_calc_minus_used_lbmolph | relative_V_calc_minus_used | vflow_energy_P_used_minus_source_P_psia | vflow_energy_pressure_basis_code | source_minus_receiver_HV_BTU_per_lbmol | vflow_energy_hV_in_source_code | vflow_energy_hV_out_source_code | source_dT_energy_raw_F_per_s | receiver_dT_energy_raw_F_per_s |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 15 | 14 | 54.8957 | 0 | 0 | -2.41555e-05 | 1 | 120.662 | 2 | 2 | 0 | 0 |
| 14 | 13 | 53.4831 | 0 | 0 | -3.00074e-05 | 1 | 103.848 | 2 | 2 | 0 | 0 |
| 12 | 11 | 53.1443 | 0 | 0 | -3.73557e-05 | 1 | 92.1095 | 2 | 2 | 0 | 0 |
| 13 | 12 | 52.7551 | 0 | 0 | -3.42853e-05 | 1 | 87.6782 | 2 | 2 | 0 | 0 |
| 19 | 18 | 52.4263 | 0 | 0 | 0 | 1 | 157.679 | 2 | 2 | 0 | 0 |
| 11 | 10 | 51.8314 | 0 | 0 | -3.78429e-05 | 1 | 61.8936 | 2 | 2 | 0 | 0 |
| 10 | 9 | 51.5159 | 0 | 0 | -3.21908e-05 | 1 | 55.0438 | 2 | 2 | 0 | 0 |
| 9 | 8 | 51.2754 | 0 | 0 | -2.94959e-05 | 1 | 65.2252 | 2 | 2 | 0 | 0 |
| 18 | 17 | 50.6766 | 0 | 0 | -3.23066e-06 | 1 | 145.233 | 2 | 2 | 0 | 0 |
| 8 | 7 | 50.6535 | 0 | 0 | -2.85066e-05 | 1 | 84.12 | 2 | 2 | 0 | 0 |
| 7 | 6 | 50.2714 | 0 | 0 | -2.81981e-05 | 1 | 122.502 | 2 | 2 | 0 | 0 |
| 6 | 5 | 49.8459 | 0 | 0 | -2.64615e-05 | 1 | 178.169 | 2 | 2 | 0 | 0 |

## Worst Temperature Rates

| stage_1based | dT_energy_raw_F_per_s | vflow_energy_predicted_dT_from_used_F_per_s | dT_raw_minus_vflow_predicted_F_per_s | stage_energy_balance_resid_BTUps | stage_energy_resid_over_heat_capacity_F_per_s | dominant_energy_term | dominant_energy_term_BTUps |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 | 7.41596e-10 | 0 | 7.41596e-10 | nan | nan | vflow_energy_V_in_term_BTUps | 9621.01 |
| 1 | 0 | nan | nan | nan | nan |  | nan |
| 3 | 0 | 0 | 0 | nan | nan | vflow_energy_V_in_term_BTUps | 9686.47 |
| 4 | 0 | 0 | 0 | nan | nan | vflow_energy_V_in_term_BTUps | 9696.42 |
| 5 | 0 | 0 | 0 | nan | nan | vflow_energy_V_in_term_BTUps | 9683.88 |
| 6 | 0 | 0 | 0 | nan | nan | vflow_energy_V_in_term_BTUps | 9670.01 |
| 7 | 0 | 0 | 0 | nan | nan | vflow_energy_V_in_term_BTUps | 9658.42 |
| 8 | 0 | 0 | 0 | nan | nan | vflow_energy_V_in_term_BTUps | 9649.04 |
| 9 | 0 | 0 | 0 | nan | nan | vflow_energy_V_in_term_BTUps | 9635.34 |
| 10 | 0 | 0 | 0 | nan | nan | vflow_energy_V_in_term_BTUps | 9621.64 |
| 11 | 0 | 0 | 0 | nan | nan | vflow_energy_V_in_term_BTUps | 9604.56 |
| 12 | 0 | 0 | 0 | nan | nan | vflow_energy_V_in_term_BTUps | 10290.8 |

## Worst Temperature Equation Gaps

| stage_1based | dT_raw_minus_vflow_predicted_F_per_s | dT_energy_raw_F_per_s | vflow_energy_predicted_dT_from_used_F_per_s | vflow_energy_dT_target_F_per_s | vflow_energy_resid_after_used_BTUps |
|---:|---:|---:|---:|---:|---:|
| 2 | 7.41596e-10 | 7.41596e-10 | 0 | 0 | 0 |
| 3 | 0 | 0 | 0 | 0 | 0 |
| 4 | 0 | 0 | 0 | 0 | 0 |
| 5 | 0 | 0 | 0 | 0 | 0 |
| 6 | 0 | 0 | 0 | 0 | 0 |
| 7 | 0 | 0 | 0 | 0 | 0 |
| 8 | 0 | 0 | 0 | 0 | 0 |
| 9 | 0 | 0 | 0 | 0 | 0 |
| 10 | 0 | 0 | 0 | 0 | 0 |
| 11 | 0 | 0 | 0 | 0 | 0 |
| 12 | 0 | 0 | 0 | 0 | 0 |
| 13 | 0 | 0 | 0 | 0 | 0 |

## Worst Temperature/Vapor-Flow Term Gaps

| stage_1based | temp_energy_dE_minus_vflow_resid_BTUps | temp_energy_dE_BTUps | vflow_energy_resid_after_used_BTUps | temp_energy_L_in_term_BTUps | vflow_energy_L_in_term_BTUps | temp_energy_V_in_term_BTUps | vflow_energy_V_in_term_BTUps | temp_energy_V_out_term_BTUps | vflow_energy_numer_BTUps |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 | 2.35194e-06 | 2.35194e-06 | 0 | -646.555 | -646.555 | 9621.01 | 9621.01 | 8974.45 | 8974.45 |
| 3 | 0 | 0 | 0 | -742.359 | -742.359 | 9686.47 | 9686.47 | 8944.11 | 8944.11 |
| 4 | 0 | 0 | 0 | -568.357 | -568.357 | 9696.42 | 9696.42 | 9128.06 | 9128.06 |
| 5 | 0 | 0 | 0 | -407.294 | -407.294 | 9683.88 | 9683.88 | 9276.58 | 9276.58 |
| 6 | 0 | 0 | 0 | -233.622 | -233.622 | 9670.01 | 9670.01 | 9436.39 | 9436.39 |
| 7 | 0 | 0 | 0 | -165.398 | -165.398 | 9658.42 | 9658.42 | 9493.02 | 9493.02 |
| 8 | 0 | 0 | 0 | -122.799 | -122.799 | 9649.04 | 9649.04 | 9526.24 | 9526.24 |
| 9 | 0 | 0 | 0 | -169.767 | -169.767 | 9635.34 | 9635.34 | 9465.57 | 9465.57 |
| 10 | 0 | 0 | 0 | -145.94 | -145.94 | 9621.64 | 9621.64 | 9475.7 | 9475.7 |
| 11 | 0 | 0 | 0 | -159.3 | -159.3 | 9604.56 | 9604.56 | 9445.26 | 9445.26 |
| 12 | 0 | 0 | 0 | 109.218 | 109.218 | 10290.8 | 10290.8 | 9727.4 | 9727.4 |
| 13 | 0 | 0 | 0 | -365.872 | -365.872 | 10480.5 | 10480.5 | 10114.7 | 10114.7 |

## Top K Mismatches

| stage_1based | component | ln_K_state_over_K_thermo | K_state | K_thermo | y_state | y_eq |
|---:|---:|---:|---:|---:|---:|---:|
| 4 | n_Pentane | 1.65014 | 1.61024 | 0.309203 | 0.0517391 | nan |
| 3 | n_Pentane | 1.6387 | 1.50683 | 0.292676 | 0.0518175 | nan |
| 5 | n_Pentane | 1.63236 | 1.68449 | 0.329266 | 0.051666 | nan |
| 11 | n_Pentane | 1.61182 | 1.89975 | 0.379045 | 0.0511823 | nan |
| 10 | n_Pentane | 1.61051 | 1.88493 | 0.376581 | 0.0512769 | nan |
| 6 | n_Pentane | 1.60241 | 1.73888 | 0.350228 | 0.0515948 | nan |
| 9 | n_Pentane | 1.60113 | 1.85645 | 0.374389 | 0.0513646 | nan |
| 8 | n_Pentane | 1.58971 | 1.82173 | 0.371606 | 0.0514461 | nan |
| 7 | n_Pentane | 1.58728 | 1.78295 | 0.36458 | 0.0515222 | nan |
| 2 | n_Pentane | 1.57337 | 1.38319 | 0.286797 | 0.0519953 | nan |
| 3 | n_Butane | 0.657482 | 1.09494 | 0.56735 | 0.445251 | nan |
| 4 | n_Butane | 0.652668 | 1.12888 | 0.587757 | 0.444111 | nan |

## Top K Eq-Relax Mismatches

No finite records.

## Top Vapor Target Mismatches

No finite records.

## Top Interior Vapor Target Mismatches

No finite records.

