# Initialization Dynamic Gate

Baseline: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_baseline_thermoprov_60s_20260706b\column_summary_20260706_202739.csv`

## align025: FAIL

| Check | Value | Limit | Candidate | Baseline | Result |
|---|---:|---:|---:|---:|---|
| final score ratio | 4.01539 | 1 | 7.89443 | 1.96604 | FAIL |
| peak score ratio | 24.0277 | 1 | 83.2421 | 3.46442 | FAIL |
| final relative state-rate ratio | 4.75653 | 1 | 0.0236833 | 0.00497911 | FAIL |
| peak relative state-rate ratio | 26.7489 | 1 | 0.249726 | 0.00933596 | FAIL |
| final temperature-rate ratio | 2.28937 | 1.25 | 0.67515 | 0.294906 | FAIL |
| P_top_drum_psia final absolute drift | 0.717599 | 0.5 | 170.953 | 171.67 | FAIL |
| T_sump_F final absolute drift | 3.02765e-07 | 0.5 | 220.604 | 220.604 | PASS |
| K_state_over_K_thermo_max_abs final ratio | 1.01036 | 1.25 | 1.86564 | 1.84651 | PASS |
| K_state_over_K_thermo_max_abs peak ratio | 1.01768 | 1.25 | 1.87916 | 1.84651 | PASS |
| K_state_minus_K_thermo_max_abs final ratio | 1.00865 | 1.25 | 1.0012 | 0.992621 | PASS |
| K_state_minus_K_thermo_max_abs peak ratio | 1.00865 | 1.25 | 1.0012 | 0.992621 | PASS |
| pv_inner_dv_max_lbmolph final ratio | 19.2118 | 1.25 | 14.2891 | 0.743768 | FAIL |
| pv_inner_dv_max_lbmolph peak ratio | 2.85724 | 1.25 | 14.2891 | 5.00103 | FAIL |
| top_L_net_worst_abs_lbmolph final ratio | 1.14177 | 1.25 | 676.158 | 592.2 | PASS |
| top_L_net_worst_abs_lbmolph peak ratio | 1.14177 | 1.25 | 676.158 | 592.2 | PASS |

### Failure Breakdown

| Family | Ratio | Abs delta | Candidate | Baseline | Field |
|---|---:|---:|---:|---:|---|
| top liquid component net | 1.14177 | 83.958 | 676.158 | 592.2 | `top_L_net_worst_abs_lbmolph` |
| pressure/vapor-flow inner solve | 19.2118 | 13.5454 | 14.2891 | 0.743768 | `pv_inner_dv_max_lbmolph` |
| dynamic score | 4.01539 | 5.92838 | 7.89443 | 1.96604 | `steady_state_score` |
| temperature rate | 2.28937 | 0.380243 | 0.67515 | 0.294906 | `ss_max_temp_rate_F_per_s` |
| K-state over K-thermo | 1.01036 | 0.0191287 | 1.86564 | 1.84651 | `K_state_over_K_thermo_max_abs` |
| relative state rate | 4.75653 | 0.0187042 | 0.0236833 | 0.00497911 | `ss_max_rel_state_rate_per_s` |
| K-state minus K-thermo | 1.00865 | 0.00858167 | 1.0012 | 0.992621 | `K_state_minus_K_thermo_max_abs` |
| pressure inner solve | 1.32663 | 0.000125713 | 0.000510589 | 0.000384876 | `pv_inner_dp_max_psia` |

## align050: FAIL

| Check | Value | Limit | Candidate | Baseline | Result |
|---|---:|---:|---:|---:|---|
| final score ratio | 41.5859 | 1 | 81.7596 | 1.96604 | FAIL |
| peak score ratio | 23.5998 | 1 | 81.7596 | 3.46442 | FAIL |
| final relative state-rate ratio | 49.2616 | 1 | 0.245279 | 0.00497911 | FAIL |
| peak relative state-rate ratio | 26.2725 | 1 | 0.245279 | 0.00933596 | FAIL |
| final temperature-rate ratio | 2.34497 | 1.25 | 0.691547 | 0.294906 | FAIL |
| P_top_drum_psia final absolute drift | 0.711191 | 0.5 | 170.959 | 171.67 | FAIL |
| T_sump_F final absolute drift | 3.00655e-07 | 0.5 | 220.604 | 220.604 | PASS |
| K_state_over_K_thermo_max_abs final ratio | 1.01115 | 1.25 | 1.8671 | 1.84651 | PASS |
| K_state_over_K_thermo_max_abs peak ratio | 1.01301 | 1.25 | 1.87053 | 1.84651 | PASS |
| K_state_minus_K_thermo_max_abs final ratio | 1.00969 | 1.25 | 1.00224 | 0.992621 | PASS |
| K_state_minus_K_thermo_max_abs peak ratio | 1.00969 | 1.25 | 1.00224 | 0.992621 | PASS |
| pv_inner_dv_max_lbmolph final ratio | 16.6417 | 1.25 | 12.3776 | 0.743768 | FAIL |
| pv_inner_dv_max_lbmolph peak ratio | 2.475 | 1.25 | 12.3776 | 5.00103 | FAIL |
| top_L_net_worst_abs_lbmolph final ratio | 1.0823 | 1.25 | 640.939 | 592.2 | PASS |
| top_L_net_worst_abs_lbmolph peak ratio | 1.0823 | 1.25 | 640.939 | 592.2 | PASS |

### Failure Breakdown

| Family | Ratio | Abs delta | Candidate | Baseline | Field |
|---|---:|---:|---:|---:|---|
| dynamic score | 41.5859 | 79.7935 | 81.7596 | 1.96604 | `steady_state_score` |
| top liquid component net | 1.0823 | 48.7393 | 640.939 | 592.2 | `top_L_net_worst_abs_lbmolph` |
| pressure/vapor-flow inner solve | 16.6417 | 11.6338 | 12.3776 | 0.743768 | `pv_inner_dv_max_lbmolph` |
| temperature rate | 2.34497 | 0.39664 | 0.691547 | 0.294906 | `ss_max_temp_rate_F_per_s` |
| relative state rate | 49.2616 | 0.2403 | 0.245279 | 0.00497911 | `ss_max_rel_state_rate_per_s` |
| K-state over K-thermo | 1.01115 | 0.0205928 | 1.8671 | 1.84651 | `K_state_over_K_thermo_max_abs` |
| K-state minus K-thermo | 1.00969 | 0.00961535 | 1.00224 | 0.992621 | `K_state_minus_K_thermo_max_abs` |
| pressure inner solve | 1.55344 | 0.000213005 | 0.000597881 | 0.000384876 | `pv_inner_dp_max_psia` |

## align100: FAIL

| Check | Value | Limit | Candidate | Baseline | Result |
|---|---:|---:|---:|---:|---|
| final score ratio | 2.25575 | 1 | 4.43491 | 1.96604 | FAIL |
| peak score ratio | 3.2498 | 1 | 11.2587 | 3.46442 | FAIL |
| final relative state-rate ratio | 2.49412 | 1 | 0.0124185 | 0.00497911 | FAIL |
| peak relative state-rate ratio | 3.61784 | 1 | 0.033776 | 0.00933596 | FAIL |
| final temperature-rate ratio | 2.25575 | 1.25 | 0.665236 | 0.294906 | FAIL |
| P_top_drum_psia final absolute drift | 0.728899 | 0.5 | 170.941 | 171.67 | FAIL |
| T_sump_F final absolute drift | 3.02475e-07 | 0.5 | 220.604 | 220.604 | PASS |
| K_state_over_K_thermo_max_abs final ratio | 1.01063 | 1.25 | 1.86614 | 1.84651 | PASS |
| K_state_over_K_thermo_max_abs peak ratio | 1.01792 | 1.25 | 1.8796 | 1.84651 | PASS |
| K_state_minus_K_thermo_max_abs final ratio | 1.00948 | 1.25 | 1.00203 | 0.992621 | PASS |
| K_state_minus_K_thermo_max_abs peak ratio | 1.00948 | 1.25 | 1.00203 | 0.992621 | PASS |
| pv_inner_dv_max_lbmolph final ratio | 18.7489 | 1.25 | 13.9448 | 0.743768 | FAIL |
| pv_inner_dv_max_lbmolph peak ratio | 2.78839 | 1.25 | 13.9448 | 5.00103 | FAIL |
| top_L_net_worst_abs_lbmolph final ratio | 1.00475 | 1.25 | 595.012 | 592.2 | PASS |
| top_L_net_worst_abs_lbmolph peak ratio | 1.00475 | 1.25 | 595.012 | 592.2 | PASS |

### Failure Breakdown

| Family | Ratio | Abs delta | Candidate | Baseline | Field |
|---|---:|---:|---:|---:|---|
| pressure/vapor-flow inner solve | 18.7489 | 13.201 | 13.9448 | 0.743768 | `pv_inner_dv_max_lbmolph` |
| top liquid component net | 1.00475 | 2.8124 | 595.012 | 592.2 | `top_L_net_worst_abs_lbmolph` |
| dynamic score | 2.25575 | 2.46886 | 4.43491 | 1.96604 | `steady_state_score` |
| temperature rate | 2.25575 | 0.37033 | 0.665236 | 0.294906 | `ss_max_temp_rate_F_per_s` |
| K-state over K-thermo | 1.01063 | 0.0196358 | 1.86614 | 1.84651 | `K_state_over_K_thermo_max_abs` |
| K-state minus K-thermo | 1.00948 | 0.00941264 | 1.00203 | 0.992621 | `K_state_minus_K_thermo_max_abs` |
| relative state rate | 2.49412 | 0.00743938 | 0.0124185 | 0.00497911 | `ss_max_rel_state_rate_per_s` |
| pressure inner solve | 1.45403 | 0.000174744 | 0.00055962 | 0.000384876 | `pv_inner_dp_max_psia` |

