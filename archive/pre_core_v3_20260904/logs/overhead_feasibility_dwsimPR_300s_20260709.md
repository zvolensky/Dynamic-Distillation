# Overhead Feasibility Audit

Summary CSV: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_truelevel_fixedcond_Q42MM_dwsimPR_300s_20260709\column_summary_20260709_212607.csv`
Profile CSV: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_truelevel_fixedcond_Q42MM_dwsimPR_300s_20260709\column_profile_20260709_212607.csv`
Diagnosis: `top_overhead_feasible_at_final_time`

## Top Boundary

| Metric | Final | Final-window mean |
|---|---:|---:|
| `condensate_lbmolph` | 8361.16 | 8582.91 |
| `reflux_lbmolph` | 5967.32 | 5967.32 |
| `distillate_lbmolph` | 2378.25 | 2371.97 |
| `top_draw_demand_lbmolph` | 8345.57 | 8339.3 |
| `condensate_minus_reflux_lbmolph` | 2393.84 | 2615.59 |
| `condensate_minus_top_draws_lbmolph` | 15.5889 | 243.614 |
| `reflux_to_distillate_ratio` | 2.50912 | 2.51576 |

## Reference

| Metric | Value |
|---|---:|
| `reference_reflux_lbmolph` | nan |
| `reference_distillate_lbmolph` | nan |
| `reference_overhead_condensate_demand_lbmolph` | nan |
| `final_condensate_fraction_of_reference` | nan |
| `mean_condensate_fraction_of_reference` | nan |

## Vapor Profile

| Metric | Value |
|---|---:|
| `top_stage` | 1 |
| `bottom_stage` | 20 |
| `top_stage_v_out_lbmolph` | 0 |
| `bottom_stage_v_out_lbmolph` | 8030.03 |
| `overhead_vapor_stage` | 2 |
| `overhead_vapor_to_condenser_lbmolph` | 8361.16 |
| `overhead_vapor_fraction_of_bottom` | 1.04124 |
| `top_vapor_fraction_of_bottom` | 0 |
| `vflow_clamped_fraction_in_final_window` | 0 |
| `largest_adjacent_vapor_drop_lbmolph` | 181.775 from stage 20 to 19 |
