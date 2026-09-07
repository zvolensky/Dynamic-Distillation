# Overhead Feasibility Audit

Summary CSV: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_dd044_exponential_eq_continue600s_to900_topKc5_20260711\column_summary_20260711_100559.csv`
Profile CSV: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_dd044_exponential_eq_continue600s_to900_topKc5_20260711\column_profile_20260711_100559.csv`
Diagnosis: `overhead_vapor_below_reference`

## Top Boundary

| Metric | Final | Final-window mean |
|---|---:|---:|
| `condensate_lbmolph` | 7457.89 | 7512.51 |
| `reflux_lbmolph` | 5967.32 | 5967.32 |
| `distillate_lbmolph` | 340.809 | 273.601 |
| `top_draw_demand_lbmolph` | 6308.13 | 6240.92 |
| `condensate_minus_reflux_lbmolph` | 1490.57 | 1545.19 |
| `condensate_minus_top_draws_lbmolph` | 1149.76 | 1271.58 |
| `reflux_to_distillate_ratio` | 17.5093 | 21.8103 |

## Reference

| Metric | Value |
|---|---:|
| `reference_reflux_lbmolph` | 5967.32 |
| `reference_distillate_lbmolph` | 2387 |
| `reference_overhead_condensate_demand_lbmolph` | 8354.32 |
| `final_condensate_fraction_of_reference` | 0.892698 |
| `mean_condensate_fraction_of_reference` | 0.899236 |

## Vapor Profile

| Metric | Value |
|---|---:|
| `top_stage` | 1 |
| `bottom_stage` | 20 |
| `top_stage_v_out_lbmolph` | 0 |
| `bottom_stage_v_out_lbmolph` | 8030.03 |
| `overhead_vapor_stage` | 2 |
| `overhead_vapor_to_condenser_lbmolph` | 7457.89 |
| `overhead_vapor_fraction_of_bottom` | 0.92875 |
| `top_vapor_fraction_of_bottom` | 0 |
| `vflow_clamped_fraction_in_final_window` | 0 |
| `largest_adjacent_vapor_drop_lbmolph` | 402.598 from stage 20 to 19 |
