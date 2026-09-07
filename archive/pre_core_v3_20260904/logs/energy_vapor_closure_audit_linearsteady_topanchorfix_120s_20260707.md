# Energy/Vapor Closure Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_liq_eq_vap_linearsteady_300s_topanchorfix_20260707\column_profile_20260707_203741.csv`
Time: `120 s`
Stage rows: `20`

## Summary

| Check | Value |
|---|---:|
| max \|V_calc - V_used\| lbmol/h | 0 |
| max \|relative V gap\| | 0 |
| max \|adjacent vapor enthalpy gap\| BTU/lbmol | 107.757 |
| max \|P_from_holdup - P\| psia | 222.62 |
| max \|energy P used - logged P\| psia | 0.000235781 |
| max \|ln(K_state/K_thermo)\| | 0.715991 |
| max \|ln(K_state/K_eq_relax)\| | 0.715991 |
| max \|y_state - y_eq\| | 0.905668 |
| max \|y_state - y_target\| | 0.905668 |
| max \|y_state - y_target\| interior | 0.00996567 |
| max \|dT_energy_raw\| F/s | 2.42345e-15 |
| max \|energy residual / heat capacity\| F/s | 0.142468 |
| max \|dT raw - vapor-flow predicted dT\| F/s | 8.53969e-16 |
| max \|temp dE - vapor-flow residual\| BTU/s | 0 |

## Diagnostic Interpretation

- equilibrium K-state mismatch

This report uses logged RHS diagnostics only. It does not recompute thermo or change vapor-flow closure.

## Top Composite Interfaces

| vapor_source_stage_1based | vapor_receiver_stage_1based | interface_inconsistency_score | V_calc_minus_used_lbmolph | relative_V_calc_minus_used | vflow_energy_P_used_minus_source_P_psia | vflow_energy_pressure_basis_code | source_minus_receiver_HV_BTU_per_lbmol | vflow_energy_hV_in_source_code | vflow_energy_hV_out_source_code | source_dT_energy_raw_F_per_s | receiver_dT_energy_raw_F_per_s |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | nan | 22.262 | nan | nan | nan | nan | nan | nan | nan | 0 | nan |
| 3 | 2 | 3.03379 | 0 | 0 | -7.40689e-05 | 1 | 107.757 | 2 | 2 | -1.94167e-15 | -1.37599e-15 |
| 4 | 3 | 2.82179 | 0 | 0 | -0.000123443 | 1 | 40.1486 | 2 | 2 | 2.10748e-15 | -1.94167e-15 |
| 5 | 4 | 2.67761 | 0 | 0 | -0.000150302 | 1 | 29.002 | 2 | 2 | -2.27039e-15 | 2.10748e-15 |
| 11 | 10 | 2.54646 | 0 | 0 | -0.000235781 | 1 | 8.34227 | 2 | 2 | 0 | 0 |
| 6 | 5 | 2.49338 | 0 | 0 | -0.000164305 | 1 | 18.4346 | 2 | 2 | 0 | -2.27039e-15 |
| 10 | 9 | 2.48719 | 0 | 0 | -0.000209391 | 1 | 6.1908 | 2 | 2 | 0 | -2.42345e-15 |
| 13 | 12 | 2.40506 | 0 | 0 | -0.000178509 | 1 | 4.50083 | 2 | 2 | 0 | 1.72706e-15 |
| 14 | 13 | 2.4031 | 0 | 0 | -0.000163083 | 1 | 4.74155 | 2 | 2 | 0 | 0 |
| 7 | 6 | 2.39555 | 0 | 0 | -0.000173192 | 1 | 11.3024 | 2 | 2 | -2.42032e-15 | 0 |
| 9 | 8 | 2.36318 | 0 | 0 | -0.000192443 | 1 | 5.91187 | 2 | 2 | -2.42345e-15 | 0 |
| 8 | 7 | 2.3583 | 0 | 0 | -0.000181533 | 1 | 7.40967 | 2 | 2 | 0 | -2.42032e-15 |

## Worst Temperature Rates

