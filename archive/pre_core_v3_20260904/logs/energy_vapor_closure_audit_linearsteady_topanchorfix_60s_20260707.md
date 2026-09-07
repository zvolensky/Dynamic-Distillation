# Energy/Vapor Closure Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_liq_eq_vap_linearsteady_60s_topanchorfix_20260707\column_profile_20260707_172502.csv`
Time: `60 s`
Stage rows: `20`

## Summary

| Check | Value |
|---|---:|
| max \|V_calc - V_used\| lbmol/h | 0 |
| max \|relative V gap\| | 0 |
| max \|adjacent vapor enthalpy gap\| BTU/lbmol | 107.265 |
| max \|P_from_holdup - P\| psia | 222.62 |
| max \|energy P used - logged P\| psia | 0.000226142 |
| max \|ln(K_state/K_thermo)\| | 0.713347 |
| max \|ln(K_state/K_eq_relax)\| | 0.713347 |
| max \|y_state - y_eq\| | 0.905668 |
| max \|y_state - y_target\| | 0.905668 |
| max \|y_state - y_target\| interior | 0.00941305 |
| max \|dT_energy_raw\| F/s | 2.41912e-15 |
| max \|energy residual / heat capacity\| F/s | 0.151997 |
| max \|dT raw - vapor-flow predicted dT\| F/s | 8.58522e-16 |
| max \|temp dE - vapor-flow residual\| BTU/s | 0 |

## Diagnostic Interpretation

- equilibrium K-state mismatch

This report uses logged RHS diagnostics only. It does not recompute thermo or change vapor-flow closure.

## Top Composite Interfaces

| vapor_source_stage_1based | vapor_receiver_stage_1based | interface_inconsistency_score | V_calc_minus_used_lbmolph | relative_V_calc_minus_used | vflow_energy_P_used_minus_source_P_psia | vflow_energy_pressure_basis_code | source_minus_receiver_HV_BTU_per_lbmol | vflow_energy_hV_in_source_code | vflow_energy_hV_out_source_code | source_dT_energy_raw_F_per_s | receiver_dT_energy_raw_F_per_s |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | nan | 22.262 | nan | nan | nan | nan | nan | nan | nan | 0 | nan |
| 3 | 2 | 2.01206 | 0 | 0 | -7.51322e-05 | 1 | 107.265 | 2 | 2 | 0 | -1.46846e-15 |
| 4 | 3 | 1.80517 | 0 | 0 | -0.000125015 | 1 | 40.1409 | 2 | 2 | 0 | 0 |
| 5 | 4 | 1.62983 | 0 | 0 | -0.000151633 | 1 | 28.9903 | 2 | 2 | -2.32684e-15 | 0 |
| 11 | 10 | 1.43593 | 0 | 0 | -0.000226142 | 1 | 8.3714 | 2 | 2 | 2.40842e-15 | 0 |
| 6 | 5 | 1.43586 | 0 | 0 | -0.000164994 | 1 | 18.4205 | 2 | 2 | -2.38819e-15 | -2.32684e-15 |
| 10 | 9 | 1.40117 | 0 | 0 | -0.000204739 | 1 | 6.17556 | 2 | 2 | 0 | 0 |
| 7 | 6 | 1.33192 | 0 | 0 | -0.000173113 | 1 | 11.2884 | 2 | 2 | -2.41912e-15 | -2.38819e-15 |
| 9 | 8 | 1.29183 | 0 | 0 | -0.000191061 | 1 | 5.89579 | 2 | 2 | 0 | 0 |
| 8 | 7 | 1.29058 | 0 | 0 | -0.000180756 | 1 | 7.39645 | 2 | 2 | 0 | -2.41912e-15 |
| 13 | 12 | 1.28226 | 0 | 0 | -0.000115026 | 1 | 4.56332 | 2 | 2 | 0 | 0 |
| 14 | 13 | 1.26052 | 0 | 0 | -6.70556e-05 | 1 | 4.87386 | 2 | 2 | 0 | 0 |

## Worst Temperature Rates

