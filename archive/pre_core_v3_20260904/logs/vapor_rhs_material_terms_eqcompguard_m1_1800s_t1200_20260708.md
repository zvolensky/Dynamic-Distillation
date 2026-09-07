# Vapor RHS Material Terms Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_liq_eq_vap_linearsteady_1800s_eqcompguard_m1_20260708\column_profile_20260708_190111.csv`
Time: `1200` s

## Summary
| n_stages | max_relative_rhs_per_s | max_relative_rhs_per_s_interior | max_abs_final_rhs_lbmolps |
|---|---|---|---|
| 20 | 0.00133661 | 0.00133661 | 0.0289406 |

## Interpretation
- `final_rhs` is the live RHS contribution to explicit tray vapor component inventory.
- `pre_equilibrium_rhs` is transport/feed/terminal/holdup behavior before equilibrium transfer.
- Dominant terms identify whether the motion is transport, feed, terminal handling, holdup relaxation, or equilibrium transfer.

## Top Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 12 | n_Propane | 0.00133661 | 0.0239379 | 0.0239379 | transport_out | -0.868396 | 0.774284 | -0.868396 | 0 | 0 |
| 5 | n_Propane | 0.0013169 | 0.0244453 | 0.0244453 | transport_out | -0.783003 | 0.763175 | -0.783003 | 0 | 0 |
| 11 | n_Propane | 0.00126975 | 0.0239851 | 0.0239851 | transport_in | 0.868396 | 0.868396 | -0.860499 | 0 | 0 |
| 14 | n_Propane | 0.00126351 | 0.0237392 | 0.0237392 | transport_out | -0.769923 | 0.760178 | -0.769923 | -0 | 0 |
| 15 | n_Propane | 0.00126323 | 0.023668 | 0.023668 | transport_out | -0.760178 | 0.749362 | -0.760178 | -0 | 0 |
| 13 | n_Propane | 0.0012617 | 0.0237541 | 0.0237541 | transport_out | -0.774284 | 0.769923 | -0.774284 | -0 | 0 |
| 10 | n_Propane | 0.00125885 | 0.0238008 | 0.0238008 | transport_in | 0.860499 | 0.860499 | -0.851017 | 0 | 0 |
| 7 | n_Propane | 0.00125189 | 0.0234224 | 0.0234224 | transport_out | -0.756228 | 0.752143 | -0.756228 | 0 | 0 |
| 6 | n_Propane | 0.00125158 | 0.0233811 | 0.0233811 | transport_out | -0.763175 | 0.756228 | -0.763175 | 0 | 0 |
| 8 | n_Propane | 0.0012348 | 0.0231449 | 0.0231449 | transport_out | -0.752143 | 0.749784 | -0.752143 | 0 | 0 |
| 4 | n_Propane | 0.00122932 | 0.0239913 | 0.0239913 | transport_in | 0.783003 | 0.783003 | -0.761834 | 0 | 0 |
| 3 | n_Propane | 0.00122634 | 0.0243278 | 0.0243278 | transport_in | 0.761834 | 0.761834 | -0.742927 | 0 | 0 |
| 17 | n_Propane | 0.00118334 | 0.023608 | 0.023608 | transport_in | 1.05755 | 1.05755 | -1.01907 | -0 | 0 |
| 18 | n_Propane | 0.0011754 | 0.0234392 | 0.0234392 | transport_in | 1.10225 | 1.10225 | -1.05755 | -0 | 0 |
| 19 | n_Propane | 0.00116563 | 0.0232776 | 0.0232776 | transport_in | 1.15637 | 1.15637 | -1.10225 | -0 | 0 |
| 9 | n_Propane | 0.00116295 | 0.0230327 | 0.0230327 | transport_in | 0.851017 | 0.851017 | -0.749784 | 0 | 0 |
| 12 | n_Butane | 0.0011571 | 0.0178478 | 0.0178478 | transport_out | -0.740788 | 0.657933 | -0.740788 | 0 | 0 |
| 5 | n_Butane | 0.00114594 | 0.0187817 | 0.0187817 | transport_out | -0.686121 | 0.666108 | -0.686121 | -0 | 0 |
| 15 | n_Butane | 0.00109287 | 0.0174279 | 0.0174279 | transport_out | -0.64063 | 0.628997 | -0.64063 | 0 | 0 |
| 11 | n_Butane | 0.00109263 | 0.017828 | 0.017828 | transport_in | 0.740788 | 0.740788 | -0.736734 | -0 | 0 |

