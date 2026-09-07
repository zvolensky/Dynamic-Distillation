# Vapor RHS Material Terms Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_30min_pressure_level_xD_C4_relaxed_refluxcap_20260711\column_profile_20260711_083447.csv`
Time: `300` s

## Summary
| n_stages | max_relative_rhs_per_s | max_relative_rhs_per_s_interior | max_abs_final_rhs_lbmolps |
|---|---|---|---|
| 20 | 0.00103643 | 0.00103643 | 0.0153988 |

## Interpretation
- `final_rhs` is the live RHS contribution to explicit tray vapor component inventory.
- `pre_equilibrium_rhs` is transport/feed/terminal/holdup behavior before equilibrium transfer.
- Dominant terms identify whether the motion is transport, feed, terminal handling, holdup relaxation, or equilibrium transfer.

## Top Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 7 | n_Propane | 0.00103643 | 0.0124962 | 0.0124962 | transport_in | 0.845124 | 0.845124 | -0.841754 | 0 | 0 |
| 16 | n_Propane | 0.00102732 | 0.0135941 | 0.0135941 | transport_in | 0.921835 | 0.921835 | -0.893804 | -0 | 0 |
| 15 | n_Propane | 0.00102477 | 0.0126765 | 0.0126765 | transport_in | 0.893804 | 0.893804 | -0.88075 | -0 | 0 |
| 13 | n_Propane | 0.00102012 | 0.0125208 | 0.0125208 | transport_in | 0.870278 | 0.870278 | -0.862171 | 0 | 0 |
| 14 | n_Propane | 0.00102003 | 0.0125715 | 0.0125715 | transport_in | 0.88075 | 0.88075 | -0.870278 | -0 | 0 |
| 10 | n_Propane | 0.00101806 | 0.0123189 | 0.0123189 | transport_out | -0.847586 | 0.847166 | -0.847586 | 0 | 0 |
| 11 | n_Propane | 0.00101268 | 0.0122584 | 0.0122584 | transport_out | -0.847166 | 0.844234 | -0.847166 | 0 | 0 |
| 19 | n_Propane | 0.00100666 | 0.0133679 | 0.0133679 | transport_in | 1.05378 | 1.05378 | -1.00985 | -0 | 0 |
| 12 | n_Propane | 0.00100015 | 0.0123444 | 0.0123444 | transport_in | 0.862171 | 0.862171 | -0.844234 | 0 | 0 |
| 18 | n_Propane | 0.000993445 | 0.0132393 | 0.0132393 | transport_in | 1.00985 | 1.00985 | -0.965398 | -0 | 0 |
| 9 | n_Propane | 0.000981519 | 0.011864 | 0.011864 | transport_in | 0.847586 | 0.847586 | -0.846744 | 0 | 0 |
| 17 | n_Propane | 0.000978457 | 0.013062 | 0.013062 | transport_in | 0.965398 | 0.965398 | -0.921835 | -0 | 0 |
| 4 | n_Propane | 0.000951604 | 0.0117742 | 0.0117742 | transport_in | 0.841973 | 0.841973 | -0.81706 | 0 | 0 |
| 8 | n_Propane | 0.000949433 | 0.0114613 | 0.0114613 | transport_in | 0.846744 | 0.846744 | -0.845124 | 0 | 0 |
| 3 | n_Propane | 0.000933685 | 0.0116433 | 0.0116433 | transport_in | 0.81706 | 0.81706 | -0.800298 | 0 | 0 |
| 5 | n_Propane | 0.000908351 | 0.0109185 | 0.0109185 | transport_out | -0.841973 | 0.840675 | -0.841973 | 0 | 0 |
| 6 | n_Propane | 0.000886387 | 0.0106728 | 0.0106728 | transport_in | 0.841754 | 0.841754 | -0.840675 | 0 | 0 |
| 2 | n_Butane | 0.000818306 | 0.0153988 | 0.264663 | transport_in | 0.852551 | 0.852551 | -0.619184 | -0.249264 | 0 |
| 2 | n_Pentane | 0.000813992 | 0.00233078 | 0.0451945 | transport_in | 0.106676 | 0.106676 | -0.0647543 | -0.0428637 | 0 |
| 7 | n_Butane | 0.000759597 | 0.00956019 | 0.00956019 | transport_out | -0.882025 | 0.882022 | -0.882025 | -0 | 0 |