| stage_1based | dT_energy_raw_F_per_s | vflow_energy_predicted_dT_from_used_F_per_s | dT_raw_minus_vflow_predicted_F_per_s | stage_energy_balance_resid_BTUps | stage_energy_resid_over_heat_capacity_F_per_s | dominant_energy_term | dominant_energy_term_BTUps |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 7 | -2.41912e-15 | -1.56059e-15 | -8.58522e-16 | 60.1705 | 0.0516231 | vflow_energy_numer_BTUps | 14428.2 |
| 11 | 2.40842e-15 | 1.56942e-15 | 8.39001e-16 | -63.7538 | -0.0550068 | vflow_energy_numer_BTUps | 14534.5 |
| 6 | -2.38819e-15 | -1.53197e-15 | -8.56226e-16 | 35.4862 | 0.0298867 | vflow_energy_numer_BTUps | 14434.2 |
| 5 | -2.32684e-15 | -1.48286e-15 | -8.43979e-16 | -30.4506 | -0.0248237 | vflow_energy_numer_BTUps | 14447.5 |
| 2 | -1.46846e-15 | -8.63414e-16 | -6.05042e-16 | -160.962 | -0.0764032 | vflow_energy_V_in_term_BTUps | 14091.3 |
| 19 | 1.24207e-15 | 8.9336e-16 | 3.48708e-16 | 37.677 | 0.0185043 | vflow_energy_numer_BTUps | 14700 |
| 1 | 0 | nan | nan | nan | nan |  | nan |
| 3 | 0 | 0 | 0 | -207.872 | -0.151997 | vflow_energy_numer_BTUps | 14385.2 |
| 4 | 0 | 0 | 0 | -125.378 | -0.0969857 | vflow_energy_numer_BTUps | 14418.9 |
| 8 | 0 | 0 | 0 | 52.7188 | 0.0456224 | vflow_energy_numer_BTUps | 14431 |
| 9 | 0 | 0 | 0 | 25.8994 | 0.0224735 | vflow_energy_numer_BTUps | 14443.1 |
| 10 | 0 | 0 | 0 | -13.8615 | -0.0120181 | vflow_energy_numer_BTUps | 14506.9 |

## Worst Temperature Equation Gaps

| stage_1based | dT_raw_minus_vflow_predicted_F_per_s | dT_energy_raw_F_per_s | vflow_energy_predicted_dT_from_used_F_per_s | vflow_energy_dT_target_F_per_s | vflow_energy_resid_after_used_BTUps |
|---:|---:|---:|---:|---:|---:|
| 7 | -8.58522e-16 | -2.41912e-15 | -1.56059e-15 | 0 | -1.81899e-12 |
| 6 | -8.56226e-16 | -2.38819e-15 | -1.53197e-15 | 0 | -1.81899e-12 |
| 5 | -8.43979e-16 | -2.32684e-15 | -1.48286e-15 | 0 | -1.81899e-12 |
| 11 | 8.39001e-16 | 2.40842e-15 | 1.56942e-15 | 0 | 1.81899e-12 |
| 2 | -6.05042e-16 | -1.46846e-15 | -8.63414e-16 | 0 | -1.81899e-12 |
| 19 | 3.48708e-16 | 1.24207e-15 | 8.9336e-16 | 0 | 1.81899e-12 |
| 3 | 0 | 0 | 0 | 0 | 0 |
| 4 | 0 | 0 | 0 | 0 | 0 |
| 8 | 0 | 0 | 0 | 0 | 0 |
| 9 | 0 | 0 | 0 | 0 | 0 |
| 10 | 0 | 0 | 0 | 0 | 0 |
| 12 | 0 | 0 | 0 | 0 | 0 |

## Worst Temperature/Vapor-Flow Term Gaps

