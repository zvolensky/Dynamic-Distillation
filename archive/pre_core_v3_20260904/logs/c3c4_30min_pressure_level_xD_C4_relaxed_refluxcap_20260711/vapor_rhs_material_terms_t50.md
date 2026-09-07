# Vapor RHS Material Terms Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_30min_pressure_level_xD_C4_relaxed_refluxcap_20260711\column_profile_20260711_083447.csv`
Time: `50` s

## Summary
| n_stages | max_relative_rhs_per_s | max_relative_rhs_per_s_interior | max_abs_final_rhs_lbmolps |
|---|---|---|---|
| 20 | 0.000978603 | 0.000978603 | 0.0108449 |

## Interpretation
- `final_rhs` is the live RHS contribution to explicit tray vapor component inventory.
- `pre_equilibrium_rhs` is transport/feed/terminal/holdup behavior before equilibrium transfer.
- Dominant terms identify whether the motion is transport, feed, terminal handling, holdup relaxation, or equilibrium transfer.

## Top Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 19 | n_Propane | 0.000978603 | 0.010175 | 0.010175 | transport_in | 1.0037 | 1.0037 | -0.962971 | -0 | 0 |
| 18 | n_Propane | 0.000942067 | 0.00986405 | 0.00986405 | transport_in | 0.962971 | 0.962971 | -0.921605 | -0 | 0 |
| 17 | n_Propane | 0.000930962 | 0.00977592 | 0.00977592 | transport_in | 0.921605 | 0.921605 | -0.883 | -0 | 0 |
| 8 | n_Propane | 0.000926602 | 0.00877707 | 0.00877707 | transport_in | 0.83228 | 0.83228 | -0.830935 | 0 | 0 |
| 9 | n_Propane | 0.000924568 | 0.00876089 | 0.00876089 | transport_in | 0.832818 | 0.832818 | -0.83228 | 0 | 0 |
| 10 | n_Propane | 0.000923503 | 0.00874754 | 0.00874754 | transport_out | -0.832818 | 0.831671 | -0.832818 | 0 | 0 |
| 7 | n_Propane | 0.000922475 | 0.0087329 | 0.0087329 | transport_in | 0.830935 | 0.830935 | -0.829662 | 0 | 0 |
| 11 | n_Propane | 0.000918304 | 0.00868421 | 0.00868421 | transport_out | -0.831671 | 0.827842 | -0.831671 | 0 | 0 |
| 15 | n_Propane | 0.000903071 | 0.00869426 | 0.00869426 | transport_in | 0.871018 | 0.871018 | -0.858479 | -0 | 0 |
| 13 | n_Propane | 0.00089942 | 0.00859038 | 0.00859038 | transport_in | 0.851301 | 0.851301 | -0.846866 | 0 | 0 |
| 3 | n_Propane | 0.000893724 | 0.00888593 | 0.00888593 | transport_in | 0.799173 | 0.799173 | -0.790067 | 0 | 0 |
| 14 | n_Propane | 0.000890465 | 0.00853025 | 0.00853025 | transport_in | 0.858479 | 0.858479 | -0.851301 | 0 | 0 |
| 12 | n_Propane | 0.000881676 | 0.00854464 | 0.00854464 | transport_in | 0.846866 | 0.846866 | -0.827842 | 0 | 0 |
| 16 | n_Propane | 0.000872267 | 0.00899607 | 0.00899607 | transport_in | 0.883 | 0.883 | -0.871018 | -0 | 0 |
| 4 | n_Propane | 0.000843022 | 0.00825237 | 0.00825237 | transport_in | 0.812086 | 0.812086 | -0.799173 | 0 | 0 |
| 5 | n_Propane | 0.000837103 | 0.00810865 | 0.00810865 | transport_in | 0.828995 | 0.828995 | -0.812086 | 0 | 0 |
| 6 | n_Propane | 0.000814572 | 0.00772 | 0.00772 | transport_in | 0.829662 | 0.829662 | -0.828995 | 0 | 0 |
| 2 | n_Pentane | 0.000753703 | 0.00175959 | 0.0629672 | transport_in | 0.112082 | 0.112082 | -0.0529806 | -0.0612076 | 0 |
| 2 | n_Butane | 0.00070284 | 0.0108449 | 0.378041 | transport_in | 0.909088 | 0.909088 | -0.572847 | -0.367196 | 0 |
| 15 | n_Butane | 0.00069778 | 0.00734881 | 0.00734881 | transport_in | 0.960055 | 0.960055 | -0.948458 | 0 | 0 |

