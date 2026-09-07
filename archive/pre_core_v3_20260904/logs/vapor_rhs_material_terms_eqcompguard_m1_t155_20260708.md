# Vapor RHS Material Terms Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_liq_eq_vap_linearsteady_300s_eqcompguard_m1_20260708\column_profile_20260708_082230.csv`
Time: `155` s

## Summary
| n_stages | max_relative_rhs_per_s | max_relative_rhs_per_s_interior | max_abs_final_rhs_lbmolps |
|---|---|---|---|
| 20 | 0.0661867 | 0.0661867 | 0.278185 |

## Interpretation
- `final_rhs` is the live RHS contribution to explicit tray vapor component inventory.
- `pre_equilibrium_rhs` is transport/feed/terminal/holdup behavior before equilibrium transfer.
- Dominant terms identify whether the motion is transport, feed, terminal handling, holdup relaxation, or equilibrium transfer.

## Top Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 4 | n_Butane | 0.0661867 | 0.278185 | 0.278185 | transport_in | 1.01608 | 1.01608 | -0.76736 | 0 | 0 |
| 4 | n_Propane | 0.0337406 | -0.256099 | -0.256099 | transport_out | -1.57884 | 1.26212 | -1.57884 | -0 | 0 |
| 5 | n_Butane | 0.0207569 | 0.112582 | 0.112582 | transport_in | 1.10141 | 1.10141 | -1.01608 | 0 | 0 |
| 4 | n_Pentane | 0.0187098 | 0.0203829 | 0.0203829 | transport_in | 0.0409835 | 0.0409835 | -0.0214233 | -0 | 0 |
| 5 | n_Propane | 0.0136538 | -0.0886817 | -0.0886817 | transport_out | -1.26212 | 1.13959 | -1.26212 | -0 | 0 |
| 5 | n_Pentane | 0.00983953 | 0.0115952 | 0.0115952 | transport_in | 0.0514797 | 0.0514797 | -0.0409835 | -0 | 0 |
| 6 | n_Propane | 0.00658179 | -0.0399001 | -0.0608212 | transport_out | -1.13959 | 1.09228 | -1.13959 | 0.0209211 | 0 |
| 15 | n_Propane | 0.00466673 | -0.01719 | -0.113797 | transport_out | -0.621304 | 0.510658 | -0.621304 | 0.0966073 | 0 |
| 7 | n_Propane | 0.00455452 | -0.0262852 | -0.0519399 | transport_out | -1.09228 | 1.04576 | -1.09228 | 0.0256547 | 0 |
| 8 | n_Propane | 0.00371455 | -0.0206927 | -0.054207 | transport_out | -1.04576 | 0.995747 | -1.04576 | 0.0335143 | 0 |
| 3 | n_Pentane | 0.0037112 | 0.00384003 | 0.0133454 | transport_in | 0.0214233 | 0.0214233 | -0.00813503 | -0.00950541 | 0 |
| 14 | n_Propane | 0.00368463 | -0.0155532 | -0.130292 | transport_out | -0.749087 | 0.621304 | -0.749087 | 0.114739 | 0 |
| 13 | n_Propane | 0.00368387 | -0.0170258 | -0.0959801 | transport_out | -0.841653 | 0.749087 | -0.841653 | 0.0789543 | 0 |
| 16 | n_Propane | 0.00343213 | -0.012297 | -0.077568 | transport_out | -0.510658 | 0.436118 | -0.510658 | 0.065271 | 0 |
| 9 | n_Propane | 0.00316804 | -0.0170598 | -0.0417209 | transport_out | -0.995747 | 0.96005 | -0.995747 | 0.0246611 | 0 |
| 12 | n_Propane | 0.00302934 | -0.0153758 | -0.0881777 | transport_out | -0.916664 | 0.841653 | -0.916664 | 0.0728019 | 0 |
| 10 | n_Propane | 0.00290308 | -0.0152222 | -0.0281175 | transport_out | -0.96005 | 0.939286 | -0.96005 | 0.0128953 | 0 |
| 11 | n_Propane | 0.00275464 | -0.0141447 | -0.0291649 | transport_out | -0.939286 | 0.916664 | -0.939286 | 0.0150202 | 0 |
| 17 | n_Butane | 0.00219199 | -0.0205514 | -0.0205514 | transport_out | -1.65606 | 1.64925 | -1.65606 | -0 | 0 |
| 6 | n_Pentane | 0.00215302 | 0.00264538 | 0.00511447 | transport_in | 0.0572047 | 0.0572047 | -0.0514797 | -0.00246909 | 0 |