## Top Interior Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 12 | n_Propane | 0.00133661 | 0.0239379 | 0.0239379 | transport_out | -0.868396 | 0.774284 | -0.868396 | 0 | 0 |
| 5 | n_Propane | 0.0013169 | 0.0244453 | 0.0244453 | transport_out | -0.783003 | 0.763175 | -0.783003 | 0 | 0 |
| 11 | n_Propane | 0.00126975 | 0.0239851 | 0.0239851 | transport_in | 0.868396 | 0.868396 | -0.860499 | 0 | 0 |
| 14 | n_Propane | 0.00126351 | 0.0237392 | 0.0237392 | transport_out | -0.769923 | 0.760178 | -0.769923 | -0 | 0 |
| 15 | n_Propane | 0.00126323 | 0.023668 | 0.023668 | transport_out | -0.760178 | 0.749362 | -0.760178 | -0 | 0 |
| 13 | n_Propane | 0.0012617 | 0.0237541 | 0.0237541 | transport_out | -0.774284 | 0.769923 | -0.774284 | -0 | 0 |
| 10 | n_Propane | 0.00125885 | 0.0238008 | 0.0238008 | transport_in | 0.860499 | 0.860499 | -0.851017 | 0 | 0 |
| 7 | n_Propane | 0.00125189 | 0.0234224 | 0.0234224 | transport_out | -0.756228 | 0.752143 | -0.756228 | 0 | 0 |
| 6 | n_Propane | 0.00125158 | 0.0233811 | 0.0233811 | transport_out | -0.763175 | 0.756228 | -0.763175 | 0 | 0 |
| 8 | n_Propane | 0.0012348 | 0.0231449 | 0.0231449 | transport_out | -0.752143 | 0.749784 | -0.752143 | 0 | 0 |
| 4 | n_Propane | 0.00122932 | 0.0239913 | 0.0239913 | transport_in | 0.783003 | 0.783003 | -0.761834 | 0 | 0 |
| 3 | n_Propane | 0.00122634 | 0.0243278 | 0.0243278 | transport_in | 0.761834 | 0.761834 | -0.742927 | 0 | 0 |
| 17 | n_Propane | 0.00118334 | 0.023608 | 0.023608 | transport_in | 1.05755 | 1.05755 | -1.01907 | -0 | 0 |
| 18 | n_Propane | 0.0011754 | 0.0234392 | 0.0234392 | transport_in | 1.10225 | 1.10225 | -1.05755 | -0 | 0 |
| 19 | n_Propane | 0.00116563 | 0.0232776 | 0.0232776 | transport_in | 1.15637 | 1.15637 | -1.10225 | -0 | 0 |
| 9 | n_Propane | 0.00116295 | 0.0230327 | 0.0230327 | transport_in | 0.851017 | 0.851017 | -0.749784 | 0 | 0 |
| 12 | n_Butane | 0.0011571 | 0.0178478 | 0.0178478 | transport_out | -0.740788 | 0.657933 | -0.740788 | 0 | 0 |
| 5 | n_Butane | 0.00114594 | 0.0187817 | 0.0187817 | transport_out | -0.686121 | 0.666108 | -0.686121 | -0 | 0 |
| 15 | n_Butane | 0.00109287 | 0.0174279 | 0.0174279 | transport_out | -0.64063 | 0.628997 | -0.64063 | 0 | 0 |
| 11 | n_Butane | 0.00109263 | 0.017828 | 0.017828 | transport_in | 0.740788 | 0.740788 | -0.736734 | -0 | 0 |

## Top Stage Terms
| stage_1based | max_abs_final_rhs_lbmolps | dominant_stage_term | dominant_stage_term_abs_lbmolps |
|---|---|---|---|
| 2 | 0.0289406 | transport_in | 0.742927 |
| 5 | 0.0244453 | transport_out | 0.783003 |
| 3 | 0.0243278 | transport_in | 0.761834 |
| 4 | 0.0239913 | transport_in | 0.783003 |
| 11 | 0.0239851 | transport_in | 0.868396 |
| 12 | 0.0239379 | transport_out | 0.868396 |
| 16 | 0.0238264 | transport_in | 1.01907 |
| 10 | 0.0238008 | transport_in | 0.860499 |
| 13 | 0.0237541 | transport_out | 0.774284 |
| 14 | 0.0237392 | transport_out | 0.769923 |
| 15 | 0.023668 | transport_out | 0.760178 |
| 17 | 0.023608 | transport_in | 1.05755 |
| 18 | 0.0234392 | transport_in | 1.10225 |
| 7 | 0.0234224 | transport_out | 0.756228 |
| 6 | 0.0233811 | transport_out | 0.763175 |
| 19 | 0.0232776 | transport_in | 1.15637 |
| 8 | 0.0231449 | transport_out | 0.752143 |
| 9 | 0.0230327 | transport_in | 0.851017 |
| 1 | 0 | transport_in | 0.721056 |
| 20 | 0 | transport_in | 1.7973 |
