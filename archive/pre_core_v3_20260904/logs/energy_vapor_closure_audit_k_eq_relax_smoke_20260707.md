# Energy/Vapor Closure Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_k_eq_relax_smoke_20260707\column_profile_20260707_093902.csv`
Time: `0.2 s`
Stage rows: `20`

## Summary

| Check | Value |
|---|---:|
| max \|V_calc - V_used\| lbmol/h | 1187.6 |
| max \|relative V gap\| | 0.167766 |
| max \|adjacent vapor enthalpy gap\| BTU/lbmol | 108.179 |
| max \|P_from_holdup - P\| psia | 222.62 |
| max \|energy P used - logged P\| psia | 0.0084519 |
| max \|ln(K_state/K_thermo)\| | 0.719572 |
| max \|ln(K_state/K_eq_relax)\| | 0.719572 |
| max \|y_state - y_eq\| | 0.905668 |
| max \|y_state - y_target\| | 0.905668 |
| max \|y_state - y_target\| interior | 0.0402962 |
| max \|dT_energy_raw\| F/s | 0.464801 |
| max \|energy residual / heat capacity\| F/s | 2.00575 |

## Diagnostic Interpretation

- temperature-rate spike
- equilibrium K-state mismatch

This report uses logged RHS diagnostics only. It does not recompute thermo or change vapor-flow closure.

## Top Composite Interfaces

| vapor_source_stage_1based | vapor_receiver_stage_1based | interface_inconsistency_score | V_calc_minus_used_lbmolph | relative_V_calc_minus_used | vflow_energy_P_used_minus_source_P_psia | vflow_energy_pressure_basis_code | source_minus_receiver_HV_BTU_per_lbmol | vflow_energy_hV_in_source_code | vflow_energy_hV_out_source_code | source_dT_energy_raw_F_per_s | receiver_dT_energy_raw_F_per_s |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | nan | 22.262 | nan | nan | nan | nan | nan | nan | nan | 0 | nan |
| 3 | 2 | 0.936314 | -0.0338709 | -3.89889e-06 | -0.00183235 | 1 | 108.179 | 2 | 2 | -0.193451 | 0.464801 |
| 2 | 1 | 0.870914 | 1187.6 | 0.167766 | -0.000550296 | 1 | 39.4512 | 2 | 2 | 0.464801 | 0 |
| 19 | 18 | 0.85269 | 150.186 | 0.0197766 | -0.00053929 | 1 | 6.31204 | 2 | 2 | 0.271677 | 0.245874 |
| 18 | 17 | 0.777826 | 132.324 | 0.0184056 | -0.00090873 | 1 | 3.77399 | 2 | 2 | 0.245874 | 0.213855 |
| 17 | 16 | 0.622722 | 94.3509 | 0.0137891 | -0.00169408 | 1 | 3.71331 | 2 | 2 | 0.213855 | 0.118 |
| 20 | 19 | 0.593535 | nan | nan | nan | nan | -13.1048 | nan | nan | 0 | 0.271677 |
| 4 | 3 | 0.574852 | -75.9676 | -0.00900297 | -0.00296435 | 1 | 40.1493 | 2 | 2 | -0.130858 | -0.193451 |

## Worst Temperature Rates

| stage_1based | dT_energy_raw_F_per_s | stage_energy_balance_resid_BTUps | stage_energy_resid_over_heat_capacity_F_per_s | dominant_energy_term | dominant_energy_term_BTUps |
|---:|---:|---:|---:|---:|---:|
| 2 | 0.464801 | 3962.08 | 2.00575 | vflow_energy_V_in_term_BTUps | 14193.2 |
| 19 | 0.271677 | 272.562 | 0.132098 | vflow_energy_V_in_term_BTUps | 14662.8 |
| 18 | 0.245874 | 136.179 | 0.0644081 | vflow_energy_V_in_term_BTUps | 13801.6 |
| 17 | 0.213855 | 35.0587 | 0.0161494 | vflow_energy_V_in_term_BTUps | 13052.6 |
| 12 | 0.205221 | -613.5 | -0.349307 | vflow_energy_V_in_term_BTUps | 12002.6 |
| 3 | -0.193451 | 450.521 | 0.353942 | vflow_energy_numer_BTUps | 14410.9 |
| 6 | -0.185335 | 58.1468 | 0.0490604 | vflow_energy_numer_BTUps | 13351.1 |
| 5 | -0.174886 | 148.082 | 0.12282 | vflow_energy_numer_BTUps | 13842.9 |

