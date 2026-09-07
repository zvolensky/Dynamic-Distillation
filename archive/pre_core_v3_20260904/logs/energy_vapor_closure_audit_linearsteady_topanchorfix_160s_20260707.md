# Energy/Vapor Closure Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_liq_eq_vap_linearsteady_300s_topanchorfix_20260707\column_profile_20260707_203741.csv`
Time: `160 s`
Stage rows: `20`

## Summary

| Check | Value |
|---|---:|
| max \|V_calc - V_used\| lbmol/h | 0 |
| max \|relative V gap\| | 0 |
| max \|adjacent vapor enthalpy gap\| BTU/lbmol | 184.659 |
| max \|P_from_holdup - P\| psia | 222.62 |
| max \|energy P used - logged P\| psia | 0.000859086 |
| max \|ln(K_state/K_thermo)\| | 0.70978 |
| max \|ln(K_state/K_eq_relax)\| | 0.70978 |
| max \|y_state - y_eq\| | 0.905668 |
| max \|y_state - y_target\| | 0.905668 |
| max \|y_state - y_target\| interior | 0.050312 |
| max \|dT_energy_raw\| F/s | 5.74962e-06 |
| max \|energy residual / heat capacity\| F/s | 6.08907 |
| max \|dT raw - vapor-flow predicted dT\| F/s | 5.74962e-06 |
| max \|temp dE - vapor-flow residual\| BTU/s | 0.0023743 |

## Diagnostic Interpretation

- equilibrium K-state mismatch
- vapor composition target mismatch

This report uses logged RHS diagnostics only. It does not recompute thermo or change vapor-flow closure.

## Top Composite Interfaces

| vapor_source_stage_1based | vapor_receiver_stage_1based | interface_inconsistency_score | V_calc_minus_used_lbmolph | relative_V_calc_minus_used | vflow_energy_P_used_minus_source_P_psia | vflow_energy_pressure_basis_code | source_minus_receiver_HV_BTU_per_lbmol | vflow_energy_hV_in_source_code | vflow_energy_hV_out_source_code | source_dT_energy_raw_F_per_s | receiver_dT_energy_raw_F_per_s |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | nan | 22.262 | nan | nan | nan | nan | nan | nan | nan | 0 | nan |
| 12 | 11 | 4.349 | 0 | 0 | -0.000283949 | 1 | -173.431 | 2 | 2 | -5.74962e-06 | 0 |
| 4 | 3 | 3.95249 | 0 | 0 | 0.000230507 | 1 | 40.16 | 2 | 2 | 0 | 0 |
| 3 | 2 | 3.92815 | 0 | 0 | 0.000223394 | 1 | 120.732 | 2 | 2 | 0 | 0 |
| 19 | 18 | 3.65916 | 0 | 0 | 9.9476e-13 | 1 | -98.3518 | 2 | 2 | 0 | 0 |
| 5 | 4 | 3.60635 | 0 | 0 | 0.000204727 | 1 | 29.0286 | 2 | 2 | 0 | 0 |
| 11 | 10 | 3.562 | 0 | 0 | 0.000175606 | 1 | 8.63352 | 2 | 2 | 0 | 0 |
| 10 | 9 | 3.38685 | 0 | 0 | 0.000101834 | 1 | 6.73627 | 2 | 2 | 0 | 0 |
| 6 | 5 | 3.33251 | 0 | 0 | 0.000188259 | 1 | 18.4947 | 2 | 2 | 0 | 0 |
| 9 | 8 | 3.25731 | 0 | 0 | 0.000105281 | 1 | 6.28743 | 2 | 2 | 0 | 0 |
| 14 | 13 | 3.2448 | 0 | 0 | -0.000584537 | 1 | 184.659 | 2 | 2 | 1.62792e-15 | 1.58135e-15 |
| 7 | 6 | 3.2263 | 0 | 0 | 0.000166906 | 1 | 11.4264 | 2 | 2 | 0 | 0 |

