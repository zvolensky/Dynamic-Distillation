# Feed Stage Equation Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_productdrawfix_300s_20260709\column_profile_20260709_142739.csv`

## Summary

| Check | Value |
|---|---:|
| feed stage, 1-based | 12 |
| time window, s | 0 to 300 |
| feed-stage rows | 61 |
| min liquid inventory, lbmol | 38.3486 at 300 s |
| max feed vapor-fraction step | 0 at 10 s |
| worst inventory update fraction | 0.00549504 at 295 s |
| max liquid closure residual, lbmol/s | 0 |
| max feed-liquid residual, lbmol/s | 0 |
| max pre-phase flow residual, lbmol/s | 9.4369e-16 |
| max `L_out_used - L_out_hyd`, lbmol/h | 8202.98 at 300 s |
| max feed energy term delta, BTU/s | 0 |
| max pressure-basis delta, psi | 0 |
| max stage energy residual, BTU/s | 276.778 |
| max raw dT, F/s | 2.01918e-15 |
| first score above 10 | 110 s |
| peak score | 19.9833 |
| final score | 2.269 |

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
| 5 | 50.8502 | 0 | -0.0423784 | 1.98416 | 12372.2 | 8291.02 | 4081.17 | 0 | 5.55112e-17 |
| 10 | 50.6384 | 0 | -0.0423784 | 1.98416 | 12372.2 | 8213.65 | 4158.55 | 0 | 2.77556e-16 |
| 75 | 47.8838 | 0 | -0.0423784 | 1.98416 | 12372.2 | 7230.11 | 5142.08 | 0 | 0 |
| 150 | 44.7054 | 0 | -0.0423784 | 1.98416 | 12372.2 | 6148.49 | 6223.7 | 0 | 3.33067e-16 |
| 225 | 41.527 | 0 | -0.0423784 | 1.98416 | 12372.2 | 5126.94 | 7245.26 | 0 | 1.66533e-16 |
| 270 | 39.62 | 0 | -0.0423784 | 1.98416 | 12372.2 | 4544.37 | 7827.82 | 0 | -5.55112e-16 |
| 300 | 38.3486 | 0 | -0.0423784 | 1.98416 | 12372.2 | 4169.21 | 8202.98 | 0 | 3.33067e-16 |

## Energy Basis Samples

| time_s | feed_energy_delta_BTUps | pressure_basis_delta_psia | energy_resid_BTUps | dT_raw_F_per_s |
|---:|---:|---:|---:|---:|
| 0 | nan | nan | nan | nan |
| 75 | 0 | 0 | 195.751 | 0 |
| 150 | 0 | 0 | 192.75 | 0 |
| 225 | 0 | 0 | 210.1 | 0 |
| 300 | 0 | 0 | 238.358 | 0 |

## Components By Liquid Composition Step

| component | max_x_step | time_s | before | after | max_final_vapor_rhs | max_eq_transfer | max_K_delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| n_Propane | 0.00900045 | 205 | 0.300727 | 0.291727 | 0.103616 | 0.239436 | 0.881875 |
| n_Butane | 0.00768946 | 210 | 0.624434 | 0.616744 | 0.102229 | 0.196974 | 0.385403 |
| eq_n_Propane | 0.00755775 | 210 | 0.303151 | 0.295593 | nan | nan | nan |
| eq_n_Butane | 0.00587115 | 210 | 0.618438 | 0.624309 | nan | nan | nan |
| n_Pentane | 0.00178321 | 205 | 0.0820566 | 0.0838398 | 0.02175 | 0.0424618 | 0.491408 |
| eq_n_Pentane | 0.0016866 | 210 | 0.0784108 | 0.0800974 | nan | nan | nan |