| stage_1based | dT_energy_raw_F_per_s | vflow_energy_predicted_dT_from_used_F_per_s | dT_raw_minus_vflow_predicted_F_per_s | stage_energy_balance_resid_BTUps | stage_energy_resid_over_heat_capacity_F_per_s | dominant_energy_term | dominant_energy_term_BTUps |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 9 | -2.42345e-15 | -1.57981e-15 | -8.43637e-16 | 26.3709 | 0.0229034 | vflow_energy_numer_BTUps | 14554.9 |
| 7 | -2.42032e-15 | -1.56636e-15 | -8.53969e-16 | 16.5498 | 0.0142513 | vflow_energy_numer_BTUps | 14539.2 |
| 5 | -2.27039e-15 | -1.45337e-15 | -8.17022e-16 | -52.6718 | -0.0420847 | vflow_energy_numer_BTUps | 14557.2 |
| 4 | 2.10748e-15 | 1.34315e-15 | 7.64324e-16 | -124.68 | -0.0920648 | vflow_energy_numer_BTUps | 14522.4 |
| 3 | -1.94167e-15 | -1.23712e-15 | -7.04545e-16 | -209.477 | -0.142468 | vflow_energy_numer_BTUps | 14496.7 |
| 12 | 1.72706e-15 | 1.1472e-15 | 5.79867e-16 | 194.917 | 0.12293 | vflow_energy_V_in_term_BTUps | 14789.7 |
| 15 | 1.56624e-15 | 1.07165e-15 | 4.94586e-16 | 70.9567 | 0.0418039 | vflow_energy_numer_BTUps | 14777.2 |
| 2 | -1.37599e-15 | -8.15964e-16 | -5.60023e-16 | -237.033 | -0.106328 | vflow_energy_V_in_term_BTUps | 14197.2 |
| 1 | 0 | nan | nan | nan | nan |  | nan |
| 6 | 0 | 0 | 0 | -7.8193 | -0.00656313 | vflow_energy_numer_BTUps | 14544.7 |
| 8 | 0 | 0 | 0 | 28.0171 | 0.0243552 | vflow_energy_numer_BTUps | 14542.4 |
| 10 | 0 | 0 | 0 | 6.92767 | 0.00596348 | vflow_energy_numer_BTUps | 14620.4 |

## Worst Temperature Equation Gaps

| stage_1based | dT_raw_minus_vflow_predicted_F_per_s | dT_energy_raw_F_per_s | vflow_energy_predicted_dT_from_used_F_per_s | vflow_energy_dT_target_F_per_s | vflow_energy_resid_after_used_BTUps |
|---:|---:|---:|---:|---:|---:|
| 7 | -8.53969e-16 | -2.42032e-15 | -1.56636e-15 | 0 | -1.81899e-12 |
| 9 | -8.43637e-16 | -2.42345e-15 | -1.57981e-15 | 0 | -1.81899e-12 |
| 5 | -8.17022e-16 | -2.27039e-15 | -1.45337e-15 | 0 | -1.81899e-12 |
| 4 | 7.64324e-16 | 2.10748e-15 | 1.34315e-15 | 0 | 1.81899e-12 |
| 3 | -7.04545e-16 | -1.94167e-15 | -1.23712e-15 | 0 | -1.81899e-12 |
| 12 | 5.79867e-16 | 1.72706e-15 | 1.1472e-15 | 0 | 1.81899e-12 |
| 2 | -5.60023e-16 | -1.37599e-15 | -8.15964e-16 | 0 | -1.81899e-12 |
| 15 | 4.94586e-16 | 1.56624e-15 | 1.07165e-15 | 0 | 1.81899e-12 |
| 6 | 0 | 0 | 0 | 0 | 0 |
| 8 | 0 | 0 | 0 | 0 | 0 |
| 10 | 0 | 0 | 0 | 0 | 0 |
| 11 | 0 | 0 | 0 | 0 | 0 |

## Worst Temperature/Vapor-Flow Term Gaps

