# Initialization Dynamic Gate

Baseline: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_baseline_thermoprov_60s_20260706b\column_summary_20260706_202739.csv`

## topLalign100_dynvflow105: FAIL

| Check | Value | Limit | Candidate | Baseline | Result |
|---|---:|---:|---:|---:|---|
| final score ratio | 2.42571 | 1 | 4.76905 | 1.96604 | FAIL |
| peak score ratio | 45.3542 | 1 | 157.126 | 3.46442 | FAIL |
| final relative state-rate ratio | 2.34305 | 1 | 0.0116663 | 0.00497911 | FAIL |
| peak relative state-rate ratio | 50.4906 | 1 | 0.471378 | 0.00933596 | FAIL |
| final temperature-rate ratio | 2.42571 | 1.25 | 0.715358 | 0.294906 | FAIL |
| P_top_drum_psia final absolute drift | 0.715126 | 0.5 | 170.955 | 171.67 | FAIL |
| T_sump_F final absolute drift | 3.01904e-07 | 0.5 | 220.604 | 220.604 | PASS |
| K_state_over_K_thermo_max_abs final ratio | 1.01559 | 1.25 | 1.8753 | 1.84651 | PASS |
| K_state_over_K_thermo_max_abs peak ratio | 1.01792 | 1.25 | 1.8796 | 1.84651 | PASS |
| K_state_minus_K_thermo_max_abs final ratio | 1.00998 | 1.25 | 1.00253 | 0.992621 | PASS |
| K_state_minus_K_thermo_max_abs peak ratio | 1.00998 | 1.25 | 1.00253 | 0.992621 | PASS |
| pv_inner_dv_max_lbmolph final ratio | 16.7439 | 1.25 | 12.4536 | 0.743768 | FAIL |
| pv_inner_dv_max_lbmolph peak ratio | 2.4902 | 1.25 | 12.4536 | 5.00103 | FAIL |
| top_L_net_worst_abs_lbmolph final ratio | 1.01315 | 1.25 | 599.99 | 592.2 | PASS |
| top_L_net_worst_abs_lbmolph peak ratio | 1.01315 | 1.25 | 599.99 | 592.2 | PASS |

### Failure Breakdown

| Family | Ratio | Abs delta | Candidate | Baseline | Field |
|---|---:|---:|---:|---:|---|
| pressure/vapor-flow inner solve | 16.7439 | 11.7098 | 12.4536 | 0.743768 | `pv_inner_dv_max_lbmolph` |
| top liquid component net | 1.01315 | 7.78976 | 599.99 | 592.2 | `top_L_net_worst_abs_lbmolph` |
| dynamic score | 2.42571 | 2.80301 | 4.76905 | 1.96604 | `steady_state_score` |
| top liquid total net | 1.00516 | 2.68079 | 522.138 | 519.457 | `top_L_net_lbmolph` |
| temperature rate | 2.42571 | 0.420451 | 0.715358 | 0.294906 | `ss_max_temp_rate_F_per_s` |
| K-state over K-thermo | 1.01559 | 0.0287881 | 1.8753 | 1.84651 | `K_state_over_K_thermo_max_abs` |
| K-state minus K-thermo | 1.00998 | 0.0099071 | 1.00253 | 0.992621 | `K_state_minus_K_thermo_max_abs` |
| relative state rate | 2.34305 | 0.00668719 | 0.0116663 | 0.00497911 | `ss_max_rel_state_rate_per_s` |