## Top K Mismatches

| stage_1based | component | ln_K_state_over_K_thermo | K_state | K_thermo | y_state | y_eq |
|---:|---:|---:|---:|---:|---:|---:|
| 2 | n_Pentane | -0.719572 | 0.48696 | 1 | 1.13394e-05 | 1.70692e-05 |
| 20 | n_Propane | -0.689303 | 1 | 1.99233 | 0.157483 | 0.110223 |
| 20 | n_Pentane | 0.613094 | 1 | 0.541672 | 0.086019 | 0.0840153 |
| 19 | n_Propane | -0.597574 | 1.07626 | 1.95631 | 0.169491 | 0.171781 |
| 19 | n_Pentane | 0.565517 | 0.900735 | 0.511677 | 0.0774803 | 0.0742324 |
| 18 | n_Propane | -0.378225 | 1.30223 | 1.90085 | 0.207481 | 0.218988 |
| 3 | n_Butane | 0.361917 | 0.727145 | 0.50634 | 0.175798 | 0.135504 |
| 18 | n_Pentane | 0.346904 | 0.686373 | 0.485179 | 0.063014 | 0.0569439 |

## Top K Eq-Relax Mismatches

| stage_1based | component | ln_K_state_over_K_eq_relax | K_state | K_eq_relax | y_state | y_eq |
|---:|---:|---:|---:|---:|---:|---:|
| 2 | n_Pentane | -0.719572 | 0.48696 | 1 | 1.13394e-05 | 1.70692e-05 |
| 20 | n_Propane | -0.689303 | 1 | 1.99233 | 0.157483 | 0.110223 |
| 20 | n_Pentane | 0.613094 | 1 | 0.541672 | 0.086019 | 0.0840153 |
| 19 | n_Propane | -0.597574 | 1.07626 | 1.95631 | 0.169491 | 0.171781 |
| 19 | n_Pentane | 0.565517 | 0.900735 | 0.511677 | 0.0774803 | 0.0742324 |
| 18 | n_Propane | -0.378225 | 1.30223 | 1.90085 | 0.207481 | 0.218988 |
| 3 | n_Butane | 0.361917 | 0.727145 | 0.50634 | 0.175798 | 0.135504 |
| 18 | n_Pentane | 0.346904 | 0.686373 | 0.485179 | 0.063014 | 0.0569439 |

## Top Vapor Target Mismatches

| stage_1based | component | y_state_minus_y_target | y_state | y_target | y_eq |
|---:|---:|---:|---:|---:|---:|
| 1 | n_Propane | -0.905668 | 0 | 0.905668 | 0.905668 |
| 1 | n_Butane | -0.0943265 | 0 | 0.0943265 | 0.0943265 |
| 20 | n_Butane | -0.0492632 | 0.756498 | 0.805762 | 0.805762 |
| 20 | n_Propane | 0.0472595 | 0.157483 | 0.110223 | 0.110223 |
| 3 | n_Propane | -0.0402962 | 0.824176 | 0.864473 | 0.864473 |
| 3 | n_Butane | 0.0402937 | 0.175798 | 0.135504 | 0.135504 |
| 4 | n_Butane | 0.0334649 | 0.257354 | 0.223889 | 0.223889 |
| 4 | n_Propane | -0.0334619 | 0.742561 | 0.776023 | 0.776023 |

## Top Interior Vapor Target Mismatches

| stage_1based | component | y_state_minus_y_target | y_state | y_target | y_eq |
|---:|---:|---:|---:|---:|---:|
| 3 | n_Propane | -0.0402962 | 0.824176 | 0.864473 | 0.864473 |
| 3 | n_Butane | 0.0402937 | 0.175798 | 0.135504 | 0.135504 |
| 4 | n_Butane | 0.0334649 | 0.257354 | 0.223889 | 0.223889 |
| 4 | n_Propane | -0.0334619 | 0.742561 | 0.776023 | 0.776023 |
| 5 | n_Butane | 0.0242487 | 0.330144 | 0.305896 | 0.305896 |
| 5 | n_Propane | -0.0242285 | 0.669622 | 0.69385 | 0.69385 |
| 15 | n_Propane | -0.0204072 | 0.362908 | 0.383315 | 0.383315 |
| 14 | n_Propane | -0.0195357 | 0.410967 | 0.430503 | 0.430503 |