| stage_1based | temp_energy_dE_minus_vflow_resid_BTUps | temp_energy_dE_BTUps | vflow_energy_resid_after_used_BTUps | temp_energy_L_in_term_BTUps | vflow_energy_L_in_term_BTUps | temp_energy_V_in_term_BTUps | vflow_energy_V_in_term_BTUps | temp_energy_V_out_term_BTUps | vflow_energy_numer_BTUps |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 | 0 | -1.81899e-12 | -1.81899e-12 | -322.092 | -322.092 | 14197.2 | 14197.2 | 13875.1 | 13875.1 |
| 3 | 0 | -1.81899e-12 | -1.81899e-12 | 196.361 | 196.361 | 14300.3 | 14300.3 | 14496.7 | 14496.7 |
| 4 | 0 | 1.81899e-12 | 1.81899e-12 | 142.683 | 142.683 | 14379.7 | 14379.7 | 14522.4 | 14522.4 |
| 5 | 0 | -1.81899e-12 | -1.81899e-12 | 112.682 | 112.682 | 14444.5 | 14444.5 | 14557.2 | 14557.2 |
| 6 | 0 | 0 | 0 | 63.4037 | 63.4037 | 14481.3 | 14481.3 | 14544.7 | 14544.7 |
| 7 | 0 | -1.81899e-12 | -1.81899e-12 | 36.6821 | 36.6821 | 14502.5 | 14502.5 | 14539.2 | 14539.2 |
| 8 | 0 | 0 | 0 | 25.2986 | 25.2986 | 14517.1 | 14517.1 | 14542.4 | 14542.4 |
| 9 | 0 | -1.81899e-12 | -1.81899e-12 | 23.9761 | 23.9761 | 14530.9 | 14530.9 | 14554.9 | 14554.9 |
| 10 | 0 | 0 | 0 | 56.7309 | 56.7309 | 14563.7 | 14563.7 | 14620.4 | 14620.4 |
| 11 | 0 | 0 | 0 | 61.5829 | 61.5829 | 14599.5 | 14599.5 | 14661.1 | 14661.1 |
| 12 | 0 | 1.81899e-12 | 1.81899e-12 | 69.7289 | 69.7289 | 14789.7 | 14789.7 | 14710.6 | 14710.6 |
| 13 | 0 | 0 | 0 | 30.2549 | 30.2549 | 14779.3 | 14779.3 | 14809.6 | 14809.6 |

## Top K Mismatches

| stage_1based | component | ln_K_state_over_K_thermo | K_state | K_thermo | y_state | y_eq |
|---:|---:|---:|---:|---:|---:|---:|
| 20 | n_Propane | 0.715991 | 2.04621 | 1 | 0.086622 | 0.110223 |
| 20 | n_Pentane | -0.588249 | 0.555299 | 1 | 0.10117 | 0.0840153 |
| 3 | n_Pentane | 0.221389 | 0.273235 | 0.218972 | 4.97746e-05 | 3.77773e-05 |
| 4 | n_Pentane | 0.182038 | 0.300499 | 0.250487 | 0.000155544 | 0.000128993 |
| 5 | n_Pentane | 0.154761 | 0.327033 | 0.280143 | 0.00039138 | 0.00033921 |
| 6 | n_Pentane | 0.133005 | 0.346974 | 0.303763 | 0.000857078 | 0.000761734 |
| 7 | n_Pentane | 0.115866 | 0.360185 | 0.320779 | 0.00171414 | 0.00154567 |
| 8 | n_Pentane | 0.101528 | 0.368246 | 0.332693 | 0.00323384 | 0.0029414 |
| 9 | n_Pentane | 0.0883974 | 0.373057 | 0.341495 | 0.005876 | 0.00537418 |
| 10 | n_Pentane | 0.0732124 | 0.375616 | 0.349099 | 0.0104114 | 0.00955301 |
| 19 | n_Propane | 0.0716444 | 2.09946 | 1.9543 | 0.147215 | 0.152971 |
| 11 | n_Pentane | 0.0575718 | 0.378821 | 0.357627 | 0.0181461 | 0.01671 |

## Top K Eq-Relax Mismatches

