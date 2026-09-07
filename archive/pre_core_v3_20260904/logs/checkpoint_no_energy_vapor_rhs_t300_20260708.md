# Vapor RHS Material Terms Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\checkpoint_no_energy_reload_300s_20260708\column_profile_20260708_181150.csv`
Time: `300` s

## Summary
| n_stages | max_relative_rhs_per_s | max_relative_rhs_per_s_interior | max_abs_final_rhs_lbmolps |
|---|---|---|---|
| 20 | 0.00128677 | 0.00128677 | 0.027359 |

## Interpretation
- `final_rhs` is the live RHS contribution to explicit tray vapor component inventory.
- `pre_equilibrium_rhs` is transport/feed/terminal/holdup behavior before equilibrium transfer.
- Dominant terms identify whether the motion is transport, feed, terminal handling, holdup relaxation, or equilibrium transfer.

## Top Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 3 | n_Propane | 0.00128677 | 0.026001 | 0.026001 | transport_in | 0.753156 | 0.753156 | -0.726236 |  | 0 |
| 11 | n_Propane | 0.00127191 | 0.0249049 | 0.0249049 | transport_in | 0.812491 | 0.812491 | -0.809367 |  | 0 |
| 10 | n_Propane | 0.00126285 | 0.0247656 | 0.0247656 | transport_in | 0.809367 | 0.809367 | -0.803999 |  | 0 |
| 5 | n_Propane | 0.00126148 | 0.0249223 | 0.0249223 | transport_in | 0.783441 | 0.783441 | -0.771059 |  | 0 |
| 4 | n_Propane | 0.00125897 | 0.0250874 | 0.0250874 | transport_in | 0.771059 | 0.771059 | -0.753156 |  | 0 |
| 14 | n_Propane | 0.00125711 | 0.0248604 | 0.0248604 | transport_in | 0.887865 | 0.887865 | -0.866821 |  | 0 |
| 13 | n_Propane | 0.00125709 | 0.024849 | 0.024849 | transport_in | 0.866821 | 0.866821 | -0.849211 |  | 0 |
| 9 | n_Propane | 0.00125442 | 0.0246412 | 0.0246412 | transport_in | 0.803999 | 0.803999 | -0.795717 |  | 0 |
| 6 | n_Propane | 0.00125425 | 0.0246422 | 0.0246422 | transport_in | 0.788454 | 0.788454 | -0.783441 |  | 0 |
| 7 | n_Propane | 0.00125224 | 0.0245758 | 0.0245758 | transport_in | 0.792726 | 0.792726 | -0.788454 |  | 0 |
| 12 | n_Propane | 0.00125194 | 0.0249872 | 0.0249872 | transport_in | 0.849211 | 0.849211 | -0.812491 |  | 0 |
| 15 | n_Propane | 0.00124865 | 0.0248481 | 0.0248481 | transport_in | 0.925359 | 0.925359 | -0.887865 |  | 0 |

## Top Interior Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 3 | n_Propane | 0.00128677 | 0.026001 | 0.026001 | transport_in | 0.753156 | 0.753156 | -0.726236 |  | 0 |
| 11 | n_Propane | 0.00127191 | 0.0249049 | 0.0249049 | transport_in | 0.812491 | 0.812491 | -0.809367 |  | 0 |
| 10 | n_Propane | 0.00126285 | 0.0247656 | 0.0247656 | transport_in | 0.809367 | 0.809367 | -0.803999 |  | 0 |
| 5 | n_Propane | 0.00126148 | 0.0249223 | 0.0249223 | transport_in | 0.783441 | 0.783441 | -0.771059 |  | 0 |
| 4 | n_Propane | 0.00125897 | 0.0250874 | 0.0250874 | transport_in | 0.771059 | 0.771059 | -0.753156 |  | 0 |
| 14 | n_Propane | 0.00125711 | 0.0248604 | 0.0248604 | transport_in | 0.887865 | 0.887865 | -0.866821 |  | 0 |
| 13 | n_Propane | 0.00125709 | 0.024849 | 0.024849 | transport_in | 0.866821 | 0.866821 | -0.849211 |  | 0 |
| 9 | n_Propane | 0.00125442 | 0.0246412 | 0.0246412 | transport_in | 0.803999 | 0.803999 | -0.795717 |  | 0 |
| 6 | n_Propane | 0.00125425 | 0.0246422 | 0.0246422 | transport_in | 0.788454 | 0.788454 | -0.783441 |  | 0 |
| 7 | n_Propane | 0.00125224 | 0.0245758 | 0.0245758 | transport_in | 0.792726 | 0.792726 | -0.788454 |  | 0 |
| 12 | n_Propane | 0.00125194 | 0.0249872 | 0.0249872 | transport_in | 0.849211 | 0.849211 | -0.812491 |  | 0 |
| 15 | n_Propane | 0.00124865 | 0.0248481 | 0.0248481 | transport_in | 0.925359 | 0.925359 | -0.887865 |  | 0 |

## Top Stage Terms
| stage_1based | max_abs_final_rhs_lbmolps | dominant_stage_term | dominant_stage_term_abs_lbmolps |
|---|---|---|---|
| 2 | 0.027359 | transport_in | 0.726236 |
| 3 | 0.026001 | transport_in | 0.753156 |
| 4 | 0.0250874 | transport_in | 0.771059 |
| 12 | 0.0249872 | transport_in | 0.849211 |
| 5 | 0.0249223 | transport_in | 0.783441 |
| 11 | 0.0249049 | transport_in | 0.812491 |
| 14 | 0.0248604 | transport_in | 0.887865 |
| 13 | 0.024849 | transport_in | 0.866821 |
| 15 | 0.0248481 | transport_in | 0.925359 |
| 16 | 0.0248466 | transport_in | 0.974381 |
| 10 | 0.0247656 | transport_in | 0.809367 |
| 17 | 0.0247076 | transport_in | 1.02625 |
