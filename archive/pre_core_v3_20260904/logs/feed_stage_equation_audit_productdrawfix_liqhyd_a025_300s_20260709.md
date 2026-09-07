# Feed Stage Equation Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_productdrawfix_liqhyd_a025_300s_20260709\column_profile_20260709_143713.csv`

## Summary

| Check | Value |
|---|---:|
| feed stage, 1-based | 12 |
| time window, s | 0 to 300 |
| feed-stage rows | 61 |
| min liquid inventory, lbmol | 51.0621 at 0 s |
| max feed vapor-fraction step | 0 at 10 s |
| worst inventory update fraction | 0.00218856 at 5 s |
| max liquid closure residual, lbmol/s | 0 |
| max feed-liquid residual, lbmol/s | 0 |
| max pre-phase flow residual, lbmol/s | 8.88178e-16 |
| max `L_out_used - L_out_hyd`, lbmol/h | 2975.26 at 5 s |
| max feed energy term delta, BTU/s | 0 |
| max pressure-basis delta, psi | 0 |
| max stage energy residual, BTU/s | 135.896 |
| max raw dT, F/s | 1.55482e-15 |
| first score above 10 | 125 s |
| peak score | 26.1338 |
| final score | 2.54283 |

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
| 5 | 51.1617 | 0 | 0.022394 | 1.98416 | 11380.4 | 8405.18 | 2975.26 | 0 | 2.22045e-16 |
| 75 | 52.2204 | 0 | 0.0102035 | 1.98416 | 11478.4 | 8797.14 | 2681.29 | 0 | 1.11022e-16 |
| 150 | 52.8192 | 0 | 0.0068189 | 1.98416 | 11534.5 | 9021.45 | 2513.06 | 0 | -1.66533e-16 |
| 170 | 52.9164 | 0 | -0.00137418 | 1.98416 | 11571.9 | 9058.03 | 2513.83 | 0 | 2.77556e-16 |
| 225 | 53.3696 | 0 | 0.00909456 | 1.98416 | 11586.5 | 9229.27 | 2357.19 | 0 | 6.66134e-16 |
| 300 | 54.3313 | 0 | 0.0178629 | 1.98416 | 11678.2 | 9596.17 | 2082.02 | 0 | 2.22045e-16 |

## Energy Basis Samples

| time_s | feed_energy_delta_BTUps | pressure_basis_delta_psia | energy_resid_BTUps | dT_raw_F_per_s |
|---:|---:|---:|---:|---:|
| 0 | nan | nan | nan | nan |
| 75 | 0 | 0 | -37.7139 | 0 |
| 150 | 0 | 0 | -36.1768 | 0 |
| 225 | 0 | 0 | -61.7481 | 0 |
| 300 | 0 | 0 | -10.3791 | 0 |

## Components By Liquid Composition Step

| component | max_x_step | time_s | before | after | max_final_vapor_rhs | max_eq_transfer | max_K_delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| eq_n_Propane | 0.012006 | 165 | 0.30486 | 0.292854 | nan | nan | nan |
| eq_n_Butane | 0.0100475 | 165 | 0.616375 | 0.626422 | nan | nan | nan |
| n_Propane | 0.00851155 | 160 | 0.296469 | 0.287957 | 0.187642 | 0.281 | 0.848813 |
| n_Butane | 0.00724486 | 160 | 0.619625 | 0.62687 | 0.193029 | 0.240759 | 0.370786 |
| eq_n_Pentane | 0.00195849 | 165 | 0.078765 | 0.0807235 | nan | nan | nan |
| n_Pentane | 0.00126669 | 160 | 0.083906 | 0.0851727 | 0.0356818 | 0.0402405 | 0.475557 |
