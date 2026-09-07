# Energy/Vapor Closure Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_topLalign100_dynvflow105_provenance_40s_20260707\column_profile_20260707_092423.csv`
Time: `40 s`
Stage rows: `20`

## Summary

| Check | Value |
|---|---:|
| max \|V_calc - V_used\| lbmol/h | 734.761 |
| max \|relative V gap\| | 0.0827771 |
| max \|adjacent vapor enthalpy gap\| BTU/lbmol | 182.273 |
| max \|P_from_holdup - P\| psia | 222.62 |
| max \|energy P used - logged P\| psia | nan |
| max \|ln(K_state/K_thermo)\| | 0.694358 |
| max \|y_state - y_eq\| | 0.905668 |
| max \|dT_energy_raw\| F/s | 0.717644 |
| max \|energy residual / heat capacity\| F/s | 0.753701 |

## Diagnostic Interpretation

- temperature-rate spike
- equilibrium K-state mismatch

This report uses logged RHS diagnostics only. It does not recompute thermo or change vapor-flow closure.

## Top Composite Interfaces

| vapor_source_stage_1based | vapor_receiver_stage_1based | interface_inconsistency_score | V_calc_minus_used_lbmolph | relative_V_calc_minus_used | vflow_energy_P_used_minus_source_P_psia | vflow_energy_pressure_basis_code | source_minus_receiver_HV_BTU_per_lbmol | vflow_energy_hV_in_source_code | vflow_energy_hV_out_source_code | source_dT_energy_raw_F_per_s | receiver_dT_energy_raw_F_per_s |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | nan | 22.262 | nan | nan | nan | nan | nan | nan | nan | 0 | nan |
| 3 | 2 | 4.20421 | -290.569 | -0.0333045 | nan | nan | -44.7372 | nan | nan | -0.0243691 | -0.717644 |
| 5 | 4 | 2.49106 | -89.2729 | -0.0115801 | nan | nan | 34.9693 | nan | nan | -0.180269 | -0.248431 |
| 4 | 3 | 2.31687 | -177.31 | -0.0219995 | nan | nan | 182.273 | nan | nan | -0.248431 | -0.0243691 |
| 17 | 16 | 2.1942 | 97.0472 | 0.0134571 | nan | nan | 11.2612 | nan | nan | 0.280902 | 0.202381 |
| 18 | 17 | 2.06632 | 81.1419 | 0.0107153 | nan | nan | 7.7917 | nan | nan | 0.232363 | 0.280902 |
| 6 | 5 | 2.03564 | -123.361 | -0.01672 | nan | nan | 22.4199 | nan | nan | -0.106097 | -0.180269 |
| 7 | 6 | 1.668 | -82.2148 | -0.0115543 | nan | nan | 15.5947 | nan | nan | -0.131039 | -0.106097 |
| 16 | 15 | 1.57373 | 74.6423 | 0.0107853 | nan | nan | 3.83978 | nan | nan | 0.202381 | 0.185347 |
| 8 | 7 | 1.39997 | -58.5641 | -0.00848548 | nan | nan | 11.392 | nan | nan | -0.115257 | -0.131039 |

## Worst Temperature Rates

| stage_1based | dT_energy_raw_F_per_s | stage_energy_balance_resid_BTUps | stage_energy_resid_over_heat_capacity_F_per_s | dominant_energy_term | dominant_energy_term_BTUps |
|---:|---:|---:|---:|---:|---:|
| 2 | -0.717644 | -803.301 | -0.38783 | vflow_energy_numer_BTUps | 15599.5 |
| 17 | 0.280902 | -246.304 | -0.114029 | vflow_energy_V_in_term_BTUps | 13965 |
| 4 | -0.248431 | 957.348 | 0.753701 | vflow_energy_numer_BTUps | 13192.5 |
| 18 | 0.232363 | -272.34 | -0.129466 | vflow_energy_V_in_term_BTUps | 14568.5 |
| 16 | 0.202381 | -199.003 | -0.0938611 | vflow_energy_V_in_term_BTUps | 13224.3 |
| 15 | 0.185347 | -126.152 | -0.0713167 | vflow_energy_V_in_term_BTUps | 12663.8 |
| 5 | -0.180269 | 827.937 | 0.682512 | vflow_energy_numer_BTUps | 13042.4 |
| 14 | 0.166152 | -41.4431 | -0.0239817 | vflow_energy_V_in_term_BTUps | 12238.8 |
| 7 | -0.131039 | 457.118 | 0.392616 | vflow_energy_numer_BTUps | 12298.9 |
| 8 | -0.115257 | 324.513 | 0.280617 | vflow_energy_numer_BTUps | 12038.8 |

## Top K Mismatches

| stage_1based | component | ln_K_state_over_K_thermo | K_state | K_thermo | y_state | y_eq |
|---:|---:|---:|---:|---:|---:|---:|
| 18 | n_Propane | -0.694358 | 1.00011 | 2.00263 | 0.158485 | 0.158484 |
| 19 | n_Propane | -0.691682 | 1.00123 | 1.99952 | 0.155784 | 0.155884 |
| 20 | n_Propane | -0.689303 | 1 | 1.99233 | 0.155593 | 0.110223 |
| 19 | n_Pentane | 0.628767 | 0.996248 | 0.531248 | 0.0988951 | 0.0989129 |
| 18 | n_Pentane | 0.62462 | 0.993051 | 0.531744 | 0.101153 | 0.101717 |
| 20 | n_Pentane | 0.613094 | 1 | 0.541672 | 0.0992675 | 0.0840153 |
| 17 | n_Propane | -0.494669 | 1.1882 | 1.94859 | 0.19416 | 0.196054 |
| 17 | n_Pentane | 0.404682 | 0.758105 | 0.505799 | 0.0800262 | 0.0790305 |
| 16 | n_Propane | -0.194949 | 1.52543 | 1.85377 | 0.274599 | 0.2797 |
| 15 | n_Propane | -0.188639 | 1.49419 | 1.80439 | 0.329879 | 0.333568 |

