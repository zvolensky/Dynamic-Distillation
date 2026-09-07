# Energy/Vapor Closure Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_liq_eq_vap_linearsteady_60s_20260707\column_profile_20260707_171839.csv`
Time: `60 s`
Stage rows: `20`

## Summary

| Check | Value |
|---|---:|
| max \|V_calc - V_used\| lbmol/h | 0 |
| max \|relative V gap\| | 0 |
| max \|adjacent vapor enthalpy gap\| BTU/lbmol | 185.217 |
| max \|P_from_holdup - P\| psia | 226.15 |
| max \|energy P used - logged P\| psia | 0.0214586 |
| max \|ln(K_state/K_thermo)\| | 1.22017 |
| max \|ln(K_state/K_eq_relax)\| | 1.22017 |
| max \|y_state - y_eq\| | 0.905668 |
| max \|y_state - y_target\| | 0.905668 |
| max \|y_state - y_target\| interior | 0.13968 |
| max \|dT_energy_raw\| F/s | 0.000401358 |
| max \|energy residual / heat capacity\| F/s | 5.37011 |
| max \|dT raw - vapor-flow predicted dT\| F/s | 0.000401358 |
| max \|temp dE - vapor-flow residual\| BTU/s | 0.171018 |

## Diagnostic Interpretation

- equilibrium K-state mismatch
- vapor composition target mismatch

This report uses logged RHS diagnostics only. It does not recompute thermo or change vapor-flow closure.

## Top Composite Interfaces

| vapor_source_stage_1based | vapor_receiver_stage_1based | interface_inconsistency_score | V_calc_minus_used_lbmolph | relative_V_calc_minus_used | vflow_energy_P_used_minus_source_P_psia | vflow_energy_pressure_basis_code | source_minus_receiver_HV_BTU_per_lbmol | vflow_energy_hV_in_source_code | vflow_energy_hV_out_source_code | source_dT_energy_raw_F_per_s | receiver_dT_energy_raw_F_per_s |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | nan | 22.615 | nan | nan | nan | nan | nan | nan | nan | 0 | nan |
| 3 | 2 | 2.70219 | 0 | 0 | -0.0199934 | 1 | 114.311 | 2 | 2 | 0 | -4.93809e-06 |
| 4 | 3 | 2.5291 | 0 | 0 | -0.0214586 | 1 | 40.1492 | 2 | 2 | 0 | 0 |
| 11 | 10 | 2.15201 | 0 | 0 | -0.0209935 | 1 | 8.68327 | 2 | 2 | 0 | 0 |
| 5 | 4 | 2.12695 | 0 | 0 | -0.0213841 | 1 | 29.011 | 2 | 2 | 0 | 0 |
| 10 | 9 | 1.87726 | 0 | 0 | -0.0210241 | 1 | 6.65041 | 2 | 2 | 0 | 0 |
| 6 | 5 | 1.86039 | 0 | 0 | -0.0213004 | 1 | 18.4738 | 2 | 2 | 0 | 0 |
| 9 | 8 | 1.7625 | 0 | 0 | -0.021086 | 1 | 6.25619 | 2 | 2 | 0 | 0 |
| 7 | 6 | 1.75214 | 0 | 0 | -0.0212213 | 1 | 11.4059 | 2 | 2 | 0 | 0 |
| 14 | 13 | 1.74274 | 0 | 0 | -0.020513 | 1 | 185.217 | 2 | 2 | 0 | 0 |
| 8 | 7 | 1.72774 | 0 | 0 | -0.0211501 | 1 | 7.61767 | 2 | 2 | 0 | 0 |
| 12 | 11 | 1.64384 | 0 | 0 | -0.0199027 | 1 | 13.9322 | 2 | 2 | -0.000401358 | 0 |

## Worst Temperature Rates

