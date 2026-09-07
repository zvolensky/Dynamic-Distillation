# Vapor RHS Material Terms Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_vapor_material_reconciled_trial1_smoke_20260707\column_profile_20260707_154658.csv`
Time: `0.2` s

## Summary
| n_stages | max_relative_rhs_per_s | max_relative_rhs_per_s_interior | max_abs_final_rhs_lbmolps |
|---|---|---|---|
| 20 | 0.104033 | 0.104033 | 0.324984 |

## Interpretation
- `final_rhs` is the live RHS contribution to explicit tray vapor component inventory.
- `pre_equilibrium_rhs` is transport/feed/terminal/holdup behavior before equilibrium transfer.
- Dominant terms identify whether the motion is transport, feed, terminal handling, holdup relaxation, or equilibrium transfer.

## Top Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 3 | n_Butane | 0.104033 | -0.272926 | 0.20494 | transport_in | 0.529871 | 0.529871 | -0.327016 | -0.477866 | 0 |
| 4 | n_Butane | 0.0826404 | -0.298311 | 0.179111 | transport_in | 0.706671 | 0.706671 | -0.529871 | -0.477423 | 0 |
| 5 | n_Butane | 0.0701235 | -0.315449 | 0.136665 | transport_in | 0.841615 | 0.841615 | -0.706671 | -0.452114 | 0 |
| 19 | n_Propane | 0.0666241 | 0.212491 | -0.127701 | transport_out | -0.388239 | 0.264227 | -0.388239 | 0.340193 | 0 |
| 18 | n_Propane | 0.065832 | 0.251131 | -0.114892 | transport_out | -0.498839 | 0.388239 | -0.498839 | 0.366023 | 0 |
| 6 | n_Butane | 0.062453 | -0.3238 | 0.0939048 | transport_in | 0.934752 | 0.934752 | -0.841615 | -0.417705 | 0 |
| 17 | n_Propane | 0.0593887 | 0.268107 | -0.128317 | transport_out | -0.622234 | 0.498839 | -0.622234 | 0.396424 | 0 |
| 7 | n_Butane | 0.057416 | -0.324984 | 0.0587067 | transport_in | 0.993749 | 0.993749 | -0.934752 | -0.383691 | 0 |
| 8 | n_Butane | 0.0536116 | -0.319698 | 0.0323023 | transport_in | 1.02738 | 1.02738 | -0.993749 | -0.352 | 0 |
| 16 | n_Propane | 0.0524487 | 0.274879 | -0.13344 | transport_out | -0.750223 | 0.622234 | -0.750223 | 0.408319 | 0 |
| 9 | n_Butane | 0.0501529 | -0.307853 | 0.0167609 | transport_in | 1.04643 | 1.04643 | -1.02738 | -0.324614 | 0 |
| 10 | n_Butane | 0.0466005 | -0.2908 | 0.0147008 | transport_in | 1.06432 | 1.06432 | -1.04643 | -0.305501 | 0 |

## Top Interior Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 3 | n_Butane | 0.104033 | -0.272926 | 0.20494 | transport_in | 0.529871 | 0.529871 | -0.327016 | -0.477866 | 0 |
| 4 | n_Butane | 0.0826404 | -0.298311 | 0.179111 | transport_in | 0.706671 | 0.706671 | -0.529871 | -0.477423 | 0 |
| 5 | n_Butane | 0.0701235 | -0.315449 | 0.136665 | transport_in | 0.841615 | 0.841615 | -0.706671 | -0.452114 | 0 |
| 19 | n_Propane | 0.0666241 | 0.212491 | -0.127701 | transport_out | -0.388239 | 0.264227 | -0.388239 | 0.340193 | 0 |
| 18 | n_Propane | 0.065832 | 0.251131 | -0.114892 | transport_out | -0.498839 | 0.388239 | -0.498839 | 0.366023 | 0 |
| 6 | n_Butane | 0.062453 | -0.3238 | 0.0939048 | transport_in | 0.934752 | 0.934752 | -0.841615 | -0.417705 | 0 |
| 17 | n_Propane | 0.0593887 | 0.268107 | -0.128317 | transport_out | -0.622234 | 0.498839 | -0.622234 | 0.396424 | 0 |
| 7 | n_Butane | 0.057416 | -0.324984 | 0.0587067 | transport_in | 0.993749 | 0.993749 | -0.934752 | -0.383691 | 0 |
| 8 | n_Butane | 0.0536116 | -0.319698 | 0.0323023 | transport_in | 1.02738 | 1.02738 | -0.993749 | -0.352 | 0 |
| 16 | n_Propane | 0.0524487 | 0.274879 | -0.13344 | transport_out | -0.750223 | 0.622234 | -0.750223 | 0.408319 | 0 |
| 9 | n_Butane | 0.0501529 | -0.307853 | 0.0167609 | transport_in | 1.04643 | 1.04643 | -1.02738 | -0.324614 | 0 |
| 10 | n_Butane | 0.0466005 | -0.2908 | 0.0147008 | transport_in | 1.06432 | 1.06432 | -1.04643 | -0.305501 | 0 |

## Top Stage Terms
| stage_1based | max_abs_final_rhs_lbmolps | dominant_stage_term | dominant_stage_term_abs_lbmolps |
|---|---|---|---|
| 7 | 0.324984 | transport_out | 1.3462 |
| 6 | 0.3238 | transport_out | 1.45685 |
| 8 | 0.319698 | transport_out | 1.27414 |
| 5 | 0.315449 | transport_out | 1.61982 |
| 9 | 0.307853 | transport_out | 1.22729 |
| 4 | 0.298311 | transport_out | 1.83715 |
| 10 | 0.2908 | transport_out | 1.19231 |
| 11 | 0.281029 | transport_out | 1.15472 |
| 16 | 0.274879 | transport_in | 1.52511 |
| 3 | 0.272926 | transport_out | 2.06278 |
| 17 | 0.268107 | transport_in | 1.62376 |
| 12 | 0.263708 | transport_out | 1.13832 |
