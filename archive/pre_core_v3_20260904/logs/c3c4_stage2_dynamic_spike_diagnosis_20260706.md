# Initialization Dynamic Spike Diagnosis

Worst time: `40 s`

Worst candidate state-rate row: `tray_V` stage `4.0` component `n-Butane`

## Summary Drivers

| Field | Baseline | Candidate | Difference | Ratio |
|---|---:|---:|---:|---:|
| ss_max_rel_state_rate_per_s | 0.00497911 | 0.13096 | 0.125981 | 26.3018 |
| steady_state_score | 1.96604 | 43.6532 | 41.6872 | 22.2036 |
| pv_inner_dv_max_lbmolph | 0.743768 | 15.4541 | 14.7103 | 20.7781 |
| ss_max_temp_rate_F_per_s | 0.294906 | 0.698232 | 0.403326 | 2.36764 |
| K_state_over_K_thermo_max_abs | 1.84651 | 3.96304 | 2.11653 | 2.14623 |
| pv_inner_dp_max_psia | 0.000384876 | 0.00057563 | 0.000190754 | 1.49562 |
| top_L_net_lbmolph | 519.457 | 465.296 | -54.1613 | 0.895735 |
| stage_mass_resid_sum_lbmolps | -0.147737 | -0.132692 | 0.0150448 | 0.898165 |
| Q_cond_calc_BTUph | -5.16822e+07 | -5.30053e+07 | -1.32313e+06 | 1.0256 |
| V_condensed_in_lbmolph | 8873.71 | 8819.55 | -54.1613 | 0.993896 |
| P_top_drum_psia | 171.67 | 170.966 | -0.704063 | 0.995899 |
| T_sump_F | 220.604 | 220.604 | 3.06659e-07 | 1 |

## Profile Drivers

### Stage 11

| Field | Baseline | Candidate | Difference | Ratio |
|---|---:|---:|---:|---:|
| dT_energy_raw_F_per_s | 0.0259531 | 0.001837 | -0.0241161 | 0.0707817 |
| stage_mass_balance_resid_lbmolps | 0.00310793 | 0.0109876 | 0.00787962 | 3.53532 |
| stage_energy_balance_resid_BTUps | -70.8449 | 59.2222 | 130.067 | 0.835942 |
| y_n_Pentane | 0.0187704 | 0.0158437 | -0.00292672 | 0.844078 |
| y_eq_n_Pentane | 0.0170796 | 0.0145019 | -0.00257766 | 0.849079 |

### Stage 10

| Field | Baseline | Candidate | Difference | Ratio |
|---|---:|---:|---:|---:|
| stage_mass_balance_resid_lbmolps | -0.00438273 | 0.000350887 | 0.00473362 | 0.0800614 |
| stage_energy_balance_resid_BTUps | 64.8447 | 148.642 | 83.7977 | 2.29228 |
| dT_energy_raw_F_per_s | -0.0706405 | -0.041183 | 0.0294575 | 0.582995 |
| y_n_Pentane | 0.00974354 | 0.00820124 | -0.0015423 | 0.84171 |
| x_eq_n_Pentane | 0.0261205 | 0.0222272 | -0.00389338 | 0.850946 |

### Stage 19

| Field | Baseline | Candidate | Difference | Ratio |
|---|---:|---:|---:|---:|
| dT_energy_raw_F_per_s | 0.0978157 | 1.04917 | 0.951353 | 10.726 |
| stage_mass_balance_resid_lbmolps | -0.0277041 | -0.0427632 | -0.015059 | 1.54357 |
| stage_energy_balance_resid_BTUps | -276.3 | -311.956 | -35.6561 | 1.12905 |
| vflow_energy_calc_lbmolph | 7941.2 | 8801.81 | 860.606 | 1.10837 |
| hydraulic_dp_used_psia | 0.50016 | 0.550163 | 0.0500031 | 1.09997 |

### Stage 8

| Field | Baseline | Candidate | Difference | Ratio |
|---|---:|---:|---:|---:|
| dT_energy_raw_F_per_s | 0.0153238 | -0.0973478 | -0.112672 | 6.3527 |
| y_eq_n_Pentane | 0.00378449 | 0.00209595 | -0.00168854 | 0.553826 |
| y_target_n_Pentane | 0.00378449 | 0.00209595 | -0.00168854 | 0.553826 |
| y_n_Pentane | 0.00400669 | 0.00228696 | -0.00171973 | 0.570785 |
| x_eq_n_Pentane | 0.0112595 | 0.00660814 | -0.00465133 | 0.586896 |

### Stage 14

| Field | Baseline | Candidate | Difference | Ratio |
|---|---:|---:|---:|---:|
| stage_energy_balance_resid_BTUps | -222.918 | -41.1581 | 181.76 | 0.184633 |
| dT_energy_raw_F_per_s | 0.0749961 | 0.166382 | 0.0913857 | 2.21854 |
| stage_mass_balance_resid_lbmolps | -0.0333381 | -0.0231998 | 0.0101383 | 0.695896 |
| V_out_lbmolph | 7600.62 | 6535.27 | -1065.35 | 0.859834 |
| vflow_energy_used_lbmolph | 7600.62 | 6535.27 | -1065.35 | 0.859834 |

### Stage 18

| Field | Baseline | Candidate | Difference | Ratio |
|---|---:|---:|---:|---:|
| dT_energy_raw_F_per_s | 0.165594 | -0.658308 | -0.823902 | 3.97542 |
| x_eq_n_Propane | 0.094491 | 0.158557 | 0.0640656 | 1.67801 |
| K_state_over_K_thermo_n_Propane | 0.636956 | 1.00031 | 0.363356 | 1.57046 |
| x_eq_n_Pentane | 0.154225 | 0.10164 | -0.0525849 | 0.659037 |
| K_state_over_K_thermo_n_Pentane | 1.42083 | 0.992693 | -0.428137 | 0.698671 |
