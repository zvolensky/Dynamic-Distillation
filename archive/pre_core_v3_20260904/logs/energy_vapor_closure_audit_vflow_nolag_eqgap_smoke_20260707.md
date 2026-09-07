# Energy/Vapor Closure Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_vflow_nolag_eqgap_smoke_20260707\column_profile_20260707_100035.csv`
Time: `0.2 s`
Stage rows: `20`

## Summary

| Check | Value |
|---|---:|
| max \|V_calc - V_used\| lbmol/h | 0 |
| max \|relative V gap\| | 0 |
| max \|adjacent vapor enthalpy gap\| BTU/lbmol | 109.542 |
| max \|P_from_holdup - P\| psia | 222.62 |
| max \|energy P used - logged P\| psia | 0.00489272 |
| max \|ln(K_state/K_thermo)\| | 0.719022 |
| max \|ln(K_state/K_eq_relax)\| | 0.719022 |
| max \|y_state - y_eq\| | 0.905668 |
| max \|y_state - y_target\| | 0.905668 |
| max \|y_state - y_target\| interior | 0.0402145 |
| max \|dT_energy_raw\| F/s | 0.523257 |
| max \|energy residual / heat capacity\| F/s | 1.42313 |
| max \|dT raw - vapor-flow predicted dT\| F/s | 0.257935 |

## Diagnostic Interpretation

- temperature-rate spike
- vapor-flow/temperature energy equation mismatch
- equilibrium K-state mismatch

This report uses logged RHS diagnostics only. It does not recompute thermo or change vapor-flow closure.

## Top Composite Interfaces

| vapor_source_stage_1based | vapor_receiver_stage_1based | interface_inconsistency_score | V_calc_minus_used_lbmolph | relative_V_calc_minus_used | vflow_energy_P_used_minus_source_P_psia | vflow_energy_pressure_basis_code | source_minus_receiver_HV_BTU_per_lbmol | vflow_energy_hV_in_source_code | vflow_energy_hV_out_source_code | source_dT_energy_raw_F_per_s | receiver_dT_energy_raw_F_per_s |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | nan | 22.262 | nan | nan | nan | nan | nan | nan | nan | 0 | nan |
| 3 | 2 | 0.952991 | 0 | 0 | -0.000935813 | 1 | 109.542 | 2 | 2 | -0.164864 | -0.523257 |
| 2 | 1 | 0.81874 | 0 | 0 | -0.000550296 | 1 | 38.1343 | 2 | 2 | -0.523257 | 0 |
| 19 | 18 | 0.583131 | 0 | 0 | -0.00053929 | 1 | 6.28258 | 2 | 2 | 0.10904 | 0.107593 |
| 13 | 12 | 0.560274 | 0 | 0 | -0.00364951 | 1 | 4.56716 | 2 | 2 | 0.0604074 | 0.321108 |
| 18 | 17 | 0.559125 | 0 | 0 | -0.000699513 | 1 | 3.7636 | 2 | 2 | 0.107593 | 0.10316 |
| 12 | 11 | 0.508949 | 0 | 0 | -0.0042204 | 1 | 16.263 | 2 | 2 | 0.321108 | -0.0340784 |
| 17 | 16 | 0.462418 | 0 | 0 | -0.00114002 | 1 | 3.70154 | 2 | 2 | 0.10316 | 0.0370095 |

## Worst Temperature Rates

| stage_1based | dT_energy_raw_F_per_s | vflow_energy_predicted_dT_from_used_F_per_s | dT_raw_minus_vflow_predicted_F_per_s | stage_energy_balance_resid_BTUps | stage_energy_resid_over_heat_capacity_F_per_s | dominant_energy_term | dominant_energy_term_BTUps |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 | -0.523257 | -0.265322 | -0.257935 | 2808.86 | 1.42313 | vflow_energy_numer_BTUps | 13626.3 |
| 12 | 0.321108 | 0.210298 | 0.11081 | -479.083 | -0.27277 | vflow_energy_V_in_term_BTUps | 13949.5 |
| 3 | -0.164864 | -0.0813483 | -0.0835155 | 473.268 | 0.371787 | vflow_energy_numer_BTUps | 13376.7 |
| 19 | 0.10904 | 0.0851517 | 0.0238882 | 31.7086 | 0.0153718 | vflow_energy_V_in_term_BTUps | 14662.3 |
| 18 | 0.107593 | 0.0684484 | 0.0391446 | -71.1388 | -0.0336538 | vflow_energy_V_in_term_BTUps | 14501.4 |
| 17 | 0.10316 | 0.0684319 | 0.0347281 | -127.849 | -0.0589032 | vflow_energy_V_in_term_BTUps | 14357.6 |
| 13 | 0.0604074 | 0.0353799 | 0.0250275 | -290.084 | -0.166169 | vflow_energy_V_in_term_BTUps | 14008 |
| 6 | 0.0433813 | 0.0273314 | 0.0160499 | 232.011 | 0.195707 | vflow_energy_numer_BTUps | 13358.3 |

## Worst Temperature Equation Gaps

