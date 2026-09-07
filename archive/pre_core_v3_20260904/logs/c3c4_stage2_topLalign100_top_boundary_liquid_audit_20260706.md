# Top Boundary Liquid Coupling Audit

Baseline: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_baseline_thermoprov_60s_20260706b\column_summary_20260706_202739.csv`
Candidate: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_topLalign100_40s_20260706\column_summary_20260706_214820.csv`
Final compared time: `40 s`

## Final Summary

| Metric | Baseline | Candidate |
|---|---:|---:|
| `top_L_net_lbmolph` | 519.457 | 356.337 |
| `top_L_net_worst_component_1based` | 2 | 2 |
| `top_L_net_worst_abs_lbmolph` | 592.2 | 595.012 |
| `V_condensed_in_lbmolph` | 8873.71 | 8710.59 |
| `top_L_reflux_out_lbmolph` | 5967.32 | 5967.32 |
| `top_L_distillate_out_lbmolph` | 2386.93 | 2386.93 |

## Worst Component Net Worsenings

| Time s | Component | Field | Ratio | Abs delta | Candidate | Baseline |
|---:|---|---|---:|---:|---:|---:|
| 30 | n_Propane | `top_L_net_component_lbmolph` | 4.77969 | 318.561 | 402.844 | -84.2824 |
| 40 | n_Propane | `top_L_net_component_lbmolph` | 3.26881 | 165.921 | -239.053 | -73.1315 |
| 10 | n_Propane | `top_L_net_component_lbmolph` | 1.81695 | 91.1201 | -202.657 | -111.537 |
| 20 | n_Propane | `top_L_net_component_lbmolph` | 1.45301 | 41.9617 | 134.59 | -92.6286 |
| 10 | n_Butane | `top_L_net_component_lbmolph` | 1.02375 | 11.1388 | -480.233 | 469.095 |
| 40 | n_Butane | `top_L_net_component_lbmolph` | 1.00475 | 2.8124 | 595.012 | 592.2 |
| 40 | n_Pentane | `top_L_net_component_lbmolph` | 0.970366 | -0.0115342 | 0.377682 | 0.389216 |
| 10 | n_Pentane | `top_L_net_component_lbmolph` | 0.11577 | -0.0973587 | -0.0127469 | 0.110106 |

## Worst Total Net Worsenings

| Time s | Component | Field | Ratio | Abs delta | Candidate | Baseline |
|---:|---|---|---:|---:|---:|---:|
| 10 | total | `top_L_net_lbmolph` | 1.90932 | 325.235 | -682.903 | 357.668 |
| 40 | total | `top_L_net_lbmolph` | 0.685979 | -163.121 | 356.337 | 519.457 |
| 20 | total | `top_L_net_lbmolph` | 0.447605 | -252.961 | -204.974 | 457.935 |
| 30 | total | `top_L_net_lbmolph` | 0.166796 | -417.879 | 83.6535 | 501.533 |

## Worst Worst-Component Worsenings

| Time s | Component | Field | Ratio | Abs delta | Candidate | Baseline |
|---:|---|---|---:|---:|---:|---:|
| 10 | worst | `top_L_net_worst_abs_lbmolph` | 1.02375 | 11.1388 | 480.233 | 469.095 |
| 40 | worst | `top_L_net_worst_abs_lbmolph` | 1.00475 | 2.8124 | 595.012 | 592.2 |
| 30 | worst | `top_L_net_worst_abs_lbmolph` | 0.688039 | -182.652 | 402.844 | 585.496 |
| 20 | worst | `top_L_net_worst_abs_lbmolph` | 0.617068 | -210.74 | 339.592 | 550.332 |

## Worst Condensed-vs-Drum Composition Worsenings

| Time s | Component | Field | Ratio | Abs delta | Candidate | Baseline |
|---:|---|---|---:|---:|---:|---:|
| 10 | n_Butane | `top_L_cond_x_minus_drum_x` | 1.37053 | 0.0183982 | -0.0680514 | 0.0496532 |
| 10 | n_Propane | `top_L_cond_x_minus_drum_x` | 1.37022 | 0.0183873 | 0.0680528 | -0.0496655 |
| 40 | n_Pentane | `top_L_cond_x_minus_drum_x` | 0.991208 | -3.77529e-07 | 4.2563e-05 | 4.29405e-05 |
| 10 | n_Pentane | `top_L_cond_x_minus_drum_x` | 0.119337 | -1.08655e-05 | -1.47237e-06 | 1.23378e-05 |
| 20 | n_Pentane | `top_L_cond_x_minus_drum_x` | 0.123639 | -2.25947e-05 | 3.18773e-06 | 2.57824e-05 |
| 30 | n_Pentane | `top_L_cond_x_minus_drum_x` | 0.107516 | -3.16068e-05 | 3.80763e-06 | 3.54145e-05 |
| 20 | n_Butane | `top_L_cond_x_minus_drum_x` | 0.980643 | -0.00110181 | -0.0558199 | 0.0569218 |
| 20 | n_Propane | `top_L_cond_x_minus_drum_x` | 0.980143 | -0.00113078 | 0.0558168 | -0.0569475 |
