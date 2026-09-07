# Overhead Feasibility Audit

Summary CSV: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_truelevel_fixedcond_Q42MM_no_topv_condense_1800s_20260709\column_summary_20260709_190946.csv`
Profile CSV: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_truelevel_fixedcond_Q42MM_no_topv_condense_1800s_20260709\column_profile_20260709_190946.csv`
Diagnosis: `top_starved_before_distillate`

## Top Boundary

| Metric | Final | Final-window mean |
|---|---:|---:|
| `condensate_lbmolph` | 5335.1 | 5117.21 |
| `reflux_lbmolph` | 5967.32 | 5967.32 |
| `distillate_lbmolph` | 621.511 | 885.861 |
| `top_draw_demand_lbmolph` | 6588.83 | 6853.18 |
| `condensate_minus_reflux_lbmolph` | -632.219 | -850.115 |
| `condensate_minus_top_draws_lbmolph` | -1253.73 | -1735.98 |
| `reflux_to_distillate_ratio` | 9.60132 | 6.73618 |

## Reference

| Metric | Value |
|---|---:|
| `reference_reflux_lbmolph` | 5945.41 |
| `reference_distillate_lbmolph` | 2386.93 |
| `reference_overhead_condensate_demand_lbmolph` | 8332.34 |
| `final_condensate_fraction_of_reference` | 0.640289 |
| `mean_condensate_fraction_of_reference` | 0.614138 |

## Vapor Profile

| Metric | Value |
|---|---:|
| `top_stage` | 1 |
| `bottom_stage` | 20 |
| `top_stage_v_out_lbmolph` | 0 |
| `bottom_stage_v_out_lbmolph` | 8030.03 |
| `overhead_vapor_stage` | 2 |
| `overhead_vapor_to_condenser_lbmolph` | 5335.1 |
| `overhead_vapor_fraction_of_bottom` | 0.664394 |
| `top_vapor_fraction_of_bottom` | 0 |
| `vflow_clamped_fraction_in_final_window` | 0 |
| `largest_adjacent_vapor_drop_lbmolph` | 1734.21 from stage 17 to 16 |