## Worst Temperature Rates

| stage_1based | dT_energy_raw_F_per_s | vflow_energy_predicted_dT_from_used_F_per_s | dT_raw_minus_vflow_predicted_F_per_s | stage_energy_balance_resid_BTUps | stage_energy_resid_over_heat_capacity_F_per_s | dominant_energy_term | dominant_energy_term_BTUps |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 12 | -5.74962e-06 | 0 | -5.74962e-06 | 3892.17 | 6.08907 | vflow_energy_numer_BTUps | 20889 |
| 14 | 1.62792e-15 | 1.10306e-15 | 5.2486e-16 | 833.236 | 0.505284 | vflow_energy_numer_BTUps | 14804.7 |
| 13 | 1.58135e-15 | 1.07498e-15 | 5.06371e-16 | 978.653 | 0.578359 | vflow_energy_V_in_term_BTUps | 14640.9 |
| 1 | 0 | nan | nan | nan | nan |  | nan |
| 2 | 0 | 0 | 0 | -1295.84 | -0.561399 | vflow_energy_V_in_term_BTUps | 19837.4 |
| 3 | 0 | 0 | 0 | -518.244 | -0.337246 | vflow_energy_numer_BTUps | 20199.6 |
| 4 | 0 | 0 | 0 | -414.922 | -0.298337 | vflow_energy_numer_BTUps | 20543 |
| 5 | 0 | 0 | 0 | -296.685 | -0.234324 | vflow_energy_numer_BTUps | 20627.8 |
| 6 | 0 | 0 | 0 | -179.13 | -0.15013 | vflow_energy_numer_BTUps | 20583.2 |
| 7 | 0 | 0 | 0 | -92.3066 | -0.0797292 | vflow_energy_numer_BTUps | 20550 |
| 8 | 0 | 0 | 0 | -37.6785 | -0.0328744 | vflow_energy_V_in_term_BTUps | 20543.7 |
| 9 | 0 | 0 | 0 | -17.1926 | -0.0149547 | vflow_energy_numer_BTUps | 20580.4 |

## Worst Temperature Equation Gaps

| stage_1based | dT_raw_minus_vflow_predicted_F_per_s | dT_energy_raw_F_per_s | vflow_energy_predicted_dT_from_used_F_per_s | vflow_energy_dT_target_F_per_s | vflow_energy_resid_after_used_BTUps |
|---:|---:|---:|---:|---:|---:|
| 12 | -5.74962e-06 | -5.74962e-06 | 0 | 0 | 0 |
| 14 | 5.2486e-16 | 1.62792e-15 | 1.10306e-15 | 0 | 1.81899e-12 |
| 13 | 5.06371e-16 | 1.58135e-15 | 1.07498e-15 | 0 | 1.81899e-12 |
| 2 | 0 | 0 | 0 | 0 | 0 |
| 3 | 0 | 0 | 0 | 0 | 0 |
| 4 | 0 | 0 | 0 | 0 | 0 |
| 5 | 0 | 0 | 0 | 0 | 0 |
| 6 | 0 | 0 | 0 | 0 | 0 |
| 7 | 0 | 0 | 0 | 0 | 0 |
| 8 | 0 | 0 | 0 | 0 | 0 |
| 9 | 0 | 0 | 0 | 0 | 0 |
| 10 | 0 | 0 | 0 | 0 | 0 |

## Worst Temperature/Vapor-Flow Term Gaps