| stage_1based | dT_energy_raw_F_per_s | vflow_energy_predicted_dT_from_used_F_per_s | dT_raw_minus_vflow_predicted_F_per_s | stage_energy_balance_resid_BTUps | stage_energy_resid_over_heat_capacity_F_per_s | dominant_energy_term | dominant_energy_term_BTUps |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 12 | -0.000401358 | 0 | -0.000401358 | 3694.42 | 5.37011 | vflow_energy_numer_BTUps | 21515.4 |
| 2 | -4.93809e-06 | 0 | -4.93809e-06 | -1039.11 | -0.492423 | vflow_energy_V_in_term_BTUps | 19500.3 |
| 17 | 1.22479e-15 | 8.59385e-16 | 3.65409e-16 | 241.999 | 0.114333 | vflow_energy_V_in_term_BTUps | 14683.5 |
| 1 | 0 | nan | nan | nan | nan |  | nan |
| 3 | 0 | 0 | 0 | -518.312 | -0.379954 | vflow_energy_numer_BTUps | 20042.2 |
| 4 | 0 | 0 | 0 | -355.608 | -0.275854 | vflow_energy_numer_BTUps | 19960.1 |
| 5 | 0 | 0 | 0 | -297.323 | -0.242604 | vflow_energy_numer_BTUps | 20481.9 |
| 6 | 0 | 0 | 0 | -120.921 | -0.101863 | vflow_energy_numer_BTUps | 20286.5 |
| 7 | 0 | 0 | 0 | -32.1138 | -0.0275543 | vflow_energy_numer_BTUps | 20253.5 |
| 8 | 0 | 0 | 0 | 7.83261 | 0.00677923 | vflow_energy_V_in_term_BTUps | 20247.3 |
| 9 | 0 | 0 | 0 | 7.82411 | 0.00679152 | vflow_energy_numer_BTUps | 20265.7 |
| 10 | 0 | 0 | 0 | -23.3092 | -0.0202158 | vflow_energy_numer_BTUps | 20357.3 |

## Worst Temperature Equation Gaps

| stage_1based | dT_raw_minus_vflow_predicted_F_per_s | dT_energy_raw_F_per_s | vflow_energy_predicted_dT_from_used_F_per_s | vflow_energy_dT_target_F_per_s | vflow_energy_resid_after_used_BTUps |
|---:|---:|---:|---:|---:|---:|
| 12 | -0.000401358 | -0.000401358 | 0 | 0 | 0 |
| 2 | -4.93809e-06 | -4.93809e-06 | 0 | 0 | 0 |
| 17 | 3.65409e-16 | 1.22479e-15 | 8.59385e-16 | 0 | 1.81899e-12 |
| 3 | 0 | 0 | 0 | 0 | 0 |
| 4 | 0 | 0 | 0 | 0 | 0 |
| 5 | 0 | 0 | 0 | 0 | 0 |
| 6 | 0 | 0 | 0 | 0 | 0 |
| 7 | 0 | 0 | 0 | 0 | 0 |
| 8 | 0 | 0 | 0 | 0 | 0 |
| 9 | 0 | 0 | 0 | 0 | 0 |
| 10 | 0 | 0 | 0 | 0 | 0 |
| 11 | 0 | 0 | 0 | 0 | 0 |

## Worst Temperature/Vapor-Flow Term Gaps

