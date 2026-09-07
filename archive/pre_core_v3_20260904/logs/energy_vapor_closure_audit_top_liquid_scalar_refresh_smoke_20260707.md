# Energy/Vapor Closure Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_top_liquid_scalar_refresh_smoke_20260707\column_profile_20260707_103001.csv`
Time: `0.2 s`
Stage rows: `20`

## Summary

| Check | Value |
|---|---:|
| max \|V_calc - V_used\| lbmol/h | 0 |
| max \|relative V gap\| | 0 |
| max \|adjacent vapor enthalpy gap\| BTU/lbmol | 108.874 |
| max \|P_from_holdup - P\| psia | 222.62 |
| max \|energy P used - logged P\| psia | 0.00779871 |
| max \|ln(K_state/K_thermo)\| | 0.719022 |
| max \|ln(K_state/K_eq_relax)\| | 0.719022 |
| max \|y_state - y_eq\| | 0.905668 |
| max \|y_state - y_target\| | 0.905668 |
| max \|y_state - y_target\| interior | 0.0400921 |
| max \|dT_energy_raw\| F/s | 0.222438 |
| max \|energy residual / heat capacity\| F/s | 1.51994 |
| max \|dT raw - vapor-flow predicted dT\| F/s | 0.222438 |
| max \|temp dE - vapor-flow residual\| BTU/s | 255.834 |

## Diagnostic Interpretation

- temperature-rate spike
- vapor-flow/temperature energy equation mismatch
- equilibrium K-state mismatch

This report uses logged RHS diagnostics only. It does not recompute thermo or change vapor-flow closure.

## Top Composite Interfaces

| vapor_source_stage_1based | vapor_receiver_stage_1based | interface_inconsistency_score | V_calc_minus_used_lbmolph | relative_V_calc_minus_used | vflow_energy_P_used_minus_source_P_psia | vflow_energy_pressure_basis_code | source_minus_receiver_HV_BTU_per_lbmol | vflow_energy_hV_in_source_code | vflow_energy_hV_out_source_code | source_dT_energy_raw_F_per_s | receiver_dT_energy_raw_F_per_s |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | nan | 22.262 | nan | nan | nan | nan | nan | nan | nan | 0 | nan |
| 2 | 1 | 0.51049 | 0 | 0 | -0.000550296 | 1 | 38.866 | 2 | 2 | -0.222438 | 0 |
| 3 | 2 | 0.486562 | 0 | 0 | -0.00128485 | 1 | 108.874 | 2 | 2 | 0 | -0.222438 |
| 19 | 18 | 0.366905 | 0 | 0 | -0.00053929 | 1 | 6.27559 | 2 | 2 | 0 | 0 |
| 18 | 17 | 0.348793 | 0 | 0 | -0.00137517 | 1 | 3.76103 | 2 | 2 | 0 | 1.19581e-15 |
| 17 | 16 | 0.322692 | 0 | 0 | -0.00236026 | 1 | 3.67968 | 2 | 2 | 1.19581e-15 | 0 |
| 20 | 19 | 0.321847 | nan | nan | nan | nan | -12.9968 | nan | nan | 0 | 0 |
| 16 | 15 | 0.282862 | 0 | 0 | -0.003532 | 1 | 4.32678 | 2 | 2 | 0 | 1.50025e-15 |

## Worst Temperature Rates

