# Energy/Vapor Closure Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_k_eq_relax_smoke_20260707\column_profile_20260707_093902.csv`
Time: `0 s`
Stage rows: `20`

## Summary

| Check | Value |
|---|---:|
| max \|V_calc - V_used\| lbmol/h | nan |
| max \|relative V gap\| | nan |
| max \|adjacent vapor enthalpy gap\| BTU/lbmol | nan |
| max \|P_from_holdup - P\| psia | nan |
| max \|energy P used - logged P\| psia | nan |
| max \|ln(K_state/K_thermo)\| | nan |
| max \|ln(K_state/K_eq_relax)\| | nan |
| max \|y_state - y_eq\| | nan |
| max \|dT_energy_raw\| F/s | nan |
| max \|energy residual / heat capacity\| F/s | nan |

## Diagnostic Interpretation

- no dominant inconsistency above built-in diagnostic thresholds

This report uses logged RHS diagnostics only. It does not recompute thermo or change vapor-flow closure.

## Top Composite Interfaces

| vapor_source_stage_1based | vapor_receiver_stage_1based | interface_inconsistency_score | V_calc_minus_used_lbmolph | relative_V_calc_minus_used | vflow_energy_P_used_minus_source_P_psia | vflow_energy_pressure_basis_code | source_minus_receiver_HV_BTU_per_lbmol | vflow_energy_hV_in_source_code | vflow_energy_hV_out_source_code | source_dT_energy_raw_F_per_s | receiver_dT_energy_raw_F_per_s |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | nan | 0 | nan | nan | nan | nan | nan | nan | nan | nan | nan |
| 2 | 1 | 0 | nan | nan | nan | nan | nan | nan | nan | nan | nan |
| 3 | 2 | 0 | nan | nan | nan | nan | nan | nan | nan | nan | nan |
| 4 | 3 | 0 | nan | nan | nan | nan | nan | nan | nan | nan | nan |
| 5 | 4 | 0 | nan | nan | nan | nan | nan | nan | nan | nan | nan |
| 6 | 5 | 0 | nan | nan | nan | nan | nan | nan | nan | nan | nan |
| 7 | 6 | 0 | nan | nan | nan | nan | nan | nan | nan | nan | nan |
| 8 | 7 | 0 | nan | nan | nan | nan | nan | nan | nan | nan | nan |

## Worst Temperature Rates

No finite records.

## Top K Mismatches

No finite records.

## Top K Eq-Relax Mismatches

No finite records.

