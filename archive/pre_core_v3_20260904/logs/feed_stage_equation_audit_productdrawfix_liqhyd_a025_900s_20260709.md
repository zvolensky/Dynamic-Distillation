# Feed Stage Equation Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_productdrawfix_liqhyd_a025_900s_20260709\column_profile_20260709_144051.csv`

## Summary

| Check | Value |
|---|---:|
| feed stage, 1-based | 12 |
| time window, s | 0 to 900 |
| feed-stage rows | 91 |
| min liquid inventory, lbmol | 51.0621 at 0 s |
| max feed vapor-fraction step | 0 at 20 s |
| worst inventory update fraction | 0.0448253 at 760 s |
| max liquid closure residual, lbmol/s | 0 |
| max feed-liquid residual, lbmol/s | 0 |
| max pre-phase flow residual, lbmol/s | 1.16573e-15 |
| max `L_out_used - L_out_hyd`, lbmol/h | 5489.08 at 830 s |
| max feed energy term delta, BTU/s | 0 |
| max pressure-basis delta, psi | 0 |
| max stage energy residual, BTU/s | 1257.73 |
| max raw dT, F/s | 1.54682e-15 |
| first score above 10 | 150 s |
| peak score | 17.0274 |
| final score | 1.54494 |

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
| 10 | 51.2701 | 0 | 0.0209416 | 1.98416 | 11390.4 | 8445.04 | 2945.36 | 0 | 2.22045e-16 |
| 220 | 53.325 | 0 | 0.00874178 | 1.98416 | 11582.2 | 9212.39 | 2369.85 | 0 | -5.55112e-17 |
| 450 | 58.9989 | 0 | 0.0417025 | 1.98416 | 12139.9 | 11443.2 | 696.772 | 0 | 7.21645e-16 |
| 670 | 67.8627 | 0 | 8.5218e-05 | 1.98416 | 13088.1 | 15236 | -2147.87 | 0 | 4.44089e-16 |
| 680 | 67.8265 | 0 | -0.00815441 | 1.98416 | 13084.1 | 15219.8 | -2135.7 | 0 | -2.22045e-16 |
| 760 | 64.4227 | 0 | 0.288777 | 1.98416 | 12499.3 | 13721.3 | -1222.01 | 0 | -3.33067e-16 |
| 830 | 74.6792 | 0 | 0.170235 | 1.98416 | 12900.3 | 18389.4 | -5489.08 | 0 | 5.55112e-16 |
| 900 | 70.0968 | 0 | -0.184431 | 1.98416 | 13341.1 | 16247.7 | -2906.63 | 0 | -5.55112e-17 |

## Energy Basis Samples

| time_s | feed_energy_delta_BTUps | pressure_basis_delta_psia | energy_resid_BTUps | dT_raw_F_per_s |
|---:|---:|---:|---:|---:|
| 0 | nan | nan | nan | nan |
| 220 | 0 | 0 | -64.1981 | 0 |
| 450 | 0 | 0 | -144.308 | 0 |
| 680 | 0 | 0 | 78.4461 | 0 |
| 900 | 0 | 0 | 872.602 | 0 |

## Components By Liquid Composition Step

| component | max_x_step | time_s | before | after | max_final_vapor_rhs | max_eq_transfer | max_K_delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| eq_n_Propane | 0.0174809 | 170 | 0.30486 | 0.28738 | nan | nan | nan |
| eq_n_Butane | 0.0142724 | 170 | 0.616375 | 0.630647 | nan | nan | nan |
| n_Propane | 0.00968955 | 180 | 0.296385 | 0.306075 | 0.097089 | 0.281 | 0.848813 |
| n_Butane | 0.00873295 | 180 | 0.619289 | 0.610556 | 0.0869695 | 0.240759 | 0.370786 |
| eq_n_Pentane | 0.00320852 | 170 | 0.078765 | 0.0819735 | nan | nan | nan |
| n_Pentane | 0.00150782 | 200 | 0.0841944 | 0.0857022 | 0.0194087 | 0.0402405 | 0.475557 |