| stage_1based | dT_energy_raw_F_per_s | vflow_energy_predicted_dT_from_used_F_per_s | dT_raw_minus_vflow_predicted_F_per_s | stage_energy_balance_resid_BTUps | stage_energy_resid_over_heat_capacity_F_per_s | dominant_energy_term | dominant_energy_term_BTUps |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 | -0.222438 | 0 | -0.222438 | 2999.95 | 1.51994 | vflow_energy_V_in_term_BTUps | 14046.6 |
| 11 | -2.46637e-15 | -1.60071e-15 | -8.65667e-16 | -186.423 | -0.164052 | vflow_energy_numer_BTUps | 14509.6 |
| 6 | 2.40185e-15 | 1.53436e-15 | 8.67488e-16 | 221.468 | 0.186814 | vflow_energy_numer_BTUps | 14374.5 |
| 5 | 2.38029e-15 | 1.50833e-15 | 8.71958e-16 | 300.791 | 0.24942 | vflow_energy_numer_BTUps | 14389.5 |
| 4 | 2.33746e-15 | 1.47001e-15 | 8.67453e-16 | 380.498 | 0.307498 | vflow_energy_numer_BTUps | 14397.3 |
| 13 | -1.55776e-15 | -1.04197e-15 | -5.15787e-16 | -309.849 | -0.177491 | vflow_energy_numer_BTUps | 14566.7 |
| 15 | 1.50025e-15 | 1.02308e-15 | 4.77175e-16 | -146.883 | -0.082613 | vflow_energy_V_in_term_BTUps | 14635.6 |
| 17 | 1.19581e-15 | 8.3805e-16 | 3.57755e-16 | -178.681 | -0.0823225 | vflow_energy_V_in_term_BTUps | 14677.3 |

## Worst Temperature Equation Gaps

| stage_1based | dT_raw_minus_vflow_predicted_F_per_s | dT_energy_raw_F_per_s | vflow_energy_predicted_dT_from_used_F_per_s | vflow_energy_dT_target_F_per_s | vflow_energy_resid_after_used_BTUps |
|---:|---:|---:|---:|---:|---:|
| 2 | -0.222438 | -0.222438 | 0 | 0 | 0 |
| 5 | 8.71958e-16 | 2.38029e-15 | 1.50833e-15 | 0 | 1.81899e-12 |
| 6 | 8.67488e-16 | 2.40185e-15 | 1.53436e-15 | 0 | 1.81899e-12 |
| 4 | 8.67453e-16 | 2.33746e-15 | 1.47001e-15 | 0 | 1.81899e-12 |
| 11 | -8.65667e-16 | -2.46637e-15 | -1.60071e-15 | 0 | -1.81899e-12 |
| 13 | -5.15787e-16 | -1.55776e-15 | -1.04197e-15 | 0 | -1.81899e-12 |
| 15 | 4.77175e-16 | 1.50025e-15 | 1.02308e-15 | 0 | 1.81899e-12 |
| 17 | 3.57755e-16 | 1.19581e-15 | 8.3805e-16 | 0 | 1.81899e-12 |

## Worst Temperature/Vapor-Flow Term Gaps

| stage_1based | temp_energy_dE_minus_vflow_resid_BTUps | temp_energy_dE_BTUps | vflow_energy_resid_after_used_BTUps | temp_energy_L_in_term_BTUps | vflow_energy_L_in_term_BTUps | temp_energy_V_in_term_BTUps | vflow_energy_V_in_term_BTUps | temp_energy_V_out_term_BTUps | vflow_energy_numer_BTUps |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 | -255.834 | -255.834 | 0 | -326.271 | -70.4372 | 14046.6 | 14046.6 | 13976.2 | 13976.2 |
| 3 | 0 | 0 | 0 | 144.32 | 144.32 | 14119.9 | 14119.9 | 14264.2 | 14264.2 |
| 4 | 0 | 1.81899e-12 | 1.81899e-12 | 179.583 | 179.583 | 14217.7 | 14217.7 | 14397.3 | 14397.3 |
| 5 | 0 | 1.81899e-12 | 1.81899e-12 | 110.2 | 110.2 | 14279.3 | 14279.3 | 14389.5 | 14389.5 |
| 6 | 0 | 1.81899e-12 | 1.81899e-12 | 60.9247 | 60.9247 | 14313.6 | 14313.6 | 14374.5 | 14374.5 |
| 7 | 0 | 0 | 0 | 34.0914 | 34.0914 | 14332.7 | 14332.7 | 14366.8 | 14366.8 |
| 8 | 0 | 0 | 0 | 23.0225 | 23.0225 | 14345.7 | 14345.7 | 14368.7 | 14368.7 |
| 9 | 0 | 0 | 0 | 22.174 | 22.174 | 14358.1 | 14358.1 | 14380.3 | 14380.3 |

## Top K Mismatches

