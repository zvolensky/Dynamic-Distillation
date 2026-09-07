# Vapor RHS Material Terms Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_dd057_final_composition_settle_hold300s_20260712\column_profile_20260712_105152.csv`
Time: `300` s

## Summary
| n_stages | max_relative_rhs_per_s | max_relative_rhs_per_s_interior | max_abs_final_rhs_lbmolps |
|---|---|---|---|
| 20 | 0.000187381 | 0.000187381 | 0.00288815 |

## Interpretation
- `final_rhs` is the live RHS contribution to explicit tray vapor component inventory.
- `pre_equilibrium_rhs` is transport/feed/terminal/holdup behavior before equilibrium transfer.
- Dominant terms identify whether the motion is transport, feed, terminal handling, holdup relaxation, or equilibrium transfer.

## Top Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 3 | n_Propane | 0.000187381 | -0.00265104 | -0.193164 | transport_out | -1.90193 | 1.66194 | -1.90193 | 0.190513 | 0 |
| 4 | n_Propane | 0.000185974 | -0.00237433 | -0.175979 | transport_out | -1.66194 | 1.45775 | -1.66194 | 0.173605 | 0 |
| 5 | n_Propane | 0.000184058 | -0.00212415 | -0.136412 | transport_out | -1.45775 | 1.30927 | -1.45775 | 0.134288 | 0 |
| 6 | n_Propane | 0.000181707 | -0.00192333 | -0.0951446 | transport_out | -1.30927 | 1.21138 | -1.30927 | 0.0932212 | 0 |
| 7 | n_Propane | 0.000180193 | -0.00178322 | -0.0629648 | transport_out | -1.21138 | 1.14832 | -1.21138 | 0.0611815 | 0 |
| 11 | n_Propane | 0.000179753 | -0.00155623 | -0.0283594 | transport_out | -1.04653 | 1.0108 | -1.04653 | 0.0268032 | 0 |
| 8 | n_Propane | 0.00017921 | -0.00169056 | -0.0416291 | transport_out | -1.14832 | 1.1067 | -1.14832 | 0.0399385 | 0 |
| 15 | n_Butane | 0.000179117 | -0.00177818 | 0.086168 | transport_in | 1.32149 | 1.32149 | -1.2228 | -0.0879462 | 0 |
| 10 | n_Propane | 0.000178919 | -0.00158984 | -0.0259849 | transport_out | -1.07609 | 1.04653 | -1.07609 | 0.024395 | 0 |
| 9 | n_Propane | 0.000178752 | -0.00163041 | -0.0294603 | transport_out | -1.1067 | 1.07609 | -1.1067 | 0.0278299 | 0 |
| 11 | n_Butane | 0.000177972 | -0.00145211 | -0.00411242 | transport_out | -0.978414 | 0.967412 | -0.978414 | 0.00266032 | 0 |
| 14 | n_Butane | 0.000177649 | -0.00164799 | 0.0843284 | transport_in | 1.2228 | 1.2228 | -1.12991 | -0.0859764 | 0 |

## Top Interior Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 3 | n_Propane | 0.000187381 | -0.00265104 | -0.193164 | transport_out | -1.90193 | 1.66194 | -1.90193 | 0.190513 | 0 |
| 4 | n_Propane | 0.000185974 | -0.00237433 | -0.175979 | transport_out | -1.66194 | 1.45775 | -1.66194 | 0.173605 | 0 |
| 5 | n_Propane | 0.000184058 | -0.00212415 | -0.136412 | transport_out | -1.45775 | 1.30927 | -1.45775 | 0.134288 | 0 |
| 6 | n_Propane | 0.000181707 | -0.00192333 | -0.0951446 | transport_out | -1.30927 | 1.21138 | -1.30927 | 0.0932212 | 0 |
| 7 | n_Propane | 0.000180193 | -0.00178322 | -0.0629648 | transport_out | -1.21138 | 1.14832 | -1.21138 | 0.0611815 | 0 |
| 11 | n_Propane | 0.000179753 | -0.00155623 | -0.0283594 | transport_out | -1.04653 | 1.0108 | -1.04653 | 0.0268032 | 0 |
| 8 | n_Propane | 0.00017921 | -0.00169056 | -0.0416291 | transport_out | -1.14832 | 1.1067 | -1.14832 | 0.0399385 | 0 |
| 15 | n_Butane | 0.000179117 | -0.00177818 | 0.086168 | transport_in | 1.32149 | 1.32149 | -1.2228 | -0.0879462 | 0 |
| 10 | n_Propane | 0.000178919 | -0.00158984 | -0.0259849 | transport_out | -1.07609 | 1.04653 | -1.07609 | 0.024395 | 0 |
| 9 | n_Propane | 0.000178752 | -0.00163041 | -0.0294603 | transport_out | -1.1067 | 1.07609 | -1.1067 | 0.0278299 | 0 |
| 11 | n_Butane | 0.000177972 | -0.00145211 | -0.00411242 | transport_out | -0.978414 | 0.967412 | -0.978414 | 0.00266032 | 0 |
| 14 | n_Butane | 0.000177649 | -0.00164799 | 0.0843284 | transport_in | 1.2228 | 1.2228 | -1.12991 | -0.0859764 | 0 |

## Top Stage Terms
| stage_1based | max_abs_final_rhs_lbmolps | dominant_stage_term | dominant_stage_term_abs_lbmolps |
|---|---|---|---|
| 2 | 0.00288815 | transport_out | 2.14046 |
| 3 | 0.00265104 | transport_out | 1.90193 |
| 4 | 0.00237433 | transport_out | 1.66194 |
| 19 | 0.00220273 | transport_out | 1.51499 |
| 18 | 0.00215851 | transport_in | 1.51499 |
| 5 | 0.00212415 | transport_out | 1.45775 |
| 17 | 0.00205381 | transport_in | 1.48656 |
| 6 | 0.00192333 | transport_out | 1.30927 |
| 16 | 0.001919 | transport_in | 1.41523 |
| 7 | 0.00178322 | transport_out | 1.21138 |
| 15 | 0.00177818 | transport_in | 1.32149 |
| 8 | 0.00169056 | transport_out | 1.14832 |
