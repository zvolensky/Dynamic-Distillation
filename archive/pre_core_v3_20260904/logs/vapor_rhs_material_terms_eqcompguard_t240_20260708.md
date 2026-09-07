# Vapor RHS Material Terms Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_liq_eq_vap_linearsteady_300s_eqcompguard_20260708\column_profile_20260708_081534.csv`
Time: `240` s

## Summary
| n_stages | max_relative_rhs_per_s | max_relative_rhs_per_s_interior | max_abs_final_rhs_lbmolps |
|---|---|---|---|
| 20 | 0.161994 | 0.161994 | 0.869452 |

## Interpretation
- `final_rhs` is the live RHS contribution to explicit tray vapor component inventory.
- `pre_equilibrium_rhs` is transport/feed/terminal/holdup behavior before equilibrium transfer.
- Dominant terms identify whether the motion is transport, feed, terminal handling, holdup relaxation, or equilibrium transfer.

## Top Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 9 | n_Propane | 0.161994 | -0.869452 | -0.347781 | transport_out | -1.1052 | 0.72698 | -1.1052 | -0.521671 | 0 |
| 9 | n_Butane | 0.154036 | 0.833803 | 0.343803 | transport_in | 1.42984 | 1.42984 | -1.1168 | 0.489999 | 0 |
| 9 | n_Pentane | 0.104959 | 0.120125 | 0.0884532 | transport_in | 0.124014 | 0.124014 | -0.036568 | 0.0316722 | 0 |
| 10 | n_Pentane | 0.0279747 | 0.0423638 | 0.059786 | transport_in | 0.182953 | 0.182953 | -0.124014 | -0.0174222 | 0 |
| 10 | n_Propane | 0.0120442 | -0.0483602 | -0.0420483 | transport_out | -0.72698 | 0.679966 | -0.72698 | -0.00631189 | 0 |
| 8 | n_Propane | 0.0103785 | -0.0617094 | -0.148283 | transport_out | -1.24771 | 1.1052 | -1.24771 | 0.0865736 | 0 |
| 11 | n_Pentane | 0.00892974 | 0.0156703 | 0.0170449 | transport_in | 0.198562 | 0.198562 | -0.182953 | -0.00137452 | 0 |
| 8 | n_Butane | 0.00758534 | 0.0377984 | 0.107332 | transport_in | 1.1168 | 1.1168 | -1.00482 | -0.069534 | 0 |
| 8 | n_Pentane | 0.00724329 | 0.00758465 | 0.0246242 | transport_in | 0.036568 | 0.036568 | -0.0118888 | -0.0170396 | 0 |
| 10 | n_Butane | 0.00570773 | 0.0395569 | 0.0158228 | transport_in | 1.4359 | 1.4359 | -1.42984 | 0.0237341 | 0 |
| 16 | n_Butane | 0.00517005 | -0.0467894 | -0.0309318 | transport_out | -1.74639 | 1.73362 | -1.74639 | -0.0158576 | 0 |
| 17 | n_Propane | 0.00504792 | 0.0134637 | 0.00538547 | transport_in | 0.367187 | 0.367187 | -0.359973 | 0.00807821 | 0 |
| 16 | n_Propane | 0.00488018 | -0.0136482 | -0.0338493 | transport_out | -0.389768 | 0.359973 | -0.389768 | 0.0202012 | 0 |
| 18 | n_Propane | 0.00431843 | 0.0116313 | 0.00465254 | transport_in | 0.373249 | 0.373249 | -0.367187 | 0.0069788 | 0 |
| 16 | n_Pentane | 0.00406353 | -0.00723928 | -0.00289571 | transport_out | -0.169545 | 0.168413 | -0.169545 | -0.00434357 | 0 |
| 19 | n_Propane | 0.00348147 | 0.00946036 | 0.00378414 | transport_in | 0.377843 | 0.377843 | -0.373249 | 0.00567622 | 0 |
| 19 | n_Butane | 0.00324781 | -0.0287729 | -0.0246257 | transport_out | -1.70811 | 1.6872 | -1.70811 | -0.0041472 | 0 |
| 15 | n_Propane | 0.00324024 | 0.00873561 | -0.0174712 | transport_out | -0.403663 | 0.389768 | -0.403663 | 0.0262068 | 0 |
| 18 | n_Butane | 0.00307745 | -0.0275485 | -0.0226904 | transport_out | -1.72419 | 1.70811 | -1.72419 | -0.00485805 | 0 |
| 11 | n_Propane | 0.00279461 | -0.0106348 | -0.0104664 | transport_out | -0.679966 | 0.664164 | -0.679966 | -0.000168425 | 0 |

