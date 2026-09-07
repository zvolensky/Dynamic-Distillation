# Energy/Vapor Closure Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_provenance_columns_smoke_20260707\column_profile_20260707_092830.csv`
Time: `0.2 s`
Stage rows: `20`

## Summary

| Check | Value |
|---|---:|
| max \|V_calc - V_used\| lbmol/h | 1189.97 |
| max \|relative V gap\| | 0.1681 |
| max \|adjacent vapor enthalpy gap\| BTU/lbmol | 108.179 |
| max \|P_from_holdup - P\| psia | 222.62 |
| max \|energy P used - logged P\| psia | 0.00844741 |
| max \|ln(K_state/K_thermo)\| | 0.719572 |
| max \|y_state - y_eq\| | 0.905668 |
| max \|dT_energy_raw\| F/s | 0.464816 |
| max \|energy residual / heat capacity\| F/s | 2.00576 |

## Diagnostic Interpretation

- temperature-rate spike
- equilibrium K-state mismatch

This report uses logged RHS diagnostics only. It does not recompute thermo or change vapor-flow closure.

## Top Composite Interfaces

| vapor_source_stage_1based | vapor_receiver_stage_1based | interface_inconsistency_score | V_calc_minus_used_lbmolph | relative_V_calc_minus_used | vflow_energy_P_used_minus_source_P_psia | vflow_energy_pressure_basis_code | source_minus_receiver_HV_BTU_per_lbmol | vflow_energy_hV_in_source_code | vflow_energy_hV_out_source_code | source_dT_energy_raw_F_per_s | receiver_dT_energy_raw_F_per_s |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | nan | 22.262 | nan | nan | nan | nan | nan | nan | nan | 0 | nan |
| 3 | 2 | 0.936834 | 3.94218 | 0.000453781 | -0.00183223 | 1 | 108.179 | 1 | 1 | -0.193507 | 0.464816 |
| 2 | 1 | 0.871263 | 1189.97 | 0.1681 | -0.000550296 | 1 | 39.4512 | 1 | 1 | 0.464816 | 0 |
| 19 | 18 | 0.849692 | 128.034 | 0.0168604 | -0.00053929 | 1 | 6.31204 | 1 | 1 | 0.271837 | 0.245633 |
| 18 | 17 | 0.77925 | 144.201 | 0.0200571 | -0.000908838 | 1 | 3.77399 | 1 | 1 | 0.245633 | 0.213869 |
| 17 | 16 | 0.623815 | 104.335 | 0.0152479 | -0.00169485 | 1 | 3.71331 | 1 | 1 | 0.213869 | 0.11762 |
| 20 | 19 | 0.593694 | nan | nan | nan | nan | -13.1048 | nan | nan | 0 | 0.271837 |
| 4 | 3 | 0.574949 | -76.4957 | -0.00906556 | -0.00296418 | 1 | 40.1493 | 1 | 1 | -0.130837 | -0.193507 |

## Worst Temperature Rates

| stage_1based | dT_energy_raw_F_per_s | stage_energy_balance_resid_BTUps | stage_energy_resid_over_heat_capacity_F_per_s | dominant_energy_term | dominant_energy_term_BTUps |
|---:|---:|---:|---:|---:|---:|
| 2 | 0.464816 | 3962.09 | 2.00576 | vflow_energy_V_in_term_BTUps | 14195.7 |
| 19 | 0.271837 | 272.797 | 0.132212 | vflow_energy_V_in_term_BTUps | 14702.6 |
| 18 | 0.245633 | 135.819 | 0.064238 | vflow_energy_V_in_term_BTUps | 13891.5 |
| 17 | 0.213869 | 35.0788 | 0.0161587 | vflow_energy_V_in_term_BTUps | 13127.8 |
| 12 | 0.206191 | -612.371 | -0.348664 | vflow_energy_V_in_term_BTUps | 11869.2 |
| 3 | -0.193507 | 450.476 | 0.353906 | vflow_energy_numer_BTUps | 14428.2 |
| 6 | -0.185335 | 58.1468 | 0.0490605 | vflow_energy_numer_BTUps | 13371 |
| 5 | -0.174889 | 148.081 | 0.122819 | vflow_energy_numer_BTUps | 13860.9 |

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