## Top Interior Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 19 | n_Propane | 0.000978603 | 0.010175 | 0.010175 | transport_in | 1.0037 | 1.0037 | -0.962971 | -0 | 0 |
| 18 | n_Propane | 0.000942067 | 0.00986405 | 0.00986405 | transport_in | 0.962971 | 0.962971 | -0.921605 | -0 | 0 |
| 17 | n_Propane | 0.000930962 | 0.00977592 | 0.00977592 | transport_in | 0.921605 | 0.921605 | -0.883 | -0 | 0 |
| 8 | n_Propane | 0.000926602 | 0.00877707 | 0.00877707 | transport_in | 0.83228 | 0.83228 | -0.830935 | 0 | 0 |
| 9 | n_Propane | 0.000924568 | 0.00876089 | 0.00876089 | transport_in | 0.832818 | 0.832818 | -0.83228 | 0 | 0 |
| 10 | n_Propane | 0.000923503 | 0.00874754 | 0.00874754 | transport_out | -0.832818 | 0.831671 | -0.832818 | 0 | 0 |
| 7 | n_Propane | 0.000922475 | 0.0087329 | 0.0087329 | transport_in | 0.830935 | 0.830935 | -0.829662 | 0 | 0 |
| 11 | n_Propane | 0.000918304 | 0.00868421 | 0.00868421 | transport_out | -0.831671 | 0.827842 | -0.831671 | 0 | 0 |
| 15 | n_Propane | 0.000903071 | 0.00869426 | 0.00869426 | transport_in | 0.871018 | 0.871018 | -0.858479 | -0 | 0 |
| 13 | n_Propane | 0.00089942 | 0.00859038 | 0.00859038 | transport_in | 0.851301 | 0.851301 | -0.846866 | 0 | 0 |
| 3 | n_Propane | 0.000893724 | 0.00888593 | 0.00888593 | transport_in | 0.799173 | 0.799173 | -0.790067 | 0 | 0 |
| 14 | n_Propane | 0.000890465 | 0.00853025 | 0.00853025 | transport_in | 0.858479 | 0.858479 | -0.851301 | 0 | 0 |
| 12 | n_Propane | 0.000881676 | 0.00854464 | 0.00854464 | transport_in | 0.846866 | 0.846866 | -0.827842 | 0 | 0 |
| 16 | n_Propane | 0.000872267 | 0.00899607 | 0.00899607 | transport_in | 0.883 | 0.883 | -0.871018 | -0 | 0 |
| 4 | n_Propane | 0.000843022 | 0.00825237 | 0.00825237 | transport_in | 0.812086 | 0.812086 | -0.799173 | 0 | 0 |
| 5 | n_Propane | 0.000837103 | 0.00810865 | 0.00810865 | transport_in | 0.828995 | 0.828995 | -0.812086 | 0 | 0 |
| 6 | n_Propane | 0.000814572 | 0.00772 | 0.00772 | transport_in | 0.829662 | 0.829662 | -0.828995 | 0 | 0 |
| 2 | n_Pentane | 0.000753703 | 0.00175959 | 0.0629672 | transport_in | 0.112082 | 0.112082 | -0.0529806 | -0.0612076 | 0 |
| 2 | n_Butane | 0.00070284 | 0.0108449 | 0.378041 | transport_in | 0.909088 | 0.909088 | -0.572847 | -0.367196 | 0 |
| 15 | n_Butane | 0.00069778 | 0.00734881 | 0.00734881 | transport_in | 0.960055 | 0.960055 | -0.948458 | 0 | 0 |

## Top Stage Terms
| stage_1based | max_abs_final_rhs_lbmolps | dominant_stage_term | dominant_stage_term_abs_lbmolps |
|---|---|---|---|
| 2 | 0.0108449 | transport_out | 1.31438 |
| 19 | 0.010175 | transport_in | 1.09044 |
| 18 | 0.00986405 | transport_in | 1.05034 |
| 17 | 0.00977592 | transport_in | 1.00918 |
| 16 | 0.00899607 | transport_in | 0.97037 |
| 3 | 0.00888593 | transport_in | 0.915631 |
| 8 | 0.00877707 | transport_out | 0.937473 |
| 9 | 0.00876089 | transport_out | 0.935604 |
| 10 | 0.00874754 | transport_out | 0.932932 |
| 7 | 0.0087329 | transport_out | 0.939489 |
| 15 | 0.00869426 | transport_in | 0.960055 |
| 11 | 0.00868421 | transport_out | 0.92854 |
| 13 | 0.00859038 | transport_in | 0.94263 |
| 12 | 0.00854464 | transport_in | 0.939972 |
| 14 | 0.00853025 | transport_in | 0.948458 |
| 4 | 0.00825237 | transport_in | 0.926635 |
| 5 | 0.00810865 | transport_in | 0.942254 |
| 6 | 0.00772 | transport_out | 0.942254 |
| 1 | 0 | transport_in | 1.31438 |
| 20 | 0 | transport_in | 1.78956 |
