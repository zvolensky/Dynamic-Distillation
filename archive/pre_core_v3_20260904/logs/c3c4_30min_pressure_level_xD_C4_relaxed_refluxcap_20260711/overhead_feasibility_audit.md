# Overhead Feasibility Audit

Summary CSV: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_30min_pressure_level_xD_C4_relaxed_refluxcap_20260711\column_summary_20260711_083447.csv`
Profile CSV: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_30min_pressure_level_xD_C4_relaxed_refluxcap_20260711\column_profile_20260711_083447.csv`
Diagnosis: `top_starved_before_distillate`

## Top Boundary

| Metric | Final | Final-window mean |
|---|---:|---:|
| `condensate_lbmolph` | 6431.37 | 6503.89 |
| `reflux_lbmolph` | 7000 | 7000 |
| `distillate_lbmolph` | 1212.48 | 1341.65 |
| `top_draw_demand_lbmolph` | 8212.48 | 8341.65 |
| `condensate_minus_reflux_lbmolph` | -568.634 | -496.112 |
| `condensate_minus_top_draws_lbmolph` | -1781.12 | -1837.76 |
| `reflux_to_distillate_ratio` | 5.77327 | 5.21745 |

## Reference

| Metric | Value |
|---|---:|
| `reference_reflux_lbmolph` | 5967.32 |
| `reference_distillate_lbmolph` | 2387 |
| `reference_overhead_condensate_demand_lbmolph` | 8354.32 |
| `final_condensate_fraction_of_reference` | 0.769825 |
| `mean_condensate_fraction_of_reference` | 0.778506 |

## Vapor Profile

| Metric | Value |
|---|---:|
| `top_stage` | 1 |
| `bottom_stage` | 20 |
| `top_stage_v_out_lbmolph` | 0 |
| `bottom_stage_v_out_lbmolph` | 8030.03 |
| `overhead_vapor_stage` | 2 |
| `overhead_vapor_to_condenser_lbmolph` | 6542.1 |
| `overhead_vapor_fraction_of_bottom` | 0.814705 |
| `top_vapor_fraction_of_bottom` | 0 |
| `vflow_clamped_fraction_in_final_window` | 0 |
| `largest_adjacent_vapor_drop_lbmolph` | 321.456 from stage 19 to 18 |
