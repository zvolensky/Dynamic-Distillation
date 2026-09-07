# Vapor RHS Material Terms Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_liq_eq_vap_linearsteady_60s_topanchorfix_20260707\column_profile_20260707_172502.csv`
Time: `60` s

## Summary
| n_stages | max_relative_rhs_per_s | max_relative_rhs_per_s_interior | max_abs_final_rhs_lbmolps |
|---|---|---|---|
| 20 | 0.000993435 | 0.000993435 | 0.00786835 |

## Interpretation
- `final_rhs` is the live RHS contribution to explicit tray vapor component inventory.
- `pre_equilibrium_rhs` is transport/feed/terminal/holdup behavior before equilibrium transfer.
- Dominant terms identify whether the motion is transport, feed, terminal handling, holdup relaxation, or equilibrium transfer.

## Top Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 12 | n_Propane | 0.000993435 | -0.00639701 | -0.0827569 | transport_out | -1.1132 | 1.04265 | -1.1132 | 0.0763599 | 0 |
| 12 | n_Butane | 0.000972127 | -0.00595067 | 0.0669532 | transport_in | 1.12657 | 1.12657 | -1.04812 | -0.0729039 | 0 |
| 19 | n_Propane | 0.000963042 | -0.00278947 | -0.130375 | transport_out | -0.345259 | 0.21588 | -0.345259 | 0.127585 | 0 |
| 18 | n_Propane | 0.000819434 | -0.00292736 | -0.124252 | transport_out | -0.468416 | 0.345259 | -0.468416 | 0.121324 | 0 |
| 14 | n_Propane | 0.000798953 | -0.0044162 | -0.112483 | transport_out | -0.947791 | 0.837721 | -0.947791 | 0.108067 | 0 |
| 3 | n_Propane | 0.000760819 | -0.00786835 | -0.213599 | transport_out | -2.04975 | 1.80285 | -2.04975 | 0.20573 | 0 |
| 14 | n_Butane | 0.000745062 | -0.00505912 | 0.0963987 | transport_in | 1.31161 | 1.31161 | -1.21213 | -0.101458 | 0 |
| 11 | n_Butane | 0.000737044 | -0.00446063 | -0.0128174 | transport_out | -1.06276 | 1.04812 | -1.06276 | 0.0083568 | 0 |
| 10 | n_Butane | 0.000731927 | -0.00442443 | 0.00126627 | transport_in | 1.06276 | 1.06276 | -1.06263 | -0.0056907 | 0 |
| 19 | n_Pentane | 0.000731805 | -0.00136422 | 0.0734148 | transport_in | 0.231192 | 0.231192 | -0.157323 | -0.074779 | 0 |
| 17 | n_Propane | 0.000730669 | -0.00312067 | -0.1279 | transport_out | -0.594613 | 0.468416 | -0.594613 | 0.124779 | 0 |
| 13 | n_Propane | 0.000727459 | -0.00434326 | -0.0969088 | transport_out | -1.04265 | 0.947791 | -1.04265 | 0.0925656 | 0 |

## Top Interior Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 12 | n_Propane | 0.000993435 | -0.00639701 | -0.0827569 | transport_out | -1.1132 | 1.04265 | -1.1132 | 0.0763599 | 0 |
| 12 | n_Butane | 0.000972127 | -0.00595067 | 0.0669532 | transport_in | 1.12657 | 1.12657 | -1.04812 | -0.0729039 | 0 |
| 19 | n_Propane | 0.000963042 | -0.00278947 | -0.130375 | transport_out | -0.345259 | 0.21588 | -0.345259 | 0.127585 | 0 |
| 18 | n_Propane | 0.000819434 | -0.00292736 | -0.124252 | transport_out | -0.468416 | 0.345259 | -0.468416 | 0.121324 | 0 |
| 14 | n_Propane | 0.000798953 | -0.0044162 | -0.112483 | transport_out | -0.947791 | 0.837721 | -0.947791 | 0.108067 | 0 |
| 3 | n_Propane | 0.000760819 | -0.00786835 | -0.213599 | transport_out | -2.04975 | 1.80285 | -2.04975 | 0.20573 | 0 |
| 14 | n_Butane | 0.000745062 | -0.00505912 | 0.0963987 | transport_in | 1.31161 | 1.31161 | -1.21213 | -0.101458 | 0 |
| 11 | n_Butane | 0.000737044 | -0.00446063 | -0.0128174 | transport_out | -1.06276 | 1.04812 | -1.06276 | 0.0083568 | 0 |
| 10 | n_Butane | 0.000731927 | -0.00442443 | 0.00126627 | transport_in | 1.06276 | 1.06276 | -1.06263 | -0.0056907 | 0 |
| 19 | n_Pentane | 0.000731805 | -0.00136422 | 0.0734148 | transport_in | 0.231192 | 0.231192 | -0.157323 | -0.074779 | 0 |
| 17 | n_Propane | 0.000730669 | -0.00312067 | -0.1279 | transport_out | -0.594613 | 0.468416 | -0.594613 | 0.124779 | 0 |
| 13 | n_Propane | 0.000727459 | -0.00434326 | -0.0969088 | transport_out | -1.04265 | 0.947791 | -1.04265 | 0.0925656 | 0 |

## Top Stage Terms
| stage_1based | max_abs_final_rhs_lbmolps | dominant_stage_term | dominant_stage_term_abs_lbmolps |
|---|---|---|---|
| 3 | 0.00786835 | transport_out | 2.04975 |
| 2 | 0.00752382 | transport_in | 2.04975 |
| 4 | 0.0066691 | transport_out | 1.80285 |
| 12 | 0.00639701 | transport_in | 1.12657 |
| 5 | 0.00610003 | transport_out | 1.59011 |
| 6 | 0.00550527 | transport_out | 1.42934 |
| 7 | 0.005089 | transport_out | 1.32014 |
| 14 | 0.00505912 | transport_in | 1.31161 |
| 8 | 0.00481623 | transport_out | 1.24886 |
| 10 | 0.00472612 | transport_out | 1.16972 |
| 9 | 0.00463869 | transport_out | 1.20219 |
| 11 | 0.00462216 | transport_out | 1.14068 |
