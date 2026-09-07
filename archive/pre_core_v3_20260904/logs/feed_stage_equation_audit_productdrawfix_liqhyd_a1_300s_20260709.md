# Feed Stage Equation Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_productdrawfix_liqhyd_a1_300s_20260709\column_profile_20260709_143350.csv`

## Summary

| Check | Value |
|---|---:|
| feed stage, 1-based | 12 |
| time window, s | 0 to 300 |
| feed-stage rows | 61 |
| min liquid inventory, lbmol | 50.4436 at 5 s |
| max feed vapor-fraction step | 0 at 10 s |
| worst inventory update fraction | 0.0996033 at 20 s |
| max liquid closure residual, lbmol/s | 0 |
| max feed-liquid residual, lbmol/s | 0 |
| max pre-phase flow residual, lbmol/s | 6.66134e-16 |
| max `L_out_used - L_out_hyd`, lbmol/h | 3958.35 at 5 s |
| max feed energy term delta, BTU/s | 0 |
| max pressure-basis delta, psi | 0 |
| max stage energy residual, BTU/s | 4401.59 |
| max raw dT, F/s | 1.56114e-15 |
| first score above 10 | 40 s |
| peak score | 26.8139 |
| final score | 2.714 |

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
| 5 | 50.4436 | 0 | -0.0404086 | 1.98416 | 12101.1 | 8142.74 | 3958.35 | 0 | -5.55112e-16 |
| 20 | 50.9621 | 0 | 1.0152 | 1.98416 | 8331.98 | 8331.98 | 0 | 0 | 2.22045e-16 |
| 75 | 52.7542 | 0 | 0.606907 | 1.98416 | 9759.32 | 8997.02 | 762.297 | 0 | -3.33067e-16 |
| 150 | 53.3694 | 0 | -0.649565 | 1.98416 | 11927.7 | 9229.21 | 2698.47 | 0 | 2.22045e-16 |
| 225 | 58.3401 | 0 | 0.26236 | 1.98416 | 11176 | 11176 | 0 | 0 | 2.22045e-16 |
| 300 | 62.9904 | 0 | 0.00169068 | 1.98416 | 13106.4 | 13106.4 | 0 | 0 | 1.66533e-16 |

## Energy Basis Samples

| time_s | feed_energy_delta_BTUps | pressure_basis_delta_psia | energy_resid_BTUps | dT_raw_F_per_s |
|---:|---:|---:|---:|---:|
| 0 | nan | nan | nan | nan |
| 75 | 0 | 0 | -2606.11 | 0 |
| 150 | 0 | 0 | 2653.13 | 0 |
| 225 | 0 | 0 | -1031.3 | 0 |
| 300 | 0 | 0 | 45.9584 | 0 |

## Components By Liquid Composition Step

| component | max_x_step | time_s | before | after | max_final_vapor_rhs | max_eq_transfer | max_K_delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| n_Propane | 0.0213836 | 90 | 0.295905 | 0.274521 | 0.422481 | 0.266404 | 0.876409 |
| n_Butane | 0.0174741 | 90 | 0.615646 | 0.63312 | 0.430068 | 0.227101 | 0.37249 |
| eq_n_Propane | 0.0163446 | 95 | 0.297477 | 0.281132 | nan | nan | nan |
| eq_n_Butane | 0.0131533 | 95 | 0.61787 | 0.631023 | nan | nan | nan |
| n_Pentane | 0.00390953 | 90 | 0.0884497 | 0.0923592 | 0.0869441 | 0.0393029 | 0.628779 |
| eq_n_Pentane | 0.00319132 | 95 | 0.0846535 | 0.0878448 | nan | nan | nan |
