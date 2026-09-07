# Overhead Feasibility Audit

Summary CSV: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_dd044_exponential_eq_continue290s_topKc5_20260711\column_summary_20260711_095431.csv`
Profile CSV: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_dd044_exponential_eq_continue290s_topKc5_20260711\column_profile_20260711_095431.csv`
Diagnosis: `top_overhead_feasible_at_final_time`

## Top Boundary

| Metric | Final | Final-window mean |
|---|---:|---:|
| `condensate_lbmolph` | 7605.17 | 7411.56 |
| `reflux_lbmolph` | 5967.32 | 5967.32 |
| `distillate_lbmolph` | 458.152 | 553.875 |
| `top_draw_demand_lbmolph` | 6425.48 | 6521.2 |
| `condensate_minus_reflux_lbmolph` | 1637.85 | 1444.24 |
| `condensate_minus_top_draws_lbmolph` | 1179.69 | 890.364 |
| `reflux_to_distillate_ratio` | 13.0248 | 10.7738 |

## Reference

| Metric | Value |
|---|---:|
| `reference_reflux_lbmolph` | 5967.32 |
| `reference_distillate_lbmolph` | 2387 |
| `reference_overhead_condensate_demand_lbmolph` | 8354.32 |
| `final_condensate_fraction_of_reference` | 0.910327 |
| `mean_condensate_fraction_of_reference` | 0.887153 |

## Vapor Profile

| Metric | Value |
|---|---:|
| `top_stage` | 1 |
| `bottom_stage` | 20 |
| `top_stage_v_out_lbmolph` | 0 |
| `bottom_stage_v_out_lbmolph` | 8030.03 |
| `overhead_vapor_stage` | 2 |
| `overhead_vapor_to_condenser_lbmolph` | 7605.17 |
| `overhead_vapor_fraction_of_bottom` | 0.947092 |
| `top_vapor_fraction_of_bottom` | 0 |
| `vflow_clamped_fraction_in_final_window` | 0 |
| `largest_adjacent_vapor_drop_lbmolph` | 380.504 from stage 20 to 19 |
