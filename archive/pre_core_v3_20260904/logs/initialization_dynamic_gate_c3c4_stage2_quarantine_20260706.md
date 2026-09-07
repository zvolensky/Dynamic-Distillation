# Initialization Dynamic Gate

Baseline: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_baseline_thermoprov_60s_20260706b\column_summary_20260706_202739.csv`

## c3c4_stage2_quarantine: FAIL

| Check | Value | Limit | Candidate | Baseline | Result |
|---|---:|---:|---:|---:|---|
| final score ratio | 2.36741 | 1 | 4.65444 | 1.96604 | FAIL |
| peak score ratio | 1.68424 | 1 | 5.83491 | 3.46442 | FAIL |
| final relative state-rate ratio | 2.21048 | 1 | 0.0110062 | 0.00497911 | FAIL |
| peak relative state-rate ratio | 1.87498 | 1 | 0.0175047 | 0.00933596 | FAIL |
| final temperature-rate ratio | 2.36741 | 1.25 | 0.698166 | 0.294906 | FAIL |
| P_top_drum_psia final absolute drift | 0.706786 | 0.5 | 170.963 | 171.67 | FAIL |
| T_sump_F final absolute drift | 3.03303e-07 | 0.5 | 220.604 | 220.604 | PASS |
| K_state_over_K_thermo_max_abs final ratio | 1.01058 | 1.25 | 1.86605 | 1.84651 | PASS |
| K_state_over_K_thermo_max_abs peak ratio | 1.01804 | 1.25 | 1.87981 | 1.84651 | PASS |
| K_state_minus_K_thermo_max_abs final ratio | 1.00941 | 1.25 | 1.00196 | 0.992621 | PASS |
| K_state_minus_K_thermo_max_abs peak ratio | 1.00941 | 1.25 | 1.00196 | 0.992621 | PASS |
| pv_inner_dv_max_lbmolph final ratio | 17.1929 | 1.25 | 12.7875 | 0.743768 | FAIL |
| pv_inner_dv_max_lbmolph peak ratio | 2.58073 | 1.25 | 12.9063 | 5.00103 | FAIL |
| top_L_net_worst_abs_lbmolph final ratio | 1.22953 | 1.25 | 728.128 | 592.2 | PASS |
| top_L_net_worst_abs_lbmolph peak ratio | 1.22953 | 1.25 | 728.128 | 592.2 | PASS |

### Failure Breakdown

| Family | Ratio | Abs delta | Candidate | Baseline | Field |
|---|---:|---:|---:|---:|---|
| top liquid component net | 1.22953 | 135.929 | 728.128 | 592.2 | `top_L_net_worst_abs_lbmolph` |
| pressure/vapor-flow inner solve | 17.1929 | 12.0438 | 12.7875 | 0.743768 | `pv_inner_dv_max_lbmolph` |
| dynamic score | 2.36741 | 2.68839 | 4.65444 | 1.96604 | `steady_state_score` |
| temperature rate | 2.36741 | 0.403259 | 0.698166 | 0.294906 | `ss_max_temp_rate_F_per_s` |
| K-state over K-thermo | 1.01058 | 0.0195369 | 1.86605 | 1.84651 | `K_state_over_K_thermo_max_abs` |
| K-state minus K-thermo | 1.00941 | 0.00934213 | 1.00196 | 0.992621 | `K_state_minus_K_thermo_max_abs` |
| relative state rate | 2.21048 | 0.0060271 | 0.0110062 | 0.00497911 | `ss_max_rel_state_rate_per_s` |
| pressure inner solve | 1.4532 | 0.000174425 | 0.000559301 | 0.000384876 | `pv_inner_dp_max_psia` |