| stage_1based | temp_energy_dE_minus_vflow_resid_BTUps | temp_energy_dE_BTUps | vflow_energy_resid_after_used_BTUps | temp_energy_L_in_term_BTUps | vflow_energy_L_in_term_BTUps | temp_energy_V_in_term_BTUps | vflow_energy_V_in_term_BTUps | temp_energy_V_out_term_BTUps | vflow_energy_numer_BTUps |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 12 | -0.0023743 | -0.0023743 | 0 | 27.4477 | 27.4477 | 14504.1 | 14504.1 | 20889 | 20889 |
| 2 | 0 | 0 | 0 | -249.183 | -249.183 | 19837.4 | 19837.4 | 19588.2 | 19588.2 |
| 3 | 0 | 0 | 0 | 171.347 | 171.347 | 20028.3 | 20028.3 | 20199.6 | 20199.6 |
| 4 | 0 | 0 | 0 | 237.357 | 237.357 | 20305.6 | 20305.6 | 20543 | 20543 |
| 5 | 0 | 0 | 0 | 147.019 | 147.019 | 20480.8 | 20480.8 | 20627.8 | 20627.8 |
| 6 | 0 | 0 | 0 | 46.5848 | 46.5848 | 20536.6 | 20536.6 | 20583.2 | 20583.2 |
| 7 | 0 | 0 | 0 | 6.08572 | 6.08572 | 20543.9 | 20543.9 | 20550 | 20550 |
| 8 | 0 | 0 | 0 | -0.186168 | -0.186168 | 20543.7 | 20543.7 | 20543.5 | 20543.5 |
| 9 | 0 | 0 | 0 | 16.5986 | 16.5986 | 20563.8 | 20563.8 | 20580.4 | 20580.4 |
| 10 | 0 | 0 | 0 | 86.8538 | 86.8538 | 20668.9 | 20668.9 | 20755.8 | 20755.8 |
| 11 | 0 | 0 | 0 | 130.656 | 130.656 | 20827.7 | 20827.7 | 20958.4 | 20958.4 |
| 13 | 0 | 1.81899e-12 | 1.81899e-12 | -393.124 | -393.124 | 14640.9 | 14640.9 | 14247.8 | 14247.8 |

## Top K Mismatches

| stage_1based | component | ln_K_state_over_K_thermo | K_state | K_thermo | y_state | y_eq |
|---:|---:|---:|---:|---:|---:|---:|
| 20 | n_Propane | 0.70978 | 2.03354 | 1 | 0.0881613 | 0.110223 |
| 20 | n_Pentane | -0.59446 | 0.551861 | 1 | 0.0947005 | 0.0840153 |
| 3 | n_Pentane | 0.425405 | 0.335071 | 0.218971 | 8.09337e-05 | 4.70602e-05 |
| 19 | n_Propane | 0.300921 | 1.3511 | 1 | 0.0966117 | 0.0755488 |
| 12 | n_Propane | 0.274334 | 1.31565 | 1 | 0.35053 | 0.300218 |
| 12 | n_Pentane | -0.265675 | 0.766688 | 1 | 0.0733285 | 0.0866781 |
| 19 | n_Pentane | -0.196817 | 0.821341 | 1 | 0.101259 | 0.119738 |
| 4 | n_Pentane | 0.138652 | 0.287738 | 0.250485 | 0.00020208 | 0.000153472 |
| 11 | n_Propane | 0.137954 | 1.83977 | 1.6027 | 0.500055 | 0.5146 |
| 12 | n_Butane | -0.10187 | 0.903147 | 1 | 0.576141 | 0.613104 |
| 9 | n_Pentane | 0.0920453 | 0.374319 | 0.341403 | 0.00760589 | 0.00657705 |
| 10 | n_Propane | 0.0907107 | 1.72885 | 1.57892 | 0.519267 | 0.524137 |

## Top K Eq-Relax Mismatches

