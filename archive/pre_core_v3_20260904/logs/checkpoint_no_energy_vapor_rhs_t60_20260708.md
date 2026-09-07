# Vapor RHS Material Terms Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\checkpoint_no_energy_reload_60s_20260708\column_profile_20260708_140811.csv`
Time: `60` s

## Summary
| n_stages | max_relative_rhs_per_s | max_relative_rhs_per_s_interior | max_abs_final_rhs_lbmolps |
|---|---|---|---|
| 20 | 0.00178286 | 0.00178286 | 0.0278355 |

## Interpretation
- `final_rhs` is the live RHS contribution to explicit tray vapor component inventory.
- `pre_equilibrium_rhs` is transport/feed/terminal/holdup behavior before equilibrium transfer.
- Dominant terms identify whether the motion is transport, feed, terminal handling, holdup relaxation, or equilibrium transfer.

## Top Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 3 | n_Propane | 0.00178286 | 0.0253025 | 0.0253025 | transport_in | 0.735382 | 0.735382 | -0.717164 |  | 0 |
| 4 | n_Propane | 0.00176806 | 0.024797 | 0.024797 | transport_in | 0.749205 | 0.749205 | -0.735382 |  | 0 |
| 5 | n_Propane | 0.00175723 | 0.0244943 | 0.0244943 | transport_in | 0.761831 | 0.761831 | -0.749205 |  | 0 |
| 6 | n_Propane | 0.00174822 | 0.0242716 | 0.0242716 | transport_in | 0.770196 | 0.770196 | -0.761831 |  | 0 |
| 7 | n_Propane | 0.00173345 | 0.0240377 | 0.0240377 | transport_in | 0.776067 | 0.776067 | -0.770196 |  | 0 |
| 8 | n_Propane | 0.00171876 | 0.0238222 | 0.0238222 | transport_in | 0.779256 | 0.779256 | -0.776067 |  | 0 |
| 10 | n_Propane | 0.00168854 | 0.0234486 | 0.0234486 | transport_in | 0.790751 | 0.790751 | -0.786583 |  | 0 |
| 9 | n_Propane | 0.00168302 | 0.0234117 | 0.0234117 | transport_in | 0.786583 | 0.786583 | -0.779256 |  | 0 |
| 11 | n_Propane | 0.00167888 | 0.0232799 | 0.0232799 | transport_in | 0.792649 | 0.792649 | -0.790751 |  | 0 |
| 13 | n_Propane | 0.00163922 | 0.0230973 | 0.0230973 | transport_in | 0.84913 | 0.84913 | -0.831922 |  | 0 |
| 12 | n_Propane | 0.00163532 | 0.0233694 | 0.0233694 | transport_in | 0.831922 | 0.831922 | -0.792649 |  | 0 |
| 14 | n_Propane | 0.00162807 | 0.0229548 | 0.0229548 | transport_in | 0.869461 | 0.869461 | -0.84913 |  | 0 |

## Top Interior Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 3 | n_Propane | 0.00178286 | 0.0253025 | 0.0253025 | transport_in | 0.735382 | 0.735382 | -0.717164 |  | 0 |
| 4 | n_Propane | 0.00176806 | 0.024797 | 0.024797 | transport_in | 0.749205 | 0.749205 | -0.735382 |  | 0 |
| 5 | n_Propane | 0.00175723 | 0.0244943 | 0.0244943 | transport_in | 0.761831 | 0.761831 | -0.749205 |  | 0 |
| 6 | n_Propane | 0.00174822 | 0.0242716 | 0.0242716 | transport_in | 0.770196 | 0.770196 | -0.761831 |  | 0 |
| 7 | n_Propane | 0.00173345 | 0.0240377 | 0.0240377 | transport_in | 0.776067 | 0.776067 | -0.770196 |  | 0 |
| 8 | n_Propane | 0.00171876 | 0.0238222 | 0.0238222 | transport_in | 0.779256 | 0.779256 | -0.776067 |  | 0 |
| 10 | n_Propane | 0.00168854 | 0.0234486 | 0.0234486 | transport_in | 0.790751 | 0.790751 | -0.786583 |  | 0 |
| 9 | n_Propane | 0.00168302 | 0.0234117 | 0.0234117 | transport_in | 0.786583 | 0.786583 | -0.779256 |  | 0 |
| 11 | n_Propane | 0.00167888 | 0.0232799 | 0.0232799 | transport_in | 0.792649 | 0.792649 | -0.790751 |  | 0 |
| 13 | n_Propane | 0.00163922 | 0.0230973 | 0.0230973 | transport_in | 0.84913 | 0.84913 | -0.831922 |  | 0 |
| 12 | n_Propane | 0.00163532 | 0.0233694 | 0.0233694 | transport_in | 0.831922 | 0.831922 | -0.792649 |  | 0 |
| 14 | n_Propane | 0.00162807 | 0.0229548 | 0.0229548 | transport_in | 0.869461 | 0.869461 | -0.84913 |  | 0 |

## Top Stage Terms
| stage_1based | max_abs_final_rhs_lbmolps | dominant_stage_term | dominant_stage_term_abs_lbmolps |
|---|---|---|---|
| 2 | 0.0278355 | transport_in | 0.717164 |
| 3 | 0.0253025 | transport_in | 0.735382 |
| 4 | 0.024797 | transport_in | 0.749205 |
| 5 | 0.0244943 | transport_in | 0.761831 |
| 6 | 0.0242716 | transport_in | 0.770196 |
| 7 | 0.0240377 | transport_in | 0.776067 |
| 8 | 0.0238222 | transport_in | 0.779256 |
| 10 | 0.0234486 | transport_in | 0.790751 |
| 9 | 0.0234117 | transport_in | 0.786583 |
| 12 | 0.0233694 | transport_in | 0.831922 |
| 11 | 0.0232799 | transport_in | 0.792649 |
| 13 | 0.0230973 | transport_in | 0.84913 |
