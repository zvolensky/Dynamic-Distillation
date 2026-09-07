# Feed Stage Equation Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_productdrawfix_liqhyd_a025_1800s_20260709\column_profile_20260709_145527.csv`

## Summary

| Check | Value |
|---|---:|
| feed stage, 1-based | 12 |
| time window, s | 0 to 1800 |
| feed-stage rows | 91 |
| min liquid inventory, lbmol | 51.0621 at 0 s |
| max feed vapor-fraction step | 0 at 40 s |
| worst inventory update fraction | 0.115809 at 1780 s |
| max liquid closure residual, lbmol/s | 0 |
| max feed-liquid residual, lbmol/s | 0 |
| max pre-phase flow residual, lbmol/s | 7.77156e-16 |
| max `L_out_used - L_out_hyd`, lbmol/h | 7908.04 at 1400 s |
| max feed energy term delta, BTU/s | 0 |
| max pressure-basis delta, psi | 0 |
| max stage energy residual, BTU/s | 1991.93 |
| max raw dT, F/s | 1.54682e-15 |
| first score above 10 | 160 s |
| peak score | 17.0274 |
| final score | 1.17976 |

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
| 440 | 58.5959 | 0 | 0.0402303 | 1.98416 | 12099 | 11279.5 | 819.535 | 0 | 0 |
| 900 | 70.0968 | 0 | -0.184431 | 1.98416 | 13341.1 | 16247.7 | -2906.63 | 0 | -5.55112e-17 |
| 1260 | 66.8926 | 0 | 0.000616984 | 1.98416 | 12980 | 14803.5 | -1823.51 | 0 | 2.22045e-16 |
| 1360 | 78.5838 | 0 | -0.158464 | 1.98416 | 14349.9 | 20282.8 | -5932.99 | 0 | -3.88578e-16 |
| 1380 | 80.2631 | 0 | 0.0280474 | 1.98416 | 13478 | 21116 | -7637.97 | 0 | -5.55112e-16 |
| 1440 | 74.6412 | 0 | -0.405524 | 1.98416 | 13872 | 18371.3 | -4499.33 | 0 | 3.88578e-16 |
| 1800 | 70.0984 | 0 | 0.303867 | 1.98416 | 13341.3 | 16248.4 | -2907.18 | 0 | -3.33067e-16 |

## Energy Basis Samples

| time_s | feed_energy_delta_BTUps | pressure_basis_delta_psia | energy_resid_BTUps | dT_raw_F_per_s |
|---:|---:|---:|---:|---:|
| 0 | nan | nan | nan | nan |
| 440 | 0 | 0 | -137.369 | 0 |
| 900 | 0 | 0 | 872.602 | 0 |
| 1360 | 0 | 0 | 875.362 | 0 |
| 1800 | 0 | 0 | -1152.76 | 0 |

## Components By Liquid Composition Step

| component | max_x_step | time_s | before | after | max_final_vapor_rhs | max_eq_transfer | max_K_delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| eq_n_Propane | 0.0186555 | 180 | 0.30486 | 0.286205 | nan | nan | nan |
| n_Propane | 0.0181174 | 180 | 0.287957 | 0.306075 | 0.0441629 | 0.281 | 0.848813 |
| n_Butane | 0.016314 | 180 | 0.62687 | 0.610556 | 0.0536797 | 0.240759 | 0.370786 |
| eq_n_Butane | 0.0143157 | 180 | 0.616375 | 0.63069 | nan | nan | nan |
| eq_n_Pentane | 0.00433988 | 180 | 0.078765 | 0.0831049 | nan | nan | nan |
| n_Pentane | 0.00233299 | 200 | 0.0833692 | 0.0857022 | 0.0078754 | 0.0402405 | 0.475557 |
