# Vapor RHS Material Terms Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_liq_eq_vap_linearsteady_60s_20260707\column_profile_20260707_171839.csv`
Time: `60` s

## Summary
| n_stages | max_relative_rhs_per_s | max_relative_rhs_per_s_interior | max_abs_final_rhs_lbmolps |
|---|---|---|---|
| 20 | 0.637135 | 0.637135 | 3.16803 |

## Interpretation
- `final_rhs` is the live RHS contribution to explicit tray vapor component inventory.
- `pre_equilibrium_rhs` is transport/feed/terminal/holdup behavior before equilibrium transfer.
- Dominant terms identify whether the motion is transport, feed, terminal handling, holdup relaxation, or equilibrium transfer.

## Top Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 4 | n_Butane | 0.637135 | -3.10281 | -0.134172 | equilibrium_transfer | -2.96864 | 1.01124 | -1.17969 | -2.96864 | 0 |
| 4 | n_Propane | 0.407385 | 3.16803 | 0.192495 | equilibrium_transfer | 2.97554 | 2.19818 | -2.0657 | 2.97554 | 0 |
| 3 | n_Butane | 0.0816098 | 0.220076 | 0.665873 | transport_in | 1.17969 | 1.17969 | -0.521175 | -0.445797 | 0 |
| 3 | n_Propane | 0.0229333 | -0.230651 | -0.677213 | transport_out | -2.78221 | 2.0657 | -2.78221 | 0.446562 | 0 |
| 13 | n_Butane | 0.0103296 | 0.0860285 | -0.109522 | transport_out | -1.30438 | 1.21677 | -1.30438 | 0.19555 | 0 |
| 12 | n_Propane | 0.00958837 | -0.0572088 | -0.502692 | transport_out | -1.43692 | 0.610699 | -1.43692 | 0.445483 | 0 |
| 13 | n_Pentane | 0.00701067 | 0.0136377 | -0.0931165 | transport_out | -0.16825 | 0.0779594 | -0.16825 | 0.106754 | 0 |
| 4 | n_Pentane | 0.00690369 | -0.00693703 | -4.26251e-05 | equilibrium_transfer | -0.0068944 | 0.0013865 | -0.00147189 | -0.0068944 | 0 |
| 13 | n_Propane | 0.00628693 | 0.0278579 | 0.330162 | transport_in | 0.951118 | 0.951118 | -0.610699 | -0.302304 | 0 |
| 14 | n_Butane | 0.00376081 | -0.0254892 | 0.075151 | transport_in | 1.29837 | 1.29837 | -1.21677 | -0.10064 | 0 |
| 14 | n_Propane | 0.00371045 | -0.0204675 | -0.127446 | transport_out | -0.951118 | 0.828712 | -0.951118 | 0.106978 | 0 |
| 5 | n_Propane | 0.0033124 | -0.0276316 | -0.222895 | transport_out | -2.19818 | 1.96674 | -2.19818 | 0.195264 | 0 |

## Top Interior Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 4 | n_Butane | 0.637135 | -3.10281 | -0.134172 | equilibrium_transfer | -2.96864 | 1.01124 | -1.17969 | -2.96864 | 0 |
| 4 | n_Propane | 0.407385 | 3.16803 | 0.192495 | equilibrium_transfer | 2.97554 | 2.19818 | -2.0657 | 2.97554 | 0 |
| 3 | n_Butane | 0.0816098 | 0.220076 | 0.665873 | transport_in | 1.17969 | 1.17969 | -0.521175 | -0.445797 | 0 |
| 3 | n_Propane | 0.0229333 | -0.230651 | -0.677213 | transport_out | -2.78221 | 2.0657 | -2.78221 | 0.446562 | 0 |
| 13 | n_Butane | 0.0103296 | 0.0860285 | -0.109522 | transport_out | -1.30438 | 1.21677 | -1.30438 | 0.19555 | 0 |
| 12 | n_Propane | 0.00958837 | -0.0572088 | -0.502692 | transport_out | -1.43692 | 0.610699 | -1.43692 | 0.445483 | 0 |
| 13 | n_Pentane | 0.00701067 | 0.0136377 | -0.0931165 | transport_out | -0.16825 | 0.0779594 | -0.16825 | 0.106754 | 0 |
| 4 | n_Pentane | 0.00690369 | -0.00693703 | -4.26251e-05 | equilibrium_transfer | -0.0068944 | 0.0013865 | -0.00147189 | -0.0068944 | 0 |
| 13 | n_Propane | 0.00628693 | 0.0278579 | 0.330162 | transport_in | 0.951118 | 0.951118 | -0.610699 | -0.302304 | 0 |
| 14 | n_Butane | 0.00376081 | -0.0254892 | 0.075151 | transport_in | 1.29837 | 1.29837 | -1.21677 | -0.10064 | 0 |
| 14 | n_Propane | 0.00371045 | -0.0204675 | -0.127446 | transport_out | -0.951118 | 0.828712 | -0.951118 | 0.106978 | 0 |
| 5 | n_Propane | 0.0033124 | -0.0276316 | -0.222895 | transport_out | -2.19818 | 1.96674 | -2.19818 | 0.195264 | 0 |

## Top Stage Terms
| stage_1based | max_abs_final_rhs_lbmolps | dominant_stage_term | dominant_stage_term_abs_lbmolps |
|---|---|---|---|
| 4 | 3.16803 | equilibrium_transfer | 2.97554 |
| 3 | 0.230651 | transport_out | 2.78221 |
| 13 | 0.0860285 | transport_out | 1.30438 |
| 12 | 0.0572088 | transport_out | 1.5406 |
| 5 | 0.0276316 | transport_out | 2.19818 |
| 14 | 0.0254892 | transport_in | 1.29837 |
| 2 | 0.012035 | transport_out | 2.79988 |
| 15 | 0.0111926 | transport_in | 1.40958 |
| 11 | 0.00945076 | transport_out | 1.58606 |
| 6 | 0.0083828 | transport_out | 1.96674 |
| 19 | 0.00815304 | transport_in | 1.78359 |
| 18 | 0.00793946 | transport_in | 1.73011 |
