# Energy/Vapor Closure Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_refinv_temp_nolag_smoke_20260707\column_profile_20260707_100353.csv`
Time: `0.2 s`
Stage rows: `20`

## Summary

| Check | Value |
|---|---:|
| max \|V_calc - V_used\| lbmol/h | 0 |
| max \|relative V gap\| | 0 |
| max \|adjacent vapor enthalpy gap\| BTU/lbmol | 108.874 |
| max \|P_from_holdup - P\| psia | 222.62 |
| max \|energy P used - logged P\| psia | 0.00760942 |
| max \|ln(K_state/K_thermo)\| | 0.719022 |
| max \|ln(K_state/K_eq_relax)\| | 0.719022 |
| max \|y_state - y_eq\| | 0.905668 |
| max \|y_state - y_target\| | 0.905668 |
| max \|y_state - y_target\| interior | 0.0400921 |
| max \|dT_energy_raw\| F/s | 0.0567727 |
| max \|energy residual / heat capacity\| F/s | 1.56235 |
| max \|dT raw - vapor-flow predicted dT\| F/s | 0.134525 |

## Diagnostic Interpretation

- vapor-flow/temperature energy equation mismatch
- equilibrium K-state mismatch

This report uses logged RHS diagnostics only. It does not recompute thermo or change vapor-flow closure.

## Top Composite Interfaces

| vapor_source_stage_1based | vapor_receiver_stage_1based | interface_inconsistency_score | V_calc_minus_used_lbmolph | relative_V_calc_minus_used | vflow_energy_P_used_minus_source_P_psia | vflow_energy_pressure_basis_code | source_minus_receiver_HV_BTU_per_lbmol | vflow_energy_hV_in_source_code | vflow_energy_hV_out_source_code | source_dT_energy_raw_F_per_s | receiver_dT_energy_raw_F_per_s |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | nan | 22.262 | nan | nan | nan | nan | nan | nan | nan | 0 | nan |
| 19 | 18 | 0.39337 | 0 | 0 | -0.00053929 | 1 | 6.27559 | 2 | 2 | 0.00914844 | -0.017316 |
| 17 | 16 | 0.392191 | 0 | 0 | -0.00229868 | 1 | 3.67968 | 2 | 2 | -0.0127317 | 0.0567727 |
| 18 | 17 | 0.378838 | 0 | 0 | -0.00133956 | 1 | 3.76103 | 2 | 2 | -0.017316 | -0.0127317 |
| 16 | 15 | 0.357142 | 0 | 0 | -0.0034253 | 1 | 4.32678 | 2 | 2 | 0.0567727 | -0.0175181 |
| 20 | 19 | 0.330995 | nan | nan | nan | nan | -12.9968 | nan | nan | 0 | 0.00914844 |
| 2 | 1 | 0.299805 | 0 | 0 | -0.000550296 | 1 | 38.866 | 2 | 2 | -0.0117535 | 0 |
| 3 | 2 | 0.275877 | 0 | 0 | -0.00128229 | 1 | 108.874 | 2 | 2 | 2.27972e-15 | -0.0117535 |

## Worst Temperature Rates

| stage_1based | dT_energy_raw_F_per_s | vflow_energy_predicted_dT_from_used_F_per_s | dT_raw_minus_vflow_predicted_F_per_s | stage_energy_balance_resid_BTUps | stage_energy_resid_over_heat_capacity_F_per_s | dominant_energy_term | dominant_energy_term_BTUps |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 0.0567727 | 0.0392527 | 0.01752 | -169.643 | -0.079593 | vflow_energy_V_in_term_BTUps | 14704.8 |
| 10 | 0.0432605 | 0.0280319 | 0.0152286 | -101.267 | -0.0883187 | vflow_energy_numer_BTUps | 14387.8 |
| 11 | 0.0270715 | 0.0175698 | 0.00950176 | -179.661 | -0.158101 | vflow_energy_numer_BTUps | 14459.7 |
| 5 | -0.0210789 | -0.0133572 | -0.00772171 | 295.114 | 0.244713 | vflow_energy_numer_BTUps | 14344.8 |
| 15 | -0.0175181 | -0.0119463 | -0.00557188 | -154.138 | -0.0866935 | vflow_energy_V_in_term_BTUps | 14583.5 |
| 18 | -0.017316 | -0.0122766 | -0.00503943 | -129.55 | -0.0612866 | vflow_energy_numer_BTUps | 14691.1 |
| 17 | -0.0127317 | -0.00892266 | -0.00380899 | -185.316 | -0.0853794 | vflow_energy_numer_BTUps | 14696.9 |
| 2 | -0.0117535 | 0.122771 | -0.134525 | 3083.64 | 1.56235 | vflow_energy_V_in_term_BTUps | 14010.4 |

## Worst Temperature Equation Gaps

| stage_1based | dT_raw_minus_vflow_predicted_F_per_s | dT_energy_raw_F_per_s | vflow_energy_predicted_dT_from_used_F_per_s | vflow_energy_dT_target_F_per_s | vflow_energy_resid_after_used_BTUps |
|---:|---:|---:|---:|---:|---:|
| 2 | -0.134525 | -0.0117535 | 0.122771 | 0.122771 | 0 |
| 16 | 0.01752 | 0.0567727 | 0.0392527 | 0.0392527 | 0 |
| 10 | 0.0152286 | 0.0432605 | 0.0280319 | 0.0280319 | 1.81899e-12 |
| 11 | 0.00950176 | 0.0270715 | 0.0175698 | 0.0175698 | -1.81899e-12 |
| 5 | -0.00772171 | -0.0210789 | -0.0133572 | -0.0133572 | 0 |
| 15 | -0.00557188 | -0.0175181 | -0.0119463 | -0.0119463 | 0 |
| 18 | -0.00503943 | -0.017316 | -0.0122766 | -0.0122766 | 1.81899e-12 |
| 17 | -0.00380899 | -0.0127317 | -0.00892266 | -0.00892266 | 0 |

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

