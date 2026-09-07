# Feed Stage Equation Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_productdrawfix_liqhyd_a025_truelevel_1800s_20260709\column_profile_20260709_152005.csv`

## Summary

| Check | Value |
|---|---:|
| feed stage, 1-based | 12 |
| time window, s | 0 to 1800 |
| feed-stage rows | 91 |
| min liquid inventory, lbmol | 51.0621 at 0 s |
| max feed vapor-fraction step | 0 at 40 s |
| worst inventory update fraction | 0.174525 at 1280 s |
| max liquid closure residual, lbmol/s | 0 |
| max feed-liquid residual, lbmol/s | 0 |
| max pre-phase flow residual, lbmol/s | 1.05471e-15 |
| max `L_out_used - L_out_hyd`, lbmol/h | 8248.99 at 1380 s |
| max feed energy term delta, BTU/s | 0 |
| max pressure-basis delta, psi | 0 |
| max stage energy residual, BTU/s | 2616.44 |
| max raw dT, F/s | 1.54682e-15 |
| first score above 10 | 100 s |
| peak score | 24.596 |
| final score | 0.724151 |

## Interpretation

- This audit is keyed to the generic feed-bearing stage inferred from `feed_stage_1based`.
- `liquid_total_closure_resid` checks `dMLdt_total - (pre_phase_liquid + phase_relax)`.
- `feed_liquid_resid` checks whether the liquid feed source equals the reported feed liquid rate.
- `pre_phase_flow_resid` compares the pre-equilibrium liquid derivative against logged liquid in/out traffic plus feed.
- `L_out_used - L_out_hyd` shows whether the marched liquid traffic follows the hydraulic candidate or a profile/blended flow.
- Large feed vapor-fraction steps plus low liquid inventory identify timestep-sensitive composition updates.

## Liquid Balance Samples

| time_s | ML_lbmol | feed_vf | dMLdt_total | feed_L | L_out_used | L_out_hyd | used-hyd | liquid_closure | pre_phase_flow_resid |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 51.0621 | nan | nan | nan | nan | nan | nan | nan | nan |
| 20 | 51.4667 | 0 | 0.0184132 | 1.98416 | 11408.5 | 8517.51 | 2891.01 | 0 | 3.88578e-16 |
| 440 | 58.5145 | 0 | 0.0408714 | 1.98416 | 12090.8 | 11246.5 | 844.261 | 0 | -4.44089e-16 |
| 820 | 69.8678 | 0 | -0.000834412 | 1.98416 | 12819.3 | 16143 | -3323.74 | 0 | -3.33067e-16 |
| 900 | 68.8257 | 0 | 0.00157891 | 1.98416 | 13196.5 | 15669.5 | -2472.95 | 0 | 0 |
| 1280 | 68.7971 | 0 | 0.600341 | 1.98416 | 12555.6 | 15656.5 | -3100.95 | 0 | -2.22045e-16 |
| 1360 | 77.499 | 0 | 0.260805 | 1.98416 | 12796.9 | 19750.6 | -6953.66 | 0 | 2.77556e-16 |
| 1380 | 80.7767 | 0 | 0.141826 | 1.98416 | 13124 | 21373 | -8248.99 | 0 | 0 |
| 1800 | 72.7748 | 0 | -0.102496 | 1.98416 | 13434.9 | 17488.6 | -4053.7 | 0 | -1.66533e-16 |

## Energy Basis Samples

| time_s | feed_energy_delta_BTUps | pressure_basis_delta_psia | energy_resid_BTUps | dT_raw_F_per_s |
|---:|---:|---:|---:|---:|
| 0 | nan | nan | nan | nan |
| 440 | 0 | 0 | -144.238 | 0 |
| 900 | 0 | 0 | 7.25458 | 0 |
| 1360 | 0 | 0 | -1086.61 | 0 |
| 1800 | 0 | 0 | 781.626 | 0 |

## Components By Liquid Composition Step

| component | max_x_step | time_s | before | after | max_final_vapor_rhs | max_eq_transfer | max_K_delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| eq_n_Propane | 0.0244094 | 180 | 0.305119 | 0.28071 | nan | nan | nan |
| eq_n_Butane | 0.0198792 | 180 | 0.615545 | 0.635424 | nan | nan | nan |
| n_Butane | 0.00852289 | 200 | 0.617116 | 0.608594 | 0.0536551 | 0.0776253 | 0.342213 |
| n_Propane | 0.00737678 | 200 | 0.298507 | 0.305884 | 0.0633301 | 0.0854195 | 0.77926 |
| eq_n_Pentane | 0.00453023 | 180 | 0.0793365 | 0.0838667 | nan | nan | nan |
| n_Pentane | 0.00167056 | 1580 | 0.0759033 | 0.0775739 | 0.0095051 | 0.0108567 | 0.430037 |
