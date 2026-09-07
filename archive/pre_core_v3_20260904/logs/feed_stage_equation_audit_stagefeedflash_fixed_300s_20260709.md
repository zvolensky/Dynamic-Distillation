# Feed Stage Equation Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_stagefeedflash_fixed_300s_20260709\column_profile_20260709_100852.csv`

## Summary

| Check | Value |
|---|---:|
| feed stage, 1-based | 12 |
| time window, s | 0 to 300 |
| feed-stage rows | 61 |
| min liquid inventory, lbmol | 0.155514 at 200 s |
| max feed vapor-fraction step | 0.5 at 155 s |
| worst inventory update fraction | 5.17229 at 255 s |
| max liquid closure residual, lbmol/s | 0 |
| max feed-liquid residual, lbmol/s | 0 |
| max pre-phase flow residual, lbmol/s | 8.88178e-16 |
| max feed energy term delta, BTU/s | 15482.2 |
| max pressure-basis delta, psi | 0 |
| max stage energy residual, BTU/s | 3.47492e+06 |
| max raw dT, F/s | 184.478 |
| first score above 10 | 155 s |
| peak score | 491.009 |
| final score | 445.591 |

## Interpretation

- This audit is keyed to the generic feed-bearing stage inferred from `feed_stage_1based`.
- `liquid_total_closure_resid` checks `dMLdt_total - (pre_phase_liquid + phase_relax)`.
- `feed_liquid_resid` checks whether the liquid feed source equals the reported feed liquid rate.
- `pre_phase_flow_resid` compares the pre-equilibrium liquid derivative against logged liquid in/out traffic plus feed.
- Large feed vapor-fraction steps plus low liquid inventory identify timestep-sensitive composition updates.

## Liquid Balance Samples

| time_s | ML_lbmol | feed_vf | dMLdt_total | feed_L | liquid_closure | pre_phase_flow_resid |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 51.0621 | nan | nan | nan | nan | nan |
| 5 | 50.8502 | 0 | -0.0423784 | 1.98416 | 0 | 8.32667e-16 |
| 75 | 47.8838 | 0 | -0.0423784 | 1.98416 | 0 | 1.11022e-16 |
| 150 | 44.7054 | 0 | -0.0423784 | 1.98416 | 0 | 4.996e-16 |
| 200 | 0.155514 | 0.5 | -1.03446 | 0.99208 | 0 | 6.66134e-16 |
| 225 | 0.318806 | 0.5 | -1.03446 | 0.99208 | 0 | 4.44089e-16 |
| 245 | 0.340106 | 0 | -0.0423784 | 1.98416 | 0 | 8.88178e-16 |
| 290 | 0.211188 | 0.5 | -1.03446 | 0.99208 | 0 | 0 |
| 300 | 0.213133 | 0.5 | -1.03446 | 0.99208 | 0 | 6.66134e-16 |

## Energy Basis Samples

| time_s | feed_energy_delta_BTUps | pressure_basis_delta_psia | energy_resid_BTUps | dT_raw_F_per_s |
|---:|---:|---:|---:|---:|
| 0 | nan | nan | nan | nan |
| 75 | 0 | 0 | 194.413 | 0 |
| 150 | 0 | 0 | 194.427 | 0 |
| 225 | 0 | 0 | 3.47492e+06 | 169.233 |
| 300 | 0 | 0 | -3.4365e+06 | 6.36363 |

## Components By Liquid Composition Step

| component | max_x_step | time_s | before | after | max_final_vapor_rhs | max_eq_transfer | max_K_delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| n_Butane | 1 | 290 | 1 | 0 | 8.42034 | 0.128871 | 4.85863 |
| n_Propane | 1 | 205 | 1 | 0 | 3.81949 | 0.173441 | 4.4653 |
| n_Pentane | 0.157336 | 280 | 0 | 0.157336 | 0.850683 | 0.0445701 | 1.50191 |
| eq_n_Propane | 0.0368972 | 205 | 0.294998 | 0.2581 | nan | nan | nan |
| eq_n_Butane | 0.0285465 | 265 | 0.638713 | 0.66726 | nan | nan | nan |
| eq_n_Pentane | 0.0129104 | 255 | 0.0680032 | 0.0809136 | nan | nan | nan |
