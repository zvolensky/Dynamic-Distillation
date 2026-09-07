# Vapor RHS Material Terms Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_30min_pressure_level_xD_C4_relaxed_refluxcap_20260711\column_profile_20260711_083447.csv`
Time: `600` s

## Summary
| n_stages | max_relative_rhs_per_s | max_relative_rhs_per_s_interior | max_abs_final_rhs_lbmolps |
|---|---|---|---|
| 20 | 0.00100842 | 0.00100842 | 0.0233743 |

## Interpretation
- `final_rhs` is the live RHS contribution to explicit tray vapor component inventory.
- `pre_equilibrium_rhs` is transport/feed/terminal/holdup behavior before equilibrium transfer.
- Dominant terms identify whether the motion is transport, feed, terminal handling, holdup relaxation, or equilibrium transfer.

## Top Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 8 | n_Propane | 0.00100842 | 0.0164899 | 0.0164899 | transport_in | 0.909003 | 0.909003 | -0.897796 | 0 | 0 |
| 2 | n_Pentane | 0.000968358 | 0.00362974 | 0.0228796 | transport_in | 0.104732 | 0.104732 | -0.0839185 | -0.0192499 | 0 |
| 13 | n_Propane | 0.000949574 | 0.0157472 | 0.0157472 | transport_in | 0.904809 | 0.904809 | -0.895677 | 0 | 0 |
| 15 | n_Propane | 0.000948405 | 0.0158615 | 0.0158615 | transport_in | 0.93276 | 0.93276 | -0.91514 | -0 | 0 |
| 2 | n_Butane | 0.000947963 | 0.0233743 | 0.129933 | transport_in | 0.834508 | 0.834508 | -0.722359 | -0.106558 | 0 |
| 5 | n_Propane | 0.000946134 | 0.0152631 | 0.0152631 | transport_in | 0.891297 | 0.891297 | -0.889292 | 0 | 0 |
| 12 | n_Propane | 0.000943103 | 0.0155563 | 0.0155563 | transport_out | -0.926208 | 0.895677 | -0.926208 | 0 | 0 |
| 14 | n_Propane | 0.000936361 | 0.0155876 | 0.0155876 | transport_in | 0.91514 | 0.91514 | -0.904809 | -0 | 0 |
| 10 | n_Propane | 0.000919552 | 0.0150995 | 0.0150995 | transport_in | 0.920253 | 0.920253 | -0.915928 | 0 | 0 |
| 11 | n_Propane | 0.00091673 | 0.0151201 | 0.0151201 | transport_in | 0.926208 | 0.926208 | -0.920253 | 0 | 0 |
| 3 | n_Propane | 0.000910456 | 0.0150268 | 0.0150268 | transport_in | 0.880705 | 0.880705 | -0.860276 | 0 | 0 |
| 4 | n_Propane | 0.000899814 | 0.0146166 | 0.0146166 | transport_in | 0.889292 | 0.889292 | -0.880705 | 0 | 0 |
| 9 | n_Propane | 0.00087648 | 0.0143678 | 0.0143678 | transport_in | 0.915928 | 0.915928 | -0.909003 | 0 | 0 |
| 17 | n_Propane | 0.000875447 | 0.015529 | 0.015529 | transport_in | 1.01779 | 1.01779 | -0.973499 | -0 | 0 |
| 16 | n_Propane | 0.000875246 | 0.0155184 | 0.0155184 | transport_in | 0.973499 | 0.973499 | -0.93276 | -0 | 0 |
| 18 | n_Propane | 0.000874285 | 0.0155152 | 0.0155152 | transport_in | 1.06411 | 1.06411 | -1.01779 | -0 | 0 |
| 19 | n_Propane | 0.000874208 | 0.0154812 | 0.0154812 | transport_in | 1.10928 | 1.10928 | -1.06411 | -0 | 0 |
| 6 | n_Propane | 0.000799605 | 0.0129525 | 0.0129525 | transport_in | 0.89448 | 0.89448 | -0.891297 | 0 | 0 |
| 7 | n_Propane | 0.000791113 | 0.0128567 | 0.0128567 | transport_in | 0.897796 | 0.897796 | -0.89448 | 0 | 0 |
| 8 | n_Butane | 0.000709992 | 0.0109919 | 0.0109919 | transport_in | 0.852902 | 0.852902 | -0.846894 | -0 | 0 |