## Top Interior Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 7 | n_Propane | 0.00103643 | 0.0124962 | 0.0124962 | transport_in | 0.845124 | 0.845124 | -0.841754 | 0 | 0 |
| 16 | n_Propane | 0.00102732 | 0.0135941 | 0.0135941 | transport_in | 0.921835 | 0.921835 | -0.893804 | -0 | 0 |
| 15 | n_Propane | 0.00102477 | 0.0126765 | 0.0126765 | transport_in | 0.893804 | 0.893804 | -0.88075 | -0 | 0 |
| 13 | n_Propane | 0.00102012 | 0.0125208 | 0.0125208 | transport_in | 0.870278 | 0.870278 | -0.862171 | 0 | 0 |
| 14 | n_Propane | 0.00102003 | 0.0125715 | 0.0125715 | transport_in | 0.88075 | 0.88075 | -0.870278 | -0 | 0 |
| 10 | n_Propane | 0.00101806 | 0.0123189 | 0.0123189 | transport_out | -0.847586 | 0.847166 | -0.847586 | 0 | 0 |
| 11 | n_Propane | 0.00101268 | 0.0122584 | 0.0122584 | transport_out | -0.847166 | 0.844234 | -0.847166 | 0 | 0 |
| 19 | n_Propane | 0.00100666 | 0.0133679 | 0.0133679 | transport_in | 1.05378 | 1.05378 | -1.00985 | -0 | 0 |
| 12 | n_Propane | 0.00100015 | 0.0123444 | 0.0123444 | transport_in | 0.862171 | 0.862171 | -0.844234 | 0 | 0 |
| 18 | n_Propane | 0.000993445 | 0.0132393 | 0.0132393 | transport_in | 1.00985 | 1.00985 | -0.965398 | -0 | 0 |
| 9 | n_Propane | 0.000981519 | 0.011864 | 0.011864 | transport_in | 0.847586 | 0.847586 | -0.846744 | 0 | 0 |
| 17 | n_Propane | 0.000978457 | 0.013062 | 0.013062 | transport_in | 0.965398 | 0.965398 | -0.921835 | -0 | 0 |
| 4 | n_Propane | 0.000951604 | 0.0117742 | 0.0117742 | transport_in | 0.841973 | 0.841973 | -0.81706 | 0 | 0 |
| 8 | n_Propane | 0.000949433 | 0.0114613 | 0.0114613 | transport_in | 0.846744 | 0.846744 | -0.845124 | 0 | 0 |
| 3 | n_Propane | 0.000933685 | 0.0116433 | 0.0116433 | transport_in | 0.81706 | 0.81706 | -0.800298 | 0 | 0 |
| 5 | n_Propane | 0.000908351 | 0.0109185 | 0.0109185 | transport_out | -0.841973 | 0.840675 | -0.841973 | 0 | 0 |
| 6 | n_Propane | 0.000886387 | 0.0106728 | 0.0106728 | transport_in | 0.841754 | 0.841754 | -0.840675 | 0 | 0 |
| 2 | n_Butane | 0.000818306 | 0.0153988 | 0.264663 | transport_in | 0.852551 | 0.852551 | -0.619184 | -0.249264 | 0 |
| 2 | n_Pentane | 0.000813992 | 0.00233078 | 0.0451945 | transport_in | 0.106676 | 0.106676 | -0.0647543 | -0.0428637 | 0 |
| 7 | n_Butane | 0.000759597 | 0.00956019 | 0.00956019 | transport_out | -0.882025 | 0.882022 | -0.882025 | -0 | 0 |

## Top Stage Terms
| stage_1based | max_abs_final_rhs_lbmolps | dominant_stage_term | dominant_stage_term_abs_lbmolps |
|---|---|---|---|
| 2 | 0.0153988 | transport_out | 1.15058 |
| 16 | 0.0135941 | transport_in | 0.926661 |
| 19 | 0.0133679 | transport_in | 1.05378 |
| 18 | 0.0132393 | transport_in | 1.00985 |
| 17 | 0.013062 | transport_in | 0.96609 |
| 15 | 0.0126765 | transport_in | 0.902585 |
| 14 | 0.0125715 | transport_in | 0.893202 |
| 13 | 0.0125208 | transport_in | 0.886308 |
| 7 | 0.0124962 | transport_out | 0.882025 |
| 12 | 0.0123444 | transport_in | 0.881715 |
| 10 | 0.0123189 | transport_out | 0.877534 |
| 11 | 0.0122584 | transport_out | 0.873558 |
| 9 | 0.011864 | transport_out | 0.880187 |
| 4 | 0.0117742 | transport_in | 0.88937 |
| 3 | 0.0116433 | transport_in | 0.866651 |
| 8 | 0.0114613 | transport_out | 0.882022 |
| 5 | 0.0109185 | transport_out | 0.88937 |
| 6 | 0.0106728 | transport_out | 0.884433 |
| 1 | 0 | transport_in | 1.15058 |
| 20 | 0 | transport_in | 1.78956 |
