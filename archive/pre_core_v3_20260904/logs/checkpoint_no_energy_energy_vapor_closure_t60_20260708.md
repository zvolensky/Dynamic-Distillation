# Energy/Vapor Closure Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\checkpoint_no_energy_reload_60s_20260708\column_profile_20260708_140811.csv`
Time: `60 s`
Stage rows: `20`

## Summary

| Check | Value |
|---|---:|
| max \|V_calc - V_used\| lbmol/h | 0 |
| max \|relative V gap\| | 0 |
| max \|adjacent vapor enthalpy gap\| BTU/lbmol | 319.191 |
| max \|P_from_holdup - P\| psia | 322.905 |
| max \|energy P used - logged P\| psia | 0.00027827 |
| max \|ln(K_state/K_thermo)\| | 1.99758 |
| max \|ln(K_state/K_eq_relax)\| | nan |
| max \|y_state - y_eq\| | nan |
| max \|y_state - y_target\| | nan |
| max \|y_state - y_target\| interior | nan |
| max \|dT_energy_raw\| F/s | 1.38752e-08 |
| max \|energy residual / heat capacity\| F/s | nan |
| max \|dT raw - vapor-flow predicted dT\| F/s | 1.38752e-08 |
| max \|temp dE - vapor-flow residual\| BTU/s | 3.75739e-05 |

## Diagnostic Interpretation

- adjacent vapor enthalpy discontinuity
- equilibrium K-state mismatch

This report uses logged RHS diagnostics only. It does not recompute thermo or change vapor-flow closure.

## Top Composite Interfaces

| vapor_source_stage_1based | vapor_receiver_stage_1based | interface_inconsistency_score | V_calc_minus_used_lbmolph | relative_V_calc_minus_used | vflow_energy_P_used_minus_source_P_psia | vflow_energy_pressure_basis_code | source_minus_receiver_HV_BTU_per_lbmol | vflow_energy_hV_in_source_code | vflow_energy_hV_out_source_code | source_dT_energy_raw_F_per_s | receiver_dT_energy_raw_F_per_s |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 15 | 14 | 32.3027 | 0 | 0 | -9.46481e-05 | 1 | 122.296 | 2 | 2 | 0 | 0 |
| 12 | 11 | 31.5689 | 0 | 0 | -0.000151547 | 1 | 92.9775 | 2 | 2 | 0 | 0 |
| 19 | 18 | 31.4941 | 0 | 0 | 0 | 1 | 159.351 | 2 | 2 | 0 | 0 |
| 14 | 13 | 31.2111 | 0 | 0 | -0.000113884 | 1 | 104.979 | 2 | 2 | 0 | 0 |
| 13 | 12 | 30.7698 | 0 | 0 | -0.000132687 | 1 | 90.1148 | 2 | 2 | 0 | 0 |
| 11 | 10 | 30.0942 | 0 | 0 | -0.000160014 | 1 | 62.0097 | 2 | 2 | 0 | 0 |
| 18 | 17 | 30.082 | 0 | 0 | -2.38906e-05 | 1 | 147.324 | 2 | 2 | 0 | 0 |
| 10 | 9 | 29.9481 | 0 | 0 | -0.000173985 | 1 | 55.086 | 2 | 2 | 0 | 0 |
| 9 | 8 | 29.8753 | 0 | 0 | -0.000188046 | 1 | 65.1915 | 2 | 2 | 0 | 0 |
| 17 | 16 | 29.5607 | 0 | 0 | -4.81189e-05 | 1 | 142.188 | 2 | 2 | 0 | 0 |
| 8 | 7 | 29.4515 | 0 | 0 | -0.00020204 | 1 | 83.908 | 2 | 2 | 0 | 0 |
| 7 | 6 | 29.3661 | 0 | 0 | -0.000213621 | 1 | 122.26 | 2 | 2 | 0 | 0 |

## Worst Temperature Rates

| stage_1based | dT_energy_raw_F_per_s | vflow_energy_predicted_dT_from_used_F_per_s | dT_raw_minus_vflow_predicted_F_per_s | stage_energy_balance_resid_BTUps | stage_energy_resid_over_heat_capacity_F_per_s | dominant_energy_term | dominant_energy_term_BTUps |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 | -1.38752e-08 | 0 | -1.38752e-08 | nan | nan | vflow_energy_V_in_term_BTUps | 9710.79 |
| 1 | 0 | nan | nan | nan | nan |  | nan |
| 3 | 0 | 0 | 0 | nan | nan | vflow_energy_V_in_term_BTUps | 9747.79 |
| 4 | 0 | 0 | 0 | nan | nan | vflow_energy_V_in_term_BTUps | 9748.45 |
| 5 | 0 | 0 | 0 | nan | nan | vflow_energy_V_in_term_BTUps | 9732.95 |
| 6 | 0 | 0 | 0 | nan | nan | vflow_energy_V_in_term_BTUps | 9715.99 |
| 7 | 0 | 0 | 0 | nan | nan | vflow_energy_V_in_term_BTUps | 9702.65 |
| 8 | 0 | 0 | 0 | nan | nan | vflow_energy_V_in_term_BTUps | 9693.18 |
| 9 | 0 | 0 | 0 | nan | nan | vflow_energy_V_in_term_BTUps | 9680.13 |
| 10 | 0 | 0 | 0 | nan | nan | vflow_energy_V_in_term_BTUps | 9668 |
| 11 | 0 | 0 | 0 | nan | nan | vflow_energy_V_in_term_BTUps | 9652.95 |
| 12 | 0 | 0 | 0 | nan | nan | vflow_energy_V_in_term_BTUps | 10330.8 |