## Top Interior Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 8 | n_Propane | 0.00100842 | 0.0164899 | 0.0164899 | transport_in | 0.909003 | 0.909003 | -0.897796 | 0 | 0 |
| 2 | n_Pentane | 0.000968358 | 0.00362974 | 0.0228796 | transport_in | 0.104732 | 0.104732 | -0.0839185 | -0.0192499 | 0 |
| 13 | n_Propane | 0.000949574 | 0.0157472 | 0.0157472 | transport_in | 0.904809 | 0.904809 | -0.895677 | 0 | 0 |
| 15 | n_Propane | 0.000948405 | 0.0158615 | 0.0158615 | transport_in | 0.93276 | 0.93276 | -0.91514 | -0 | 0 |
| 2 | n_Butane | 0.000947963 | 0.0233743 | 0.129933 | transport_in | 0.834508 | 0.834508 | -0.722359 | -0.106558 | 0 |
| 5 | n_Propane | 0.000946134 | 0.0152631 | 0.0152631 | transport_in | 0.891297 | 0.891297 | -0.889292 | 0 | 0 |
| 12 | n_Propane | 0.000943103 | 0.0155563 | 0.0155563 | transport_out | -0.926208 | 0.895677 | -0.926208 | 0 | 0 |
| 14 | n_Propane | 0.000936361 | 0.0155876 | 0.0155876 | transport_in | 0.91514 | 0.91514 | -0.904809 | -0 | 0 |
| 10 | n_Propane | 0.000919552 | 0.0150995 | 0.0150995 | transport_in | 0.920253 | 0.920253 | -0.915928 | 0 | 0 |
| 11 | n_Propane | 0.00091673 | 0.0151201 | 0.0151201 | transport_in | 0.926208 | 0.926208 | -0.920253 | 0 | 0 |
| 3 | n_Propane | 0.000910456 | 0.0150268 | 0.0150268 | transport_in | 0.880705 | 0.880705 | -0.860276 | 0 | 0 |
| 4 | n_Propane | 0.000899814 | 0.0146166 | 0.0146166 | transport_in | 0.889292 | 0.889292 | -0.880705 | 0 | 0 |
| 9 | n_Propane | 0.00087648 | 0.0143678 | 0.0143678 | transport_in | 0.915928 | 0.915928 | -0.909003 | 0 | 0 |
| 17 | n_Propane | 0.000875447 | 0.015529 | 0.015529 | transport_in | 1.01779 | 1.01779 | -0.973499 | -0 | 0 |
| 16 | n_Propane | 0.000875246 | 0.0155184 | 0.0155184 | transport_in | 0.973499 | 0.973499 | -0.93276 | -0 | 0 |
| 18 | n_Propane | 0.000874285 | 0.0155152 | 0.0155152 | transport_in | 1.06411 | 1.06411 | -1.01779 | -0 | 0 |
| 19 | n_Propane | 0.000874208 | 0.0154812 | 0.0154812 | transport_in | 1.10928 | 1.10928 | -1.06411 | -0 | 0 |
| 6 | n_Propane | 0.000799605 | 0.0129525 | 0.0129525 | transport_in | 0.89448 | 0.89448 | -0.891297 | 0 | 0 |
| 7 | n_Propane | 0.000791113 | 0.0128567 | 0.0128567 | transport_in | 0.897796 | 0.897796 | -0.89448 | 0 | 0 |
| 8 | n_Butane | 0.000709992 | 0.0109919 | 0.0109919 | transport_in | 0.852902 | 0.852902 | -0.846894 | -0 | 0 |

## Top Stage Terms
| stage_1based | max_abs_final_rhs_lbmolps | dominant_stage_term | dominant_stage_term_abs_lbmolps |
|---|---|---|---|
| 2 | 0.0233743 | transport_out | 1.01097 |
| 8 | 0.0164899 | transport_in | 0.909003 |
| 15 | 0.0158615 | transport_in | 0.93276 |
| 13 | 0.0157472 | transport_in | 0.904809 |
| 14 | 0.0155876 | transport_in | 0.91514 |
| 12 | 0.0155563 | transport_out | 0.926208 |
| 17 | 0.015529 | transport_in | 1.01779 |
| 16 | 0.0155184 | transport_in | 0.973499 |
| 18 | 0.0155152 | transport_in | 1.06411 |
| 19 | 0.0154812 | transport_in | 1.10928 |
| 5 | 0.0152631 | transport_in | 0.891297 |
| 11 | 0.0151201 | transport_in | 0.926208 |
| 10 | 0.0150995 | transport_in | 0.920253 |
| 3 | 0.0150268 | transport_in | 0.880705 |
| 4 | 0.0146166 | transport_in | 0.889292 |
| 9 | 0.0143678 | transport_in | 0.915928 |
| 6 | 0.0129525 | transport_in | 0.89448 |
| 7 | 0.0128567 | transport_in | 0.897796 |
| 1 | 0 | transport_in | 1.01097 |
| 20 | 0 | transport_in | 1.78956 |