## Top Interior Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 9 | n_Propane | 0.161994 | -0.869452 | -0.347781 | transport_out | -1.1052 | 0.72698 | -1.1052 | -0.521671 | 0 |
| 9 | n_Butane | 0.154036 | 0.833803 | 0.343803 | transport_in | 1.42984 | 1.42984 | -1.1168 | 0.489999 | 0 |
| 9 | n_Pentane | 0.104959 | 0.120125 | 0.0884532 | transport_in | 0.124014 | 0.124014 | -0.036568 | 0.0316722 | 0 |
| 10 | n_Pentane | 0.0279747 | 0.0423638 | 0.059786 | transport_in | 0.182953 | 0.182953 | -0.124014 | -0.0174222 | 0 |
| 10 | n_Propane | 0.0120442 | -0.0483602 | -0.0420483 | transport_out | -0.72698 | 0.679966 | -0.72698 | -0.00631189 | 0 |
| 8 | n_Propane | 0.0103785 | -0.0617094 | -0.148283 | transport_out | -1.24771 | 1.1052 | -1.24771 | 0.0865736 | 0 |
| 11 | n_Pentane | 0.00892974 | 0.0156703 | 0.0170449 | transport_in | 0.198562 | 0.198562 | -0.182953 | -0.00137452 | 0 |
| 8 | n_Butane | 0.00758534 | 0.0377984 | 0.107332 | transport_in | 1.1168 | 1.1168 | -1.00482 | -0.069534 | 0 |
| 8 | n_Pentane | 0.00724329 | 0.00758465 | 0.0246242 | transport_in | 0.036568 | 0.036568 | -0.0118888 | -0.0170396 | 0 |
| 10 | n_Butane | 0.00570773 | 0.0395569 | 0.0158228 | transport_in | 1.4359 | 1.4359 | -1.42984 | 0.0237341 | 0 |
| 16 | n_Butane | 0.00517005 | -0.0467894 | -0.0309318 | transport_out | -1.74639 | 1.73362 | -1.74639 | -0.0158576 | 0 |
| 17 | n_Propane | 0.00504792 | 0.0134637 | 0.00538547 | transport_in | 0.367187 | 0.367187 | -0.359973 | 0.00807821 | 0 |
| 16 | n_Propane | 0.00488018 | -0.0136482 | -0.0338493 | transport_out | -0.389768 | 0.359973 | -0.389768 | 0.0202012 | 0 |
| 18 | n_Propane | 0.00431843 | 0.0116313 | 0.00465254 | transport_in | 0.373249 | 0.373249 | -0.367187 | 0.0069788 | 0 |
| 16 | n_Pentane | 0.00406353 | -0.00723928 | -0.00289571 | transport_out | -0.169545 | 0.168413 | -0.169545 | -0.00434357 | 0 |
| 19 | n_Propane | 0.00348147 | 0.00946036 | 0.00378414 | transport_in | 0.377843 | 0.377843 | -0.373249 | 0.00567622 | 0 |
| 19 | n_Butane | 0.00324781 | -0.0287729 | -0.0246257 | transport_out | -1.70811 | 1.6872 | -1.70811 | -0.0041472 | 0 |
| 15 | n_Propane | 0.00324024 | 0.00873561 | -0.0174712 | transport_out | -0.403663 | 0.389768 | -0.403663 | 0.0262068 | 0 |
| 18 | n_Butane | 0.00307745 | -0.0275485 | -0.0226904 | transport_out | -1.72419 | 1.70811 | -1.72419 | -0.00485805 | 0 |
| 11 | n_Propane | 0.00279461 | -0.0106348 | -0.0104664 | transport_out | -0.679966 | 0.664164 | -0.679966 | -0.000168425 | 0 |

## Top Stage Terms
| stage_1based | max_abs_final_rhs_lbmolps | dominant_stage_term | dominant_stage_term_abs_lbmolps |
|---|---|---|---|
| 9 | 0.869452 | transport_in | 1.42984 |
| 8 | 0.0617094 | transport_out | 1.24771 |
| 10 | 0.0483602 | transport_in | 1.4359 |
| 16 | 0.0467894 | transport_out | 1.74639 |
| 19 | 0.0287729 | transport_out | 1.70811 |
| 18 | 0.0275485 | transport_out | 1.72419 |
| 17 | 0.0243192 | transport_out | 1.73362 |
| 11 | 0.0156703 | transport_out | 1.4359 |
| 2 | 0.0149628 | transport_in | 2.04253 |
| 3 | 0.0147286 | transport_out | 2.04253 |
| 4 | 0.0132437 | transport_out | 1.79708 |
| 5 | 0.0118694 | transport_out | 1.58676 |
| 6 | 0.0107634 | transport_out | 1.42793 |
| 7 | 0.0101961 | transport_out | 1.32065 |
| 15 | 0.0100362 | transport_in | 1.74639 |
| 13 | 0.0078679 | transport_in | 1.57768 |
| 14 | 0.00752602 | transport_in | 1.70873 |
| 12 | 0.00375835 | transport_in | 1.49473 |
| 1 | 0 | transport_in | 2.02694 |
| 20 | 0 | transport_in | 1.7973 |