| stage_1based | component | ln_K_state_over_K_eq_relax | K_state | K_eq_relax | y_state | y_eq |
|---:|---:|---:|---:|---:|---:|---:|
| 20 | n_Propane | 0.70978 | 2.03354 | 1 | 0.0881613 | 0.110223 |
| 20 | n_Pentane | -0.59446 | 0.551861 | 1 | 0.0947005 | 0.0840153 |
| 3 | n_Pentane | 0.425405 | 0.335071 | 0.218971 | 8.09337e-05 | 4.70602e-05 |
| 19 | n_Propane | 0.300921 | 1.3511 | 1 | 0.0966117 | 0.0755488 |
| 12 | n_Propane | 0.274334 | 1.31565 | 1 | 0.35053 | 0.300218 |
| 12 | n_Pentane | -0.265675 | 0.766688 | 1 | 0.0733285 | 0.0866781 |
| 19 | n_Pentane | -0.196817 | 0.821341 | 1 | 0.101259 | 0.119738 |
| 4 | n_Pentane | 0.138652 | 0.287738 | 0.250485 | 0.00020208 | 0.000153472 |
| 11 | n_Propane | 0.137954 | 1.83977 | 1.6027 | 0.500055 | 0.5146 |
| 12 | n_Butane | -0.10187 | 0.903147 | 1 | 0.576141 | 0.613104 |
| 9 | n_Pentane | 0.0920453 | 0.374319 | 0.341403 | 0.00760589 | 0.00657705 |
| 10 | n_Propane | 0.0907107 | 1.72885 | 1.57892 | 0.519267 | 0.524137 |

## Top Vapor Target Mismatches

| stage_1based | component | y_state_minus_y_target | y_state | y_target | y_eq |
|---:|---:|---:|---:|---:|---:|
| 1 | n_Propane | -0.905668 | 0 | 0.905668 | 0.905668 |
| 1 | n_Butane | -0.0943265 | 0 | 0.0943265 | 0.0943265 |
| 12 | n_Propane | 0.050312 | 0.35053 | 0.300218 | 0.300218 |
| 12 | n_Butane | -0.0369624 | 0.576141 | 0.613104 | 0.613104 |
| 3 | n_Propane | -0.0238279 | 0.840489 | 0.864317 | 0.864317 |
| 3 | n_Butane | 0.023794 | 0.15943 | 0.135636 | 0.135636 |
| 20 | n_Propane | -0.0220618 | 0.0881613 | 0.110223 | 0.110223 |
| 19 | n_Propane | 0.0210628 | 0.0966117 | 0.0755488 | 0.0755488 |
| 19 | n_Pentane | -0.018479 | 0.101259 | 0.119738 | 0.119738 |
| 11 | n_Propane | -0.0145453 | 0.500055 | 0.5146 | 0.5146 |
| 13 | n_Propane | 0.0133877 | 0.293316 | 0.279928 | 0.279928 |
| 12 | n_Pentane | -0.0133496 | 0.0733285 | 0.0866781 | 0.0866781 |

## Top Interior Vapor Target Mismatches

| stage_1based | component | y_state_minus_y_target | y_state | y_target | y_eq |
|---:|---:|---:|---:|---:|---:|
| 12 | n_Propane | 0.050312 | 0.35053 | 0.300218 | 0.300218 |
| 12 | n_Butane | -0.0369624 | 0.576141 | 0.613104 | 0.613104 |
| 3 | n_Propane | -0.0238279 | 0.840489 | 0.864317 | 0.864317 |
| 3 | n_Butane | 0.023794 | 0.15943 | 0.135636 | 0.135636 |
| 19 | n_Propane | 0.0210628 | 0.0966117 | 0.0755488 | 0.0755488 |
| 19 | n_Pentane | -0.018479 | 0.101259 | 0.119738 | 0.119738 |
| 11 | n_Propane | -0.0145453 | 0.500055 | 0.5146 | 0.5146 |
| 13 | n_Propane | 0.0133877 | 0.293316 | 0.279928 | 0.279928 |
| 12 | n_Pentane | -0.0133496 | 0.0733285 | 0.0866781 | 0.0866781 |
| 4 | n_Propane | -0.0132318 | 0.762716 | 0.775948 | 0.775948 |
| 4 | n_Butane | 0.0131832 | 0.237082 | 0.223898 | 0.223898 |
| 5 | n_Propane | -0.0100764 | 0.683752 | 0.693829 | 0.693829 |

