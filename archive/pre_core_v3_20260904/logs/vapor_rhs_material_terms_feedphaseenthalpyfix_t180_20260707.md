# Vapor RHS Material Terms Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_liq_eq_vap_linearsteady_180s_feedphaseenthalpyfix_20260707\column_profile_20260707_215312.csv`
Time: `180` s

## Summary
| n_stages | max_relative_rhs_per_s | max_relative_rhs_per_s_interior | max_abs_final_rhs_lbmolps |
|---|---|---|---|
| 20 | 0.258886 | 0.258886 | 0.653877 |

## Interpretation
- `final_rhs` is the live RHS contribution to explicit tray vapor component inventory.
- `pre_equilibrium_rhs` is transport/feed/terminal/holdup behavior before equilibrium transfer.
- Dominant terms identify whether the motion is transport, feed, terminal handling, holdup relaxation, or equilibrium transfer.

## Top Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 18 | n_Propane | 0.258886 | -0.653877 | 0.0133912 | equilibrium_transfer | -0.667269 | 0.313461 | -0.306233 | -0.667269 | 0 |
| 18 | n_Pentane | 0.186928 | 0.363983 | -0.0425495 | equilibrium_transfer | 0.406532 | 0.143735 | -0.19011 | 0.406532 | 0 |
| 18 | n_Butane | 0.034808 | 0.337526 | 0.0767896 | transport_in | 1.78721 | 1.78721 | -1.74555 | 0.260736 | 0 |
| 17 | n_Pentane | 0.0341159 | 0.0512435 | 0.0892512 | transport_in | 0.19011 | 0.19011 | -0.100386 | -0.0380077 | 0 |
| 17 | n_Propane | 0.0250382 | -0.0970579 | -0.271628 | transport_out | -0.575151 | 0.306233 | -0.575151 | 0.17457 | 0 |
| 19 | n_Pentane | 0.00814419 | -0.0140315 | 0.074086 | transport_in | 0.219291 | 0.219291 | -0.143735 | -0.0881175 | 0 |
| 17 | n_Butane | 0.00424112 | 0.0374181 | 0.17398 | transport_in | 1.74555 | 1.74555 | -1.5642 | -0.136562 | 0 |
| 19 | n_Butane | 0.00300722 | -0.0300373 | 0.033097 | transport_in | 1.83859 | 1.83859 | -1.78721 | -0.0631342 | 0 |
| 19 | n_Propane | 0.00282167 | 0.00726999 | -0.143982 | transport_out | -0.313461 | 0.172686 | -0.313461 | 0.151252 | 0 |
| 16 | n_Propane | 0.00165433 | -0.00753837 | -0.139428 | transport_out | -0.71157 | 0.575151 | -0.71157 | 0.13189 | 0 |
| 3 | n_Propane | 0.00112034 | -0.0104841 | -0.217275 | transport_out | -2.0642 | 1.81548 | -2.0642 | 0.206791 | 0 |
| 4 | n_Propane | 0.00111395 | -0.009412 | -0.196018 | transport_out | -1.81548 | 1.60282 | -1.81548 | 0.186606 | 0 |
| 5 | n_Propane | 0.00110162 | -0.00839919 | -0.152458 | transport_out | -1.60282 | 1.44145 | -1.60282 | 0.144059 | 0 |
| 6 | n_Propane | 0.00107774 | -0.00757585 | -0.108088 | transport_out | -1.44145 | 1.33193 | -1.44145 | 0.100512 | 0 |
| 7 | n_Propane | 0.00105814 | -0.00699277 | -0.0734034 | transport_out | -1.33193 | 1.26051 | -1.33193 | 0.0664106 | 0 |
| 14 | n_Propane | 0.00105669 | -0.00530286 | -0.116644 | transport_out | -0.950224 | 0.835833 | -0.950224 | 0.111341 | 0 |
| 13 | n_Propane | 0.00105668 | -0.00573327 | -0.100642 | transport_out | -1.04849 | 0.950224 | -1.04849 | 0.0949084 | 0 |
| 15 | n_Propane | 0.00104978 | -0.00477482 | -0.12716 | transport_out | -0.835833 | 0.71157 | -0.835833 | 0.122385 | 0 |
| 10 | n_Propane | 0.00104621 | -0.00624484 | -0.0300553 | transport_out | -1.18109 | 1.15103 | -1.18109 | 0.0238104 | 0 |
| 8 | n_Propane | 0.00104431 | -0.00660555 | -0.0499334 | transport_out | -1.26051 | 1.21376 | -1.26051 | 0.0433279 | 0 |