## Worst Temperature Equation Gaps

| stage_1based | dT_raw_minus_vflow_predicted_F_per_s | dT_energy_raw_F_per_s | vflow_energy_predicted_dT_from_used_F_per_s | vflow_energy_dT_target_F_per_s | vflow_energy_resid_after_used_BTUps |
|---:|---:|---:|---:|---:|---:|
| 2 | -1.38752e-08 | -1.38752e-08 | 0 | 0 | 0 |
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
| 2 | -3.75739e-05 | -3.75739e-05 | 0 | -596.21 | -596.21 | 9710.79 | 9710.79 | 9114.58 | 9114.58 |
| 3 | 0 | 0 | 0 | -621.642 | -621.642 | 9747.79 | 9747.79 | 9126.15 | 9126.15 |
| 4 | 0 | 0 | 0 | -501.168 | -501.168 | 9748.45 | 9748.45 | 9247.28 | 9247.28 |
| 5 | 0 | 0 | 0 | -392.125 | -392.125 | 9732.95 | 9732.95 | 9340.83 | 9340.83 |
| 6 | 0 | 0 | 0 | -256.172 | -256.172 | 9715.99 | 9715.99 | 9459.82 | 9459.82 |
| 7 | 0 | 0 | 0 | -168.233 | -168.233 | 9702.65 | 9702.65 | 9534.42 | 9534.42 |
| 8 | 0 | 0 | 0 | -110.324 | -110.324 | 9693.18 | 9693.18 | 9582.86 | 9582.86 |
| 9 | 0 | 0 | 0 | -147.308 | -147.308 | 9680.13 | 9680.13 | 9532.82 | 9532.82 |
| 10 | 0 | 0 | 0 | -122.255 | -122.255 | 9668 | 9668 | 9545.75 | 9545.75 |
| 11 | 0 | 0 | 0 | -137.224 | -137.224 | 9652.95 | 9652.95 | 9515.72 | 9515.72 |
| 12 | 0 | 0 | 0 | 68.963 | 68.963 | 10330.8 | 10330.8 | 9730.51 | 9730.51 |
| 13 | 0 | 0 | 0 | -363.605 | -363.605 | 10518.8 | 10518.8 | 10155.2 | 10155.2 |

## Top K Mismatches

| stage_1based | component | ln_K_state_over_K_thermo | K_state | K_thermo | y_state | y_eq |
|---:|---:|---:|---:|---:|---:|---:|
| 2 | n_Pentane | 1.99758 | 2.02467 | 0.274673 | 0.0535701 | nan |
| 3 | n_Pentane | 1.97846 | 2.06395 | 0.285406 | 0.0533205 | nan |
| 4 | n_Pentane | 1.89192 | 2.03258 | 0.306477 | 0.0531099 | nan |
| 5 | n_Pentane | 1.80272 | 1.98608 | 0.327405 | 0.0529157 | nan |
| 6 | n_Pentane | 1.72053 | 1.94202 | 0.347567 | 0.0527394 | nan |
| 7 | n_Pentane | 1.65976 | 1.90148 | 0.36163 | 0.0525811 | nan |
| 8 | n_Pentane | 1.61317 | 1.86308 | 0.371227 | 0.0524398 | nan |
| 9 | n_Pentane | 1.58469 | 1.82573 | 0.374297 | 0.0523131 | nan |
| 10 | n_Pentane | 1.55754 | 1.78873 | 0.376803 | 0.0521996 | nan |
| 11 | n_Pentane | 1.52942 | 1.75203 | 0.379599 | 0.0520981 | nan |
| 2 | n_Butane | 0.881368 | 1.30653 | 0.541186 | 0.470055 | nan |
| 3 | n_Butane | 0.866755 | 1.3145 | 0.552501 | 0.46517 | nan |

## Top K Eq-Relax Mismatches

No finite records.

## Top Vapor Target Mismatches

No finite records.

## Top Interior Vapor Target Mismatches

No finite records.