| stage_1based | temp_energy_dE_minus_vflow_resid_BTUps | temp_energy_dE_BTUps | vflow_energy_resid_after_used_BTUps | temp_energy_L_in_term_BTUps | vflow_energy_L_in_term_BTUps | temp_energy_V_in_term_BTUps | vflow_energy_V_in_term_BTUps | temp_energy_V_out_term_BTUps | vflow_energy_numer_BTUps |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 12 | -0.171018 | -0.171018 | 0 | 460.197 | 460.197 | 14121.1 | 14121.1 | 21515.4 | 21515.4 |
| 2 | -0.00611675 | -0.00611675 | 0 | -279.048 | -279.042 | 19500.3 | 19500.3 | 19221.2 | 19221.2 |
| 3 | 0 | 0 | 0 | 259.766 | 259.766 | 19782.4 | 19782.4 | 20042.2 | 20042.2 |
| 4 | 0 | 0 | 0 | 83.2423 | 83.2423 | 19876.9 | 19876.9 | 19960.1 | 19960.1 |
| 5 | 0 | 0 | 0 | 278.943 | 278.943 | 20202.9 | 20202.9 | 20481.9 | 20481.9 |
| 6 | 0 | 0 | 0 | 38.6707 | 38.6707 | 20247.8 | 20247.8 | 20286.5 | 20286.5 |
| 7 | 0 | 0 | 0 | 2.63139 | 2.63139 | 20250.9 | 20250.9 | 20253.5 | 20253.5 |
| 8 | 0 | 0 | 0 | -3.13335 | -3.13335 | 20247.3 | 20247.3 | 20244.1 | 20244.1 |
| 9 | 0 | 0 | 0 | 8.47583 | 8.47583 | 20257.2 | 20257.2 | 20265.7 | 20265.7 |
| 10 | 0 | 0 | 0 | 45.9777 | 45.9777 | 20311.3 | 20311.3 | 20357.3 | 20357.3 |
| 11 | 0 | 0 | 0 | 161.478 | 161.478 | 20502.6 | 20502.6 | 20664.1 | 20664.1 |
| 13 | 0 | 0 | 0 | -1448.57 | -1448.57 | 14691.6 | 14691.6 | 13243 | 13243 |

## Top K Mismatches

| stage_1based | component | ln_K_state_over_K_thermo | K_state | K_thermo | y_state | y_eq |
|---:|---:|---:|---:|---:|---:|---:|
| 4 | n_Pentane | 1.22017 | 0.848592 | 0.250487 | 0.000453327 | 0.000129685 |
| 20 | n_Propane | 0.713389 | 2.0409 | 1 | 0.0967216 | 0.110223 |
| 20 | n_Pentane | -0.590851 | 0.553856 | 1 | 0.103663 | 0.0840153 |
| 3 | n_Pentane | 0.498932 | 0.360638 | 0.218972 | 7.45625e-05 | 3.8987e-05 |
| 12 | n_Propane | 0.481643 | 2.65849 | 1.64233 | 0.462994 | 0.483759 |
| 4 | n_Butane | 0.461513 | 0.894017 | 0.563525 | 0.363332 | 0.223975 |
| 4 | n_Propane | -0.183476 | 1.07276 | 1.2888 | 0.636215 | 0.775895 |
| 11 | n_Propane | 0.152356 | 1.86644 | 1.60268 | 0.507727 | 0.514106 |
| 12 | n_Pentane | -0.116435 | 0.330947 | 0.371814 | 0.040604 | 0.033669 |
| 6 | n_Propane | 0.0983186 | 1.60298 | 1.45288 | 0.622792 | 0.629097 |
| 5 | n_Propane | 0.0948826 | 1.52032 | 1.3827 | 0.684619 | 0.693723 |
| 7 | n_Propane | 0.0872005 | 1.63794 | 1.50116 | 0.579645 | 0.583761 |

## Top K Eq-Relax Mismatches