## Top Interior Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 4 | n_Butane | 0.0661867 | 0.278185 | 0.278185 | transport_in | 1.01608 | 1.01608 | -0.76736 | 0 | 0 |
| 4 | n_Propane | 0.0337406 | -0.256099 | -0.256099 | transport_out | -1.57884 | 1.26212 | -1.57884 | -0 | 0 |
| 5 | n_Butane | 0.0207569 | 0.112582 | 0.112582 | transport_in | 1.10141 | 1.10141 | -1.01608 | 0 | 0 |
| 4 | n_Pentane | 0.0187098 | 0.0203829 | 0.0203829 | transport_in | 0.0409835 | 0.0409835 | -0.0214233 | -0 | 0 |
| 5 | n_Propane | 0.0136538 | -0.0886817 | -0.0886817 | transport_out | -1.26212 | 1.13959 | -1.26212 | -0 | 0 |
| 5 | n_Pentane | 0.00983953 | 0.0115952 | 0.0115952 | transport_in | 0.0514797 | 0.0514797 | -0.0409835 | -0 | 0 |
| 6 | n_Propane | 0.00658179 | -0.0399001 | -0.0608212 | transport_out | -1.13959 | 1.09228 | -1.13959 | 0.0209211 | 0 |
| 15 | n_Propane | 0.00466673 | -0.01719 | -0.113797 | transport_out | -0.621304 | 0.510658 | -0.621304 | 0.0966073 | 0 |
| 7 | n_Propane | 0.00455452 | -0.0262852 | -0.0519399 | transport_out | -1.09228 | 1.04576 | -1.09228 | 0.0256547 | 0 |
| 8 | n_Propane | 0.00371455 | -0.0206927 | -0.054207 | transport_out | -1.04576 | 0.995747 | -1.04576 | 0.0335143 | 0 |
| 3 | n_Pentane | 0.0037112 | 0.00384003 | 0.0133454 | transport_in | 0.0214233 | 0.0214233 | -0.00813503 | -0.00950541 | 0 |
| 14 | n_Propane | 0.00368463 | -0.0155532 | -0.130292 | transport_out | -0.749087 | 0.621304 | -0.749087 | 0.114739 | 0 |
| 13 | n_Propane | 0.00368387 | -0.0170258 | -0.0959801 | transport_out | -0.841653 | 0.749087 | -0.841653 | 0.0789543 | 0 |
| 16 | n_Propane | 0.00343213 | -0.012297 | -0.077568 | transport_out | -0.510658 | 0.436118 | -0.510658 | 0.065271 | 0 |
| 9 | n_Propane | 0.00316804 | -0.0170598 | -0.0417209 | transport_out | -0.995747 | 0.96005 | -0.995747 | 0.0246611 | 0 |
| 12 | n_Propane | 0.00302934 | -0.0153758 | -0.0881777 | transport_out | -0.916664 | 0.841653 | -0.916664 | 0.0728019 | 0 |
| 10 | n_Propane | 0.00290308 | -0.0152222 | -0.0281175 | transport_out | -0.96005 | 0.939286 | -0.96005 | 0.0128953 | 0 |
| 11 | n_Propane | 0.00275464 | -0.0141447 | -0.0291649 | transport_out | -0.939286 | 0.916664 | -0.939286 | 0.0150202 | 0 |
| 17 | n_Butane | 0.00219199 | -0.0205514 | -0.0205514 | transport_out | -1.65606 | 1.64925 | -1.65606 | -0 | 0 |
| 6 | n_Pentane | 0.00215302 | 0.00264538 | 0.00511447 | transport_in | 0.0572047 | 0.0572047 | -0.0514797 | -0.00246909 | 0 |

## Top Stage Terms
| stage_1based | max_abs_final_rhs_lbmolps | dominant_stage_term | dominant_stage_term_abs_lbmolps |
|---|---|---|---|
| 4 | 0.278185 | transport_out | 1.57884 |
| 5 | 0.112582 | transport_out | 1.26212 |
| 6 | 0.0399001 | transport_out | 1.13959 |
| 2 | 0.0290069 | transport_out | 1.98247 |
| 7 | 0.0262852 | transport_in | 1.16033 |
| 8 | 0.0206927 | transport_in | 1.19243 |
| 17 | 0.0205514 | transport_out | 1.65606 |
| 19 | 0.0178828 | transport_out | 1.6337 |
| 15 | 0.01719 | transport_in | 1.5979 |
| 9 | 0.0170598 | transport_in | 1.21914 |
| 13 | 0.0170258 | transport_in | 1.41323 |
| 18 | 0.0165334 | transport_out | 1.64925 |
| 3 | 0.0156014 | transport_out | 1.88509 |
| 14 | 0.0155532 | transport_in | 1.51341 |
| 12 | 0.0153758 | transport_in | 1.33978 |
| 10 | 0.0152222 | transport_in | 1.23828 |
| 11 | 0.0141447 | transport_in | 1.25766 |
| 16 | 0.012297 | transport_in | 1.65606 |
| 1 | 0 | transport_in | 1.98247 |
| 20 | 0 | transport_in | 1.7973 |