| stage_1based | temp_energy_dE_minus_vflow_resid_BTUps | temp_energy_dE_BTUps | vflow_energy_resid_after_used_BTUps | temp_energy_L_in_term_BTUps | vflow_energy_L_in_term_BTUps | temp_energy_V_in_term_BTUps | vflow_energy_V_in_term_BTUps | temp_energy_V_out_term_BTUps | vflow_energy_numer_BTUps |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 | 0 | -1.81899e-12 | -1.81899e-12 | -319.801 | -319.801 | 14091.3 | 14091.3 | 13771.5 | 13771.5 |
| 3 | 0 | 0 | 0 | 194.102 | 194.102 | 14191.1 | 14191.1 | 14385.2 | 14385.2 |
| 4 | 0 | 0 | 0 | 147.427 | 147.427 | 14271.5 | 14271.5 | 14418.9 | 14418.9 |
| 5 | 0 | -1.81899e-12 | -1.81899e-12 | 112.575 | 112.575 | 14334.9 | 14334.9 | 14447.5 | 14447.5 |
| 6 | 0 | -1.81899e-12 | -1.81899e-12 | 63.2876 | 63.2876 | 14370.9 | 14370.9 | 14434.2 | 14434.2 |
| 7 | 0 | -1.81899e-12 | -1.81899e-12 | 36.5738 | 36.5738 | 14391.6 | 14391.6 | 14428.2 | 14428.2 |
| 8 | 0 | 0 | 0 | 25.2 | 25.2 | 14405.8 | 14405.8 | 14431 | 14431 |
| 9 | 0 | 0 | 0 | 23.854 | 23.854 | 14419.3 | 14419.3 | 14443.1 | 14443.1 |
| 10 | 0 | 0 | 0 | 55.9786 | 55.9786 | 14451 | 14451 | 14506.9 | 14506.9 |
| 11 | 0 | 1.81899e-12 | 1.81899e-12 | 53.2085 | 53.2085 | 14481.2 | 14481.2 | 14534.5 | 14534.5 |
| 12 | 0 | 0 | 0 | 72.1514 | 72.1514 | 14682.3 | 14682.3 | 14595.4 | 14595.4 |
| 13 | 0 | 0 | 0 | 20.0726 | 20.0726 | 14675.3 | 14675.3 | 14695.4 | 14695.4 |

## Top K Mismatches

| stage_1based | component | ln_K_state_over_K_thermo | K_state | K_thermo | y_state | y_eq |
|---:|---:|---:|---:|---:|---:|---:|
| 20 | n_Propane | 0.713347 | 2.04081 | 1 | 0.0967827 | 0.110223 |
| 20 | n_Pentane | -0.590893 | 0.553833 | 1 | 0.103647 | 0.0840153 |
| 3 | n_Pentane | 0.224467 | 0.274078 | 0.218972 | 4.21988e-05 | 3.21737e-05 |
| 4 | n_Pentane | 0.188956 | 0.302587 | 0.250488 | 0.000136143 | 0.000113109 |
| 5 | n_Pentane | 0.160651 | 0.328969 | 0.280146 | 0.000353521 | 0.000306892 |
| 6 | n_Pentane | 0.134435 | 0.347476 | 0.303767 | 0.000796017 | 0.000708871 |
| 7 | n_Pentane | 0.111927 | 0.358776 | 0.320785 | 0.00162792 | 0.00147193 |
| 8 | n_Pentane | 0.0945417 | 0.36569 | 0.332701 | 0.0031201 | 0.0028478 |
| 9 | n_Pentane | 0.0821059 | 0.370727 | 0.341504 | 0.00572615 | 0.00525649 |
| 10 | n_Pentane | 0.0705824 | 0.374641 | 0.349109 | 0.0102233 | 0.00941213 |
| 11 | n_Pentane | 0.0617811 | 0.380426 | 0.357635 | 0.0179819 | 0.0166106 |
| 20 | n_Butane | 0.0436351 | 1.0446 | 1 | 0.79957 | 0.805762 |

## Top K Eq-Relax Mismatches

