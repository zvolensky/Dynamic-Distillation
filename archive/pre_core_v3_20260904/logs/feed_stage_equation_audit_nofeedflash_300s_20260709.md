# Feed Stage Equation Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_liq_eq_vap_linearsteady_300s_eqcompguard_m1_feedflash_20260709\column_profile_20260709_095126.csv`

## Summary

| Check | Value |
|---|---:|
| feed stage, 1-based | 12 |
| time window, s | 0 to 300 |
| feed-stage rows | 61 |
| min liquid inventory, lbmol | 38.3486 at 300 s |
| max feed vapor-fraction step | nan at nan s |
| worst inventory update fraction | 0.00549504 at 295 s |
| max liquid closure residual, lbmol/s | 0 |
| max feed-liquid residual, lbmol/s | nan |
| max pre-phase flow residual, lbmol/s | 1.38778e-15 |
| max feed energy term delta, BTU/s | 0 |
| max pressure-basis delta, psi | 0 |
| max stage energy residual, BTU/s | 275.937 |
| max raw dT, F/s | 1.99876e-15 |
| first score above 10 | 155 s |
| peak score | 22.681 |
| final score | 2.2646 |

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
| 75 | 47.8838 | nan | -0.0423784 | nan | 0 | 2.77556e-16 |
| 105 | 46.6124 | nan | -0.0423784 | nan | 0 | -7.77156e-16 |
| 150 | 44.7054 | nan | -0.0423784 | nan | 0 | -1.11022e-16 |
| 225 | 41.527 | nan | -0.0423784 | nan | 0 | 5.55112e-17 |
| 245 | 40.6794 | nan | -0.0423784 | nan | 0 | 1.38778e-15 |
| 300 | 38.3486 | nan | -0.0423784 | nan | 0 | 8.32667e-16 |

## Energy Basis Samples

| time_s | feed_energy_delta_BTUps | pressure_basis_delta_psia | energy_resid_BTUps | dT_raw_F_per_s |
|---:|---:|---:|---:|---:|
| 0 | nan | nan | nan | nan |
| 75 | 0 | 0 | 195.922 | 0 |
| 150 | 0 | 0 | 192.983 | 0 |
| 225 | 0 | 0 | 189.563 | 0 |
| 300 | 0 | 0 | 244.735 | 0 |

## Components By Liquid Composition Step

| component | max_x_step | time_s | before | after | max_final_vapor_rhs | max_eq_transfer | max_K_delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| n_Propane | 0.009766 | 210 | 0.295275 | 0.305041 | 0.177566 | 0.0952903 | 0.884733 |
| n_Butane | 0.00837988 | 210 | 0.621515 | 0.613135 | 0.224893 | 0.0794646 | 0.387615 |
| eq_n_Propane | 0.00571435 | 210 | 0.302584 | 0.29687 | nan | nan | nan |
| eq_n_Butane | 0.00433368 | 210 | 0.618909 | 0.623243 | nan | nan | nan |
| n_Pentane | 0.00138612 | 210 | 0.0832106 | 0.0818245 | 0.0442968 | 0.0158257 | 0.491443 |
| eq_n_Pentane | 0.00138067 | 210 | 0.0785067 | 0.0798874 | nan | nan | nan |
