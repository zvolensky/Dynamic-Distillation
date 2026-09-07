# Vapor RHS Material Terms Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_dd058_extended_composition_settle_hold300s_r2_20260712\column_profile_20260712_110933.csv`
Time: `300` s

## Summary
| n_stages | max_relative_rhs_per_s | max_relative_rhs_per_s_interior | max_abs_final_rhs_lbmolps |
|---|---|---|---|
| 20 | 0.000199297 | 0.000199297 | 0.00287481 |

## Interpretation
- `final_rhs` is the live RHS contribution to explicit tray vapor component inventory.
- `pre_equilibrium_rhs` is transport/feed/terminal/holdup behavior before equilibrium transfer.
- Dominant terms identify whether the motion is transport, feed, terminal handling, holdup relaxation, or equilibrium transfer.

## Top Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 3 | n_Propane | 0.000199297 | -0.002661 | -0.193112 | transport_out | -1.90125 | 1.66136 | -1.90125 | 0.190451 | 0 |
| 4 | n_Propane | 0.000197388 | -0.00237968 | -0.17587 | transport_out | -1.66136 | 1.45766 | -1.66136 | 0.173491 | 0 |
| 5 | n_Propane | 0.0001958 | -0.00213459 | -0.136279 | transport_out | -1.45766 | 1.30928 | -1.45766 | 0.134144 | 0 |
| 6 | n_Propane | 0.000193239 | -0.00193358 | -0.0950497 | transport_out | -1.30928 | 1.21146 | -1.30928 | 0.0931161 | 0 |
| 7 | n_Propane | 0.000191632 | -0.00179357 | -0.0628781 | transport_out | -1.21146 | 1.14848 | -1.21146 | 0.0610845 | 0 |
| 11 | n_Propane | 0.000191279 | -0.00156631 | -0.02848 | transport_out | -1.04657 | 1.01073 | -1.04657 | 0.0269137 | 0 |
| 8 | n_Propane | 0.000190617 | -0.00170114 | -0.0415887 | transport_out | -1.14848 | 1.10689 | -1.14848 | 0.0398875 | 0 |
| 10 | n_Propane | 0.000190365 | -0.00160036 | -0.026104 | transport_out | -1.07625 | 1.04657 | -1.07625 | 0.0245037 | 0 |
| 9 | n_Propane | 0.000190163 | -0.00164109 | -0.0294902 | transport_out | -1.10689 | 1.07625 | -1.10689 | 0.0278491 | 0 |
| 15 | n_Butane | 0.000190111 | -0.00178547 | 0.0858645 | transport_in | 1.3215 | 1.3215 | -1.22314 | -0.0876499 | 0 |
| 11 | n_Butane | 0.000189113 | -0.00146028 | -0.00392457 | transport_out | -0.978596 | 0.967787 | -0.978596 | 0.00246429 | 0 |
| 14 | n_Butane | 0.00018883 | -0.00165786 | 0.0842299 | transport_in | 1.22314 | 1.22314 | -1.13037 | -0.0858878 | 0 |

## Top Interior Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 3 | n_Propane | 0.000199297 | -0.002661 | -0.193112 | transport_out | -1.90125 | 1.66136 | -1.90125 | 0.190451 | 0 |
| 4 | n_Propane | 0.000197388 | -0.00237968 | -0.17587 | transport_out | -1.66136 | 1.45766 | -1.66136 | 0.173491 | 0 |
| 5 | n_Propane | 0.0001958 | -0.00213459 | -0.136279 | transport_out | -1.45766 | 1.30928 | -1.45766 | 0.134144 | 0 |
| 6 | n_Propane | 0.000193239 | -0.00193358 | -0.0950497 | transport_out | -1.30928 | 1.21146 | -1.30928 | 0.0931161 | 0 |
| 7 | n_Propane | 0.000191632 | -0.00179357 | -0.0628781 | transport_out | -1.21146 | 1.14848 | -1.21146 | 0.0610845 | 0 |
| 11 | n_Propane | 0.000191279 | -0.00156631 | -0.02848 | transport_out | -1.04657 | 1.01073 | -1.04657 | 0.0269137 | 0 |
| 8 | n_Propane | 0.000190617 | -0.00170114 | -0.0415887 | transport_out | -1.14848 | 1.10689 | -1.14848 | 0.0398875 | 0 |
| 10 | n_Propane | 0.000190365 | -0.00160036 | -0.026104 | transport_out | -1.07625 | 1.04657 | -1.07625 | 0.0245037 | 0 |
| 9 | n_Propane | 0.000190163 | -0.00164109 | -0.0294902 | transport_out | -1.10689 | 1.07625 | -1.10689 | 0.0278491 | 0 |
| 15 | n_Butane | 0.000190111 | -0.00178547 | 0.0858645 | transport_in | 1.3215 | 1.3215 | -1.22314 | -0.0876499 | 0 |
| 11 | n_Butane | 0.000189113 | -0.00146028 | -0.00392457 | transport_out | -0.978596 | 0.967787 | -0.978596 | 0.00246429 | 0 |
| 14 | n_Butane | 0.00018883 | -0.00165786 | 0.0842299 | transport_in | 1.22314 | 1.22314 | -1.13037 | -0.0858878 | 0 |

## Top Stage Terms
| stage_1based | max_abs_final_rhs_lbmolps | dominant_stage_term | dominant_stage_term_abs_lbmolps |
|---|---|---|---|
| 2 | 0.00287481 | transport_out | 2.14062 |
| 3 | 0.002661 | transport_out | 1.90125 |
| 4 | 0.00237968 | transport_out | 1.66136 |
| 19 | 0.00215389 | transport_out | 1.51358 |
| 5 | 0.00213459 | transport_out | 1.45766 |
| 18 | 0.00212509 | transport_in | 1.51358 |
| 17 | 0.00203898 | transport_in | 1.48563 |
| 6 | 0.00193358 | transport_out | 1.30928 |
| 16 | 0.00191795 | transport_in | 1.41482 |
| 7 | 0.00179357 | transport_out | 1.21146 |
| 15 | 0.00178547 | transport_in | 1.3215 |
| 8 | 0.00170114 | transport_out | 1.14848 |