| stage_1based | component | ln_K_state_over_K_thermo | K_state | K_thermo | y_state | y_eq |
|---:|---:|---:|---:|---:|---:|---:|
| 2 | n_Pentane | -0.719022 | 0.487229 | 1 | 1.13457e-05 | 1.70783e-05 |
| 20 | n_Propane | -0.689303 | 1 | 1.99233 | 0.157483 | 0.110223 |
| 20 | n_Pentane | 0.613094 | 1 | 0.541672 | 0.086019 | 0.0840153 |
| 19 | n_Propane | -0.597261 | 1.07627 | 1.95573 | 0.169494 | 0.172136 |
| 19 | n_Pentane | 0.565986 | 0.900684 | 0.511408 | 0.0774759 | 0.0739761 |
| 18 | n_Propane | -0.378248 | 1.30184 | 1.90033 | 0.20742 | 0.219413 |
| 3 | n_Butane | 0.361684 | 0.727172 | 0.506477 | 0.175804 | 0.135715 |
| 18 | n_Pentane | 0.347739 | 0.686614 | 0.484944 | 0.0630361 | 0.0567944 |

## Top K Eq-Relax Mismatches

| stage_1based | component | ln_K_state_over_K_eq_relax | K_state | K_eq_relax | y_state | y_eq |
|---:|---:|---:|---:|---:|---:|---:|
| 2 | n_Pentane | -0.719022 | 0.487229 | 1 | 1.13457e-05 | 1.70783e-05 |
| 20 | n_Propane | -0.689303 | 1 | 1.99233 | 0.157483 | 0.110223 |
| 20 | n_Pentane | 0.613094 | 1 | 0.541672 | 0.086019 | 0.0840153 |
| 19 | n_Propane | -0.597261 | 1.07627 | 1.95573 | 0.169494 | 0.172136 |
| 19 | n_Pentane | 0.565986 | 0.900684 | 0.511408 | 0.0774759 | 0.0739761 |
| 18 | n_Propane | -0.378248 | 1.30184 | 1.90033 | 0.20742 | 0.219413 |
| 3 | n_Butane | 0.361684 | 0.727172 | 0.506477 | 0.175804 | 0.135715 |
| 18 | n_Pentane | 0.347739 | 0.686614 | 0.484944 | 0.0630361 | 0.0567944 |

## Top Vapor Target Mismatches

| stage_1based | component | y_state_minus_y_target | y_state | y_target | y_eq |
|---:|---:|---:|---:|---:|---:|
| 1 | n_Propane | -0.905668 | 0 | 0.905668 | 0.905668 |
| 1 | n_Butane | -0.0943265 | 0 | 0.0943265 | 0.0943265 |
| 20 | n_Butane | -0.0492632 | 0.756498 | 0.805762 | 0.805762 |
| 20 | n_Propane | 0.0472595 | 0.157483 | 0.110223 | 0.110223 |
| 3 | n_Propane | -0.0400921 | 0.82417 | 0.864262 | 0.864262 |
| 3 | n_Butane | 0.0400897 | 0.175804 | 0.135715 | 0.135715 |
| 4 | n_Butane | 0.0333132 | 0.257423 | 0.22411 | 0.22411 |
| 4 | n_Propane | -0.0333101 | 0.742492 | 0.775802 | 0.775802 |

## Top Interior Vapor Target Mismatches

| stage_1based | component | y_state_minus_y_target | y_state | y_target | y_eq |
|---:|---:|---:|---:|---:|---:|
| 3 | n_Propane | -0.0400921 | 0.82417 | 0.864262 | 0.864262 |
| 3 | n_Butane | 0.0400897 | 0.175804 | 0.135715 | 0.135715 |
| 4 | n_Butane | 0.0333132 | 0.257423 | 0.22411 | 0.22411 |
| 4 | n_Propane | -0.0333101 | 0.742492 | 0.775802 | 0.775802 |
| 5 | n_Butane | 0.0240528 | 0.330264 | 0.306211 | 0.306211 |
| 5 | n_Propane | -0.0240326 | 0.669501 | 0.693534 | 0.693534 |
| 15 | n_Propane | -0.0207597 | 0.362533 | 0.383293 | 0.383293 |
| 14 | n_Propane | -0.0198643 | 0.410614 | 0.430478 | 0.430478 |