| stage_1based | component | ln_K_state_over_K_eq_relax | K_state | K_eq_relax | y_state | y_eq |
|---:|---:|---:|---:|---:|---:|---:|
| 4 | n_Pentane | 1.22017 | 0.848592 | 0.250487 | 0.000453327 | 0.000129685 |
| 20 | n_Propane | 0.713389 | 2.0409 | 1 | 0.0967216 | 0.110223 |
| 20 | n_Pentane | -0.590851 | 0.553856 | 1 | 0.103663 | 0.0840153 |
| 3 | n_Pentane | 0.498932 | 0.360638 | 0.218972 | 7.45625e-05 | 3.8987e-05 |
| 12 | n_Propane | 0.481643 | 2.65849 | 1.64233 | 0.462994 | 0.483759 |
| 4 | n_Butane | 0.461513 | 0.894017 | 0.563525 | 0.363332 | 0.223975 |
| 4 | n_Propane | -0.183476 | 1.07276 | 1.2888 | 0.636215 | 0.775895 |
| 11 | n_Propane | 0.152356 | 1.86644 | 1.60268 | 0.507727 | 0.514106 |
| 12 | n_Pentane | -0.116435 | 0.330947 | 0.371814 | 0.040604 | 0.033669 |
| 6 | n_Propane | 0.0983186 | 1.60298 | 1.45288 | 0.622792 | 0.629097 |
| 5 | n_Propane | 0.0948826 | 1.52032 | 1.3827 | 0.684619 | 0.693723 |
| 7 | n_Propane | 0.0872005 | 1.63794 | 1.50116 | 0.579645 | 0.583761 |

## Top Vapor Target Mismatches

| stage_1based | component | y_state_minus_y_target | y_state | y_target | y_eq |
|---:|---:|---:|---:|---:|---:|
| 1 | n_Propane | -0.905668 | 0 | 0.905668 | 0.905668 |
| 4 | n_Propane | -0.13968 | 0.636215 | 0.775895 | 0.775895 |
| 4 | n_Butane | 0.139356 | 0.363332 | 0.223975 | 0.223975 |
| 1 | n_Butane | -0.0943265 | 0 | 0.0943265 | 0.0943265 |
| 12 | n_Propane | -0.0207648 | 0.462994 | 0.483759 | 0.483759 |
| 3 | n_Propane | -0.0207607 | 0.842167 | 0.862928 | 0.862928 |
| 3 | n_Butane | 0.0207252 | 0.157758 | 0.137033 | 0.137033 |
| 20 | n_Pentane | 0.0196475 | 0.103663 | 0.0840153 | 0.0840153 |
| 12 | n_Butane | 0.0138297 | 0.496402 | 0.482572 | 0.482572 |
| 20 | n_Propane | -0.0135014 | 0.0967216 | 0.110223 | 0.110223 |
| 13 | n_Propane | 0.0129138 | 0.293136 | 0.280222 | 0.280222 |
| 5 | n_Propane | -0.00910406 | 0.684619 | 0.693723 | 0.693723 |

## Top Interior Vapor Target Mismatches

| stage_1based | component | y_state_minus_y_target | y_state | y_target | y_eq |
|---:|---:|---:|---:|---:|---:|
| 4 | n_Propane | -0.13968 | 0.636215 | 0.775895 | 0.775895 |
| 4 | n_Butane | 0.139356 | 0.363332 | 0.223975 | 0.223975 |
| 12 | n_Propane | -0.0207648 | 0.462994 | 0.483759 | 0.483759 |
| 3 | n_Propane | -0.0207607 | 0.842167 | 0.862928 | 0.862928 |
| 3 | n_Butane | 0.0207252 | 0.157758 | 0.137033 | 0.137033 |
| 12 | n_Butane | 0.0138297 | 0.496402 | 0.482572 | 0.482572 |
| 13 | n_Propane | 0.0129138 | 0.293136 | 0.280222 | 0.280222 |
| 5 | n_Propane | -0.00910406 | 0.684619 | 0.693723 | 0.693723 |
| 5 | n_Butane | 0.00902439 | 0.314949 | 0.305925 | 0.305925 |
| 13 | n_Butane | -0.00835346 | 0.626104 | 0.634457 | 0.634457 |
| 12 | n_Pentane | 0.00693508 | 0.040604 | 0.033669 | 0.033669 |
| 11 | n_Propane | -0.00637942 | 0.507727 | 0.514106 | 0.514106 |

