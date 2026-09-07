# Initialization Dynamic Spike Diagnosis

Worst time: `50 s`

Worst candidate state-rate row: `tray_V` stage `4.0` component `n-Butane`

## Summary Drivers

| Field | Baseline | Candidate | Difference | Ratio |
|---|---:|---:|---:|---:|
| steady_state_score | 2.37158 | 287.16 | 284.788 | 121.084 |
| ss_max_rel_state_rate_per_s | 0.00711475 | 0.86148 | 0.854365 | 121.084 |
| pv_inner_dv_max_lbmolph | 0.705341 | 3.89907 | 3.19372 | 5.52792 |
| ss_max_temp_rate_F_per_s | 0.263009 | 0.856592 | 0.593582 | 3.25689 |
| pv_inner_dp_max_psia | 0.000305179 | 0.000531554 | 0.000226375 | 1.74178 |
| K_state_over_K_thermo_max_abs | 1.84651 | 2.83767 | 0.991164 | 1.53678 |
| top_L_net_lbmolph | 517.125 | 745.92 | 228.795 | 1.44244 |
| stage_mass_resid_sum_lbmolps | -0.147089 | -0.210643 | -0.0635542 | 1.43208 |
| V_condensed_in_lbmolph | 8871.38 | 9100.17 | 228.795 | 1.02579 |
| Q_cond_calc_BTUph | -5.14988e+07 | -5.26679e+07 | -1.16913e+06 | 1.0227 |
| P_top_drum_psia | 171.805 | 171.866 | 0.0611419 | 1.00036 |
| T_sump_F | 220.579 | 220.579 | 6.63064e-07 | 1 |

## Profile Drivers

### Stage 7

| Field | Baseline | Candidate | Difference | Ratio |
|---|---:|---:|---:|---:|
| stage_mass_balance_resid_lbmolps | -0.0123531 | 7.20838e-05 | 0.0124252 | 0.00583529 |
| y_eq_n_Pentane | 0.00231079 | 0.000940266 | -0.00137052 | 0.406902 |
| y_target_n_Pentane | 0.00231079 | 0.000940266 | -0.00137052 | 0.406902 |
| y_n_Pentane | 0.00247263 | 0.00104034 | -0.00143229 | 0.420743 |
| x_eq_n_Pentane | 0.00704869 | 0.0031348 | -0.00391389 | 0.444736 |

### Stage 19

| Field | Baseline | Candidate | Difference | Ratio |
|---|---:|---:|---:|---:|
| dT_energy_raw_F_per_s | 0.0862508 | -0.849035 | -0.935286 | 9.8438 |
| x_eq_n_Propane | 0.074688 | 0.155208 | 0.0805203 | 2.07809 |
| K_state_over_K_thermo_n_Propane | 0.507631 | 0.99953 | 0.491899 | 1.96901 |
| x_eq_n_Pentane | 0.196334 | 0.102068 | -0.0942659 | 0.51987 |
| K_state_over_K_thermo_n_Pentane | 1.79795 | 0.999222 | -0.798733 | 0.555755 |

### Stage 10

| Field | Baseline | Candidate | Difference | Ratio |
|---|---:|---:|---:|---:|
| stage_mass_balance_resid_lbmolps | -0.000894896 | -0.00540565 | -0.00451075 | 6.04054 |
| stage_energy_balance_resid_BTUps | 106.917 | 272.398 | 165.481 | 2.54776 |
| V_out_lbmolph | 7532.81 | 6528.93 | -1003.88 | 0.866733 |
| vflow_energy_used_lbmolph | 7532.81 | 6528.93 | -1003.88 | 0.866733 |
| x_eq_n_Pentane | 0.0263005 | 0.0229644 | -0.0033361 | 0.873155 |

### Stage 9

| Field | Baseline | Candidate | Difference | Ratio |
|---|---:|---:|---:|---:|
| dT_energy_raw_F_per_s | -0.0601304 | -0.0102067 | 0.0499238 | 0.169742 |
| stage_mass_balance_resid_lbmolps | -0.0138533 | -0.00542442 | 0.00842889 | 0.391561 |
| stage_energy_balance_resid_BTUps | 230.458 | 434.26 | 203.802 | 1.88433 |
| y_eq_n_Pentane | 0.00609647 | 0.00398852 | -0.00210795 | 0.654234 |
| y_target_n_Pentane | 0.00609647 | 0.00398852 | -0.00210795 | 0.654234 |

### Stage 8

| Field | Baseline | Candidate | Difference | Ratio |
|---|---:|---:|---:|---:|
| stage_mass_balance_resid_lbmolps | -0.0143399 | -0.0034804 | 0.0108595 | 0.242707 |
| y_eq_n_Pentane | 0.00399602 | 0.00195439 | -0.00204163 | 0.489085 |
| y_target_n_Pentane | 0.00399602 | 0.00195439 | -0.00204163 | 0.489085 |
| y_n_Pentane | 0.00420704 | 0.00215206 | -0.00205499 | 0.511537 |
| x_eq_n_Pentane | 0.0118759 | 0.00619294 | -0.00568297 | 0.521471 |

### Stage 5

| Field | Baseline | Candidate | Difference | Ratio |
|---|---:|---:|---:|---:|
| dT_energy_raw_F_per_s | 0.146502 | -0.0377311 | -0.184233 | 0.257547 |
| y_eq_n_Pentane | 0.000543534 | 0.000182734 | -0.000360799 | 0.336197 |
| y_target_n_Pentane | 0.000543534 | 0.000182734 | -0.000360799 | 0.336197 |
| y_n_Pentane | 0.000605032 | 0.000208579 | -0.000396453 | 0.34474 |
| x_eq_n_Pentane | 0.00186969 | 0.000707161 | -0.00116253 | 0.378224 |