| stage_1based | component | ln_K_state_over_K_eq_relax | K_state | K_eq_relax | y_state | y_eq |
|---:|---:|---:|---:|---:|---:|---:|
| 20 | n_Propane | 0.715991 | 2.04621 | 1 | 0.086622 | 0.110223 |
| 20 | n_Pentane | -0.588249 | 0.555299 | 1 | 0.10117 | 0.0840153 |
| 3 | n_Pentane | 0.221389 | 0.273235 | 0.218972 | 4.97746e-05 | 3.77773e-05 |
| 4 | n_Pentane | 0.182038 | 0.300499 | 0.250487 | 0.000155544 | 0.000128993 |
| 5 | n_Pentane | 0.154761 | 0.327033 | 0.280143 | 0.00039138 | 0.00033921 |
| 6 | n_Pentane | 0.133005 | 0.346974 | 0.303763 | 0.000857078 | 0.000761734 |
| 7 | n_Pentane | 0.115866 | 0.360185 | 0.320779 | 0.00171414 | 0.00154567 |
| 8 | n_Pentane | 0.101528 | 0.368246 | 0.332693 | 0.00323384 | 0.0029414 |
| 9 | n_Pentane | 0.0883974 | 0.373057 | 0.341495 | 0.005876 | 0.00537418 |
| 10 | n_Pentane | 0.0732124 | 0.375616 | 0.349099 | 0.0104114 | 0.00955301 |
| 19 | n_Propane | 0.0716444 | 2.09946 | 1.9543 | 0.147215 | 0.152971 |
| 11 | n_Pentane | 0.0575718 | 0.378821 | 0.357627 | 0.0181461 | 0.01671 |

## Top Vapor Target Mismatches

| stage_1based | component | y_state_minus_y_target | y_state | y_target | y_eq |
|---:|---:|---:|---:|---:|---:|
| 1 | n_Propane | -0.905668 | 0 | 0.905668 | 0.905668 |
| 1 | n_Butane | -0.0943265 | 0 | 0.0943265 | 0.0943265 |
| 20 | n_Propane | -0.023601 | 0.086622 | 0.110223 | 0.110223 |
| 20 | n_Pentane | 0.0171551 | 0.10117 | 0.0840153 | 0.0840153 |
| 3 | n_Propane | -0.00996567 | 0.85433 | 0.864295 | 0.864295 |
| 3 | n_Butane | 0.00995367 | 0.145621 | 0.135667 | 0.135667 |
| 4 | n_Propane | -0.0090696 | 0.766824 | 0.775893 | 0.775893 |
| 4 | n_Butane | 0.00904305 | 0.233021 | 0.223978 | 0.223978 |
| 5 | n_Propane | -0.00704832 | 0.686647 | 0.693695 | 0.693695 |
| 5 | n_Butane | 0.00699615 | 0.312962 | 0.305966 | 0.305966 |
| 20 | n_Butane | 0.00644591 | 0.812208 | 0.805762 | 0.805762 |
| 15 | n_Propane | -0.00595422 | 0.373347 | 0.379301 | 0.379301 |

## Top Interior Vapor Target Mismatches

| stage_1based | component | y_state_minus_y_target | y_state | y_target | y_eq |
|---:|---:|---:|---:|---:|---:|
| 3 | n_Propane | -0.00996567 | 0.85433 | 0.864295 | 0.864295 |
| 3 | n_Butane | 0.00995367 | 0.145621 | 0.135667 | 0.135667 |
| 4 | n_Propane | -0.0090696 | 0.766824 | 0.775893 | 0.775893 |
| 4 | n_Butane | 0.00904305 | 0.233021 | 0.223978 | 0.223978 |
| 5 | n_Propane | -0.00704832 | 0.686647 | 0.693695 | 0.693695 |
| 5 | n_Butane | 0.00699615 | 0.312962 | 0.305966 | 0.305966 |
| 15 | n_Propane | -0.00595422 | 0.373347 | 0.379301 | 0.379301 |
| 19 | n_Propane | -0.00575565 | 0.147215 | 0.152971 | 0.152971 |
| 15 | n_Butane | 0.00557455 | 0.589661 | 0.584087 | 0.584087 |
| 17 | n_Propane | -0.00544872 | 0.261744 | 0.267193 | 0.267193 |
| 16 | n_Propane | -0.00544394 | 0.319366 | 0.32481 | 0.32481 |
| 14 | n_Propane | -0.00544118 | 0.422519 | 0.427961 | 0.427961 |