| stage_1based | dT_raw_minus_vflow_predicted_F_per_s | dT_energy_raw_F_per_s | vflow_energy_predicted_dT_from_used_F_per_s | vflow_energy_dT_target_F_per_s | vflow_energy_resid_after_used_BTUps |
|---:|---:|---:|---:|---:|---:|
| 2 | -0.257935 | -0.523257 | -0.265322 | -0.265322 | 0 |
| 12 | 0.11081 | 0.321108 | 0.210298 | 0.210298 | 0 |
| 3 | -0.0835155 | -0.164864 | -0.0813483 | -0.0813483 | 1.81899e-12 |
| 18 | 0.0391446 | 0.107593 | 0.0684484 | 0.0684484 | -1.81899e-12 |
| 17 | 0.0347281 | 0.10316 | 0.0684319 | 0.0684319 | 0 |
| 13 | 0.0250275 | 0.0604074 | 0.0353799 | 0.0353799 | 0 |
| 19 | 0.0238882 | 0.10904 | 0.0851517 | 0.0851517 | -1.81899e-12 |
| 5 | 0.0161594 | 0.0293407 | 0.0131813 | 0.0131813 | -1.81899e-12 |

## Top K Mismatches

| stage_1based | component | ln_K_state_over_K_thermo | K_state | K_thermo | y_state | y_eq |
|---:|---:|---:|---:|---:|---:|---:|
| 2 | n_Pentane | -0.719022 | 0.487229 | 1 | 1.13457e-05 | 1.70783e-05 |
| 20 | n_Propane | -0.689303 | 1 | 1.99233 | 0.157483 | 0.110223 |
| 20 | n_Pentane | 0.613094 | 1 | 0.541672 | 0.086019 | 0.0840153 |
| 19 | n_Propane | -0.597343 | 1.07627 | 1.95589 | 0.169494 | 0.172038 |
| 19 | n_Pentane | 0.565841 | 0.900684 | 0.511482 | 0.0774759 | 0.0740464 |
| 18 | n_Propane | -0.378334 | 1.30184 | 1.9005 | 0.20742 | 0.219277 |
| 3 | n_Butane | 0.361841 | 0.727172 | 0.506398 | 0.175804 | 0.135592 |
| 18 | n_Pentane | 0.347585 | 0.686614 | 0.485019 | 0.0630361 | 0.0568417 |

## Top K Eq-Relax Mismatches

| stage_1based | component | ln_K_state_over_K_eq_relax | K_state | K_eq_relax | y_state | y_eq |
|---:|---:|---:|---:|---:|---:|---:|
| 2 | n_Pentane | -0.719022 | 0.487229 | 1 | 1.13457e-05 | 1.70783e-05 |
| 20 | n_Propane | -0.689303 | 1 | 1.99233 | 0.157483 | 0.110223 |
| 20 | n_Pentane | 0.613094 | 1 | 0.541672 | 0.086019 | 0.0840153 |
| 19 | n_Propane | -0.597343 | 1.07627 | 1.95589 | 0.169494 | 0.172038 |
| 19 | n_Pentane | 0.565841 | 0.900684 | 0.511482 | 0.0774759 | 0.0740464 |
| 18 | n_Propane | -0.378334 | 1.30184 | 1.9005 | 0.20742 | 0.219277 |
| 3 | n_Butane | 0.361841 | 0.727172 | 0.506398 | 0.175804 | 0.135592 |
| 18 | n_Pentane | 0.347585 | 0.686614 | 0.485019 | 0.0630361 | 0.0568417 |

## Top Vapor Target Mismatches

| stage_1based | component | y_state_minus_y_target | y_state | y_target | y_eq |
|---:|---:|---:|---:|---:|---:|
| 1 | n_Propane | -0.905668 | 0 | 0.905668 | 0.905668 |
| 1 | n_Butane | -0.0943265 | 0 | 0.0943265 | 0.0943265 |
| 20 | n_Butane | -0.0492632 | 0.756498 | 0.805762 | 0.805762 |
| 20 | n_Propane | 0.0472595 | 0.157483 | 0.110223 | 0.110223 |
| 3 | n_Propane | -0.0402145 | 0.82417 | 0.864384 | 0.864384 |
| 3 | n_Butane | 0.0402121 | 0.175804 | 0.135592 | 0.135592 |
| 4 | n_Butane | 0.0333084 | 0.257423 | 0.224115 | 0.224115 |
| 4 | n_Propane | -0.0333052 | 0.742492 | 0.775797 | 0.775797 |

## Top Interior Vapor Target Mismatches

| stage_1based | component | y_state_minus_y_target | y_state | y_target | y_eq |
|---:|---:|---:|---:|---:|---:|
| 3 | n_Propane | -0.0402145 | 0.82417 | 0.864384 | 0.864384 |
| 3 | n_Butane | 0.0402121 | 0.175804 | 0.135592 | 0.135592 |
| 4 | n_Butane | 0.0333084 | 0.257423 | 0.224115 | 0.224115 |
| 4 | n_Propane | -0.0333052 | 0.742492 | 0.775797 | 0.775797 |
| 5 | n_Butane | 0.0240043 | 0.330264 | 0.30626 | 0.30626 |
| 5 | n_Propane | -0.023984 | 0.669501 | 0.693485 | 0.693485 |
| 15 | n_Propane | -0.0207519 | 0.362533 | 0.383285 | 0.383285 |
| 14 | n_Propane | -0.0198454 | 0.410614 | 0.43046 | 0.43046 |

