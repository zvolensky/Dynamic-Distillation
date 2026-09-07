# Feed Stage Equation Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_stagefeedflash_k1fix_900s_20260709\column_profile_20260709_140837.csv`

## Summary

| Check | Value |
|---|---:|
| feed stage, 1-based | 12 |
| time window, s | 0 to 900 |
| feed-stage rows | 181 |
| min liquid inventory, lbmol | 12.9216 at 900 s |
| max feed vapor-fraction step | 0 at 10 s |
| worst inventory update fraction | 0.0161337 at 895 s |
| max liquid closure residual, lbmol/s | 0 |
| max feed-liquid residual, lbmol/s | 0 |
| max pre-phase flow residual, lbmol/s | 1.11022e-15 |
| max feed energy term delta, BTU/s | 0 |
| max pressure-basis delta, psi | 0 |
| max stage energy residual, BTU/s | 356.443 |
| max raw dT, F/s | 1.99881e-15 |
| first score above 10 | 150 s |
| peak score | 23.0505 |
| final score | 0.970254 |

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
| 5 | 50.8502 | 0 | -0.0423784 | 1.98416 | 0 | 3.88578e-16 |
| 225 | 41.527 | 0 | -0.0423784 | 1.98416 | 0 | 1.11022e-15 |
| 450 | 31.9919 | 0 | -0.0423784 | 1.98416 | 0 | 1.66533e-16 |
| 575 | 26.6946 | 0 | -0.0423784 | 1.98416 | 0 | -6.10623e-16 |
| 675 | 22.4567 | 0 | -0.0423784 | 1.98416 | 0 | 1.66533e-16 |
| 900 | 12.9216 | 0 | -0.0423784 | 1.98416 | 0 | 5.55112e-17 |

## Energy Basis Samples

| time_s | feed_energy_delta_BTUps | pressure_basis_delta_psia | energy_resid_BTUps | dT_raw_F_per_s |
|---:|---:|---:|---:|---:|
| 0 | nan | nan | nan | nan |
| 225 | 0 | 0 | 199.526 | 0 |
| 450 | 0 | 0 | 220.567 | 0 |
| 675 | 0 | 0 | 252.229 | 0 |
| 900 | 0 | 0 | 263.971 | 0 |

## Components By Liquid Composition Step

| component | max_x_step | time_s | before | after | max_final_vapor_rhs | max_eq_transfer | max_K_delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| n_Propane | 0.0116155 | 210 | 0.290678 | 0.302293 | 0.215861 | 0.129648 | 0.884186 |
| n_Butane | 0.00988069 | 210 | 0.625278 | 0.615397 | 0.252589 | 0.10802 | 0.387501 |
| eq_n_Propane | 0.00612652 | 210 | 0.300975 | 0.294849 | nan | nan | nan |
| eq_n_Butane | 0.00463161 | 210 | 0.620175 | 0.624806 | nan | nan | nan |
| n_Pentane | 0.00202247 | 205 | 0.0820219 | 0.0840444 | 0.0512046 | 0.0216282 | 0.491512 |
| eq_n_Pentane | 0.00149491 | 210 | 0.07885 | 0.0803449 | nan | nan | nan |
