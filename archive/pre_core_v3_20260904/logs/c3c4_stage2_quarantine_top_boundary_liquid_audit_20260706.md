# Top Boundary Liquid Coupling Audit

Baseline: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_baseline_thermoprov_60s_20260706b\column_summary_20260706_202739.csv`
Candidate: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_quarantine_40s_20260706\column_summary_20260706_204812.csv`
Final compared time: `40 s`

## Final Summary

| Metric | Baseline | Candidate |
|---|---:|---:|
| `top_L_net_lbmolph` | 519.457 | 433.364 |
| `top_L_net_worst_component_1based` | 2 | 2 |
| `top_L_net_worst_abs_lbmolph` | 592.2 | 728.128 |
| `V_condensed_in_lbmolph` | 8873.71 | 8787.62 |
| `top_L_reflux_out_lbmolph` | 5967.32 | 5967.32 |
| `top_L_distillate_out_lbmolph` | 2386.93 | 2386.93 |

## Worst Component Net Worsenings

| Time s | Component | Field | Ratio | Abs delta | Candidate | Baseline |
|---:|---|---|---:|---:|---:|---:|
| 10 | n_Propane | `top_L_net_component_lbmolph` | 5.48344 | 500.067 | -611.604 | -111.537 |
| 40 | n_Propane | `top_L_net_component_lbmolph` | 4.03573 | 222.007 | -295.139 | -73.1315 |
| 40 | n_Butane | `top_L_net_component_lbmolph` | 1.22953 | 135.929 | 728.128 | 592.2 |
| 20 | n_Propane | `top_L_net_component_lbmolph` | 1.83213 | 77.0785 | -169.707 | -92.6286 |
| 30 | n_Propane | `top_L_net_component_lbmolph` | 1.84867 | 71.5279 | 155.81 | -84.2824 |
| 40 | n_Pentane | `top_L_net_component_lbmolph` | 0.960918 | -0.0152115 | 0.374005 | 0.389216 |
| 10 | n_Pentane | `top_L_net_component_lbmolph` | 0.13926 | -0.0947724 | 0.0153333 | 0.110106 |
| 20 | n_Pentane | `top_L_net_component_lbmolph` | 0.194499 | -0.186361 | 0.0449995 | 0.231361 |

## Worst Total Net Worsenings

| Time s | Component | Field | Ratio | Abs delta | Candidate | Baseline |
|---:|---|---|---:|---:|---:|---:|
| 10 | total | `top_L_net_lbmolph` | 1.92757 | 331.763 | -689.432 | 357.668 |
| 40 | total | `top_L_net_lbmolph` | 0.834262 | -86.0939 | 433.364 | 519.457 |
| 20 | total | `top_L_net_lbmolph` | 0.378446 | -284.632 | -173.304 | 457.935 |
| 30 | total | `top_L_net_lbmolph` | 0.256949 | -372.664 | 128.868 | 501.533 |

## Worst Worst-Component Worsenings

| Time s | Component | Field | Ratio | Abs delta | Candidate | Baseline |
|---:|---|---|---:|---:|---:|---:|
| 10 | worst | `top_L_net_worst_abs_lbmolph` | 1.3038 | 142.509 | 611.604 | 469.095 |
| 40 | worst | `top_L_net_worst_abs_lbmolph` | 1.22953 | 135.929 | 728.128 | 592.2 |
| 20 | worst | `top_L_net_worst_abs_lbmolph` | 0.308372 | -380.625 | 169.707 | 550.332 |
| 30 | worst | `top_L_net_worst_abs_lbmolph` | 0.266117 | -429.685 | 155.81 | 585.496 |

## Worst Condensed-vs-Drum Composition Worsenings

| Time s | Component | Field | Ratio | Abs delta | Candidate | Baseline |
|---:|---|---|---:|---:|---:|---:|
| 40 | n_Butane | `top_L_cond_x_minus_drum_x` | 1.30306 | 0.018148 | 0.0780299 | 0.0598819 |
| 40 | n_Propane | `top_L_cond_x_minus_drum_x` | 1.30283 | 0.0181472 | -0.078072 | -0.0599248 |
| 40 | n_Pentane | `top_L_cond_x_minus_drum_x` | 0.980618 | -8.32253e-07 | 4.21083e-05 | 4.29405e-05 |
| 10 | n_Pentane | `top_L_cond_x_minus_drum_x` | 0.203217 | -9.83058e-06 | 2.50726e-06 | 1.23378e-05 |
| 20 | n_Pentane | `top_L_cond_x_minus_drum_x` | 0.216659 | -2.01964e-05 | 5.586e-06 | 2.57824e-05 |
| 30 | n_Pentane | `top_L_cond_x_minus_drum_x` | 0.160878 | -2.9717e-05 | 5.69743e-06 | 3.54145e-05 |
| 10 | n_Butane | `top_L_cond_x_minus_drum_x` | 0.0347195 | -0.0479292 | -0.00172393 | 0.0496532 |
| 10 | n_Propane | `top_L_cond_x_minus_drum_x` | 0.0346604 | -0.0479441 | 0.00172143 | -0.0496655 |