## Top Interior Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 18 | n_Propane | 0.258886 | -0.653877 | 0.0133912 | equilibrium_transfer | -0.667269 | 0.313461 | -0.306233 | -0.667269 | 0 |
| 18 | n_Pentane | 0.186928 | 0.363983 | -0.0425495 | equilibrium_transfer | 0.406532 | 0.143735 | -0.19011 | 0.406532 | 0 |
| 18 | n_Butane | 0.034808 | 0.337526 | 0.0767896 | transport_in | 1.78721 | 1.78721 | -1.74555 | 0.260736 | 0 |
| 17 | n_Pentane | 0.0341159 | 0.0512435 | 0.0892512 | transport_in | 0.19011 | 0.19011 | -0.100386 | -0.0380077 | 0 |
| 17 | n_Propane | 0.0250382 | -0.0970579 | -0.271628 | transport_out | -0.575151 | 0.306233 | -0.575151 | 0.17457 | 0 |
| 19 | n_Pentane | 0.00814419 | -0.0140315 | 0.074086 | transport_in | 0.219291 | 0.219291 | -0.143735 | -0.0881175 | 0 |
| 17 | n_Butane | 0.00424112 | 0.0374181 | 0.17398 | transport_in | 1.74555 | 1.74555 | -1.5642 | -0.136562 | 0 |
| 19 | n_Butane | 0.00300722 | -0.0300373 | 0.033097 | transport_in | 1.83859 | 1.83859 | -1.78721 | -0.0631342 | 0 |
| 19 | n_Propane | 0.00282167 | 0.00726999 | -0.143982 | transport_out | -0.313461 | 0.172686 | -0.313461 | 0.151252 | 0 |
| 16 | n_Propane | 0.00165433 | -0.00753837 | -0.139428 | transport_out | -0.71157 | 0.575151 | -0.71157 | 0.13189 | 0 |
| 3 | n_Propane | 0.00112034 | -0.0104841 | -0.217275 | transport_out | -2.0642 | 1.81548 | -2.0642 | 0.206791 | 0 |
| 4 | n_Propane | 0.00111395 | -0.009412 | -0.196018 | transport_out | -1.81548 | 1.60282 | -1.81548 | 0.186606 | 0 |
| 5 | n_Propane | 0.00110162 | -0.00839919 | -0.152458 | transport_out | -1.60282 | 1.44145 | -1.60282 | 0.144059 | 0 |
| 6 | n_Propane | 0.00107774 | -0.00757585 | -0.108088 | transport_out | -1.44145 | 1.33193 | -1.44145 | 0.100512 | 0 |
| 7 | n_Propane | 0.00105814 | -0.00699277 | -0.0734034 | transport_out | -1.33193 | 1.26051 | -1.33193 | 0.0664106 | 0 |
| 14 | n_Propane | 0.00105669 | -0.00530286 | -0.116644 | transport_out | -0.950224 | 0.835833 | -0.950224 | 0.111341 | 0 |
| 13 | n_Propane | 0.00105668 | -0.00573327 | -0.100642 | transport_out | -1.04849 | 0.950224 | -1.04849 | 0.0949084 | 0 |
| 15 | n_Propane | 0.00104978 | -0.00477482 | -0.12716 | transport_out | -0.835833 | 0.71157 | -0.835833 | 0.122385 | 0 |
| 10 | n_Propane | 0.00104621 | -0.00624484 | -0.0300553 | transport_out | -1.18109 | 1.15103 | -1.18109 | 0.0238104 | 0 |
| 8 | n_Propane | 0.00104431 | -0.00660555 | -0.0499334 | transport_out | -1.26051 | 1.21376 | -1.26051 | 0.0433279 | 0 |

## Top Stage Terms
| stage_1based | max_abs_final_rhs_lbmolps | dominant_stage_term | dominant_stage_term_abs_lbmolps |
|---|---|---|---|
| 18 | 0.653877 | transport_in | 1.78721 |
| 17 | 0.0970579 | transport_in | 1.74555 |
| 19 | 0.0300373 | transport_in | 1.83859 |
| 2 | 0.0106737 | transport_in | 2.0642 |
| 3 | 0.0104841 | transport_out | 2.0642 |
| 4 | 0.009412 | transport_out | 1.81548 |
| 5 | 0.00839919 | transport_out | 1.60282 |
| 6 | 0.00757585 | transport_out | 1.44145 |
| 16 | 0.00753837 | transport_in | 1.5642 |
| 7 | 0.00699277 | transport_out | 1.33193 |
| 15 | 0.00676283 | transport_in | 1.4422 |
| 8 | 0.00660555 | transport_out | 1.26051 |
| 9 | 0.00635634 | transport_out | 1.21376 |
| 14 | 0.00625112 | transport_in | 1.32878 |
| 10 | 0.00624484 | transport_out | 1.18109 |
| 11 | 0.00609358 | transport_out | 1.15103 |
| 12 | 0.00607983 | transport_in | 1.13834 |
| 13 | 0.00581456 | transport_in | 1.22604 |
| 1 | 0 | transport_in | 2.04937 |
| 20 | 0 | transport_out | 1.83859 |