| stage_1based | component | ln_K_state_over_K_eq_relax | K_state | K_eq_relax | y_state | y_eq |
|---:|---:|---:|---:|---:|---:|---:|
| 20 | n_Propane | 0.713347 | 2.04081 | 1 | 0.0967827 | 0.110223 |
| 20 | n_Pentane | -0.590893 | 0.553833 | 1 | 0.103647 | 0.0840153 |
| 3 | n_Pentane | 0.224467 | 0.274078 | 0.218972 | 4.21988e-05 | 3.21737e-05 |
| 4 | n_Pentane | 0.188956 | 0.302587 | 0.250488 | 0.000136143 | 0.000113109 |
| 5 | n_Pentane | 0.160651 | 0.328969 | 0.280146 | 0.000353521 | 0.000306892 |
| 6 | n_Pentane | 0.134435 | 0.347476 | 0.303767 | 0.000796017 | 0.000708871 |
| 7 | n_Pentane | 0.111927 | 0.358776 | 0.320785 | 0.00162792 | 0.00147193 |
| 8 | n_Pentane | 0.0945417 | 0.36569 | 0.332701 | 0.0031201 | 0.0028478 |
| 9 | n_Pentane | 0.0821059 | 0.370727 | 0.341504 | 0.00572615 | 0.00525649 |
| 10 | n_Pentane | 0.0705824 | 0.374641 | 0.349109 | 0.0102233 | 0.00941213 |
| 11 | n_Pentane | 0.0617811 | 0.380426 | 0.357635 | 0.0179819 | 0.0166106 |
| 20 | n_Butane | 0.0436351 | 1.0446 | 1 | 0.79957 | 0.805762 |

## Top Vapor Target Mismatches

| stage_1based | component | y_state_minus_y_target | y_state | y_target | y_eq |
|---:|---:|---:|---:|---:|---:|
| 1 | n_Propane | -0.905668 | 0 | 0.905668 | 0.905668 |
| 1 | n_Butane | -0.0943265 | 0 | 0.0943265 | 0.0943265 |
| 20 | n_Pentane | 0.0196319 | 0.103647 | 0.0840153 | 0.0840153 |
| 20 | n_Propane | -0.0134403 | 0.0967827 | 0.110223 | 0.110223 |
| 3 | n_Propane | -0.00941305 | 0.854869 | 0.864282 | 0.864282 |
| 3 | n_Butane | 0.00940303 | 0.145088 | 0.135685 | 0.135685 |
| 4 | n_Propane | -0.00857844 | 0.767279 | 0.775858 | 0.775858 |
| 4 | n_Butane | 0.0085554 | 0.232585 | 0.224029 | 0.224029 |
| 5 | n_Propane | -0.00666501 | 0.68696 | 0.693625 | 0.693625 |
| 5 | n_Butane | 0.00661838 | 0.312687 | 0.306068 | 0.306068 |
| 20 | n_Butane | -0.00619166 | 0.79957 | 0.805762 | 0.805762 |
| 15 | n_Propane | -0.00553612 | 0.375068 | 0.380604 | 0.380604 |

## Top Interior Vapor Target Mismatches

| stage_1based | component | y_state_minus_y_target | y_state | y_target | y_eq |
|---:|---:|---:|---:|---:|---:|
| 3 | n_Propane | -0.00941305 | 0.854869 | 0.864282 | 0.864282 |
| 3 | n_Butane | 0.00940303 | 0.145088 | 0.135685 | 0.135685 |
| 4 | n_Propane | -0.00857844 | 0.767279 | 0.775858 | 0.775858 |
| 4 | n_Butane | 0.0085554 | 0.232585 | 0.224029 | 0.224029 |
| 5 | n_Propane | -0.00666501 | 0.68696 | 0.693625 | 0.693625 |
| 5 | n_Butane | 0.00661838 | 0.312687 | 0.306068 | 0.306068 |
| 15 | n_Propane | -0.00553612 | 0.375068 | 0.380604 | 0.380604 |
| 19 | n_Propane | -0.00520171 | 0.154644 | 0.159845 | 0.159845 |
| 15 | n_Butane | 0.00511868 | 0.587242 | 0.582124 | 0.582124 |
| 16 | n_Propane | -0.00508623 | 0.322007 | 0.327093 | 0.327093 |
| 17 | n_Propane | -0.00506781 | 0.265696 | 0.270764 | 0.270764 |
| 14 | n_Propane | -0.0050549 | 0.423551 | 0.428606 | 0.428606 |

