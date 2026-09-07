# Vapor RHS Material Terms Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_liq_eq_vap_linearsteady_60s_20260707\column_profile_20260707_171839.csv`
Time: `25` s

## Summary
| n_stages | max_relative_rhs_per_s | max_relative_rhs_per_s_interior | max_abs_final_rhs_lbmolps |
|---|---|---|---|
| 20 | 0.00117584 | 0.00117584 | 0.012038 |

## Interpretation
- `final_rhs` is the live RHS contribution to explicit tray vapor component inventory.
- `pre_equilibrium_rhs` is transport/feed/terminal/holdup behavior before equilibrium transfer.
- Dominant terms identify whether the motion is transport, feed, terminal handling, holdup relaxation, or equilibrium transfer.

## Top Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 19 | n_Propane | 0.00117584 | -0.00353178 | -0.131996 | transport_out | -0.356574 | 0.22532 | -0.356574 | 0.128464 | 0 |
| 3 | n_Propane | 0.00112909 | -0.012038 | -0.218349 | transport_out | -2.05343 | 1.80701 | -2.05343 | 0.206311 | 0 |
| 19 | n_Pentane | 0.000938535 | -0.00179994 | 0.075341 | transport_in | 0.239021 | 0.239021 | -0.16334 | -0.0771409 | 0 |
| 11 | n_Butane | 0.000895798 | -0.00557179 | -0.0157289 | transport_out | -1.06893 | 1.05237 | -1.06893 | 0.0101571 | 0 |
| 5 | n_Propane | 0.000860903 | -0.00743128 | -0.151569 | transport_out | -1.59289 | 1.43168 | -1.59289 | 0.144138 | 0 |
| 4 | n_Propane | 0.000820144 | -0.00783489 | -0.194145 | transport_out | -1.80701 | 1.59289 | -1.80701 | 0.186311 | 0 |
| 18 | n_Propane | 0.000801068 | -0.00294505 | -0.120661 | transport_out | -0.47645 | 0.356574 | -0.47645 | 0.117716 | 0 |
| 6 | n_Propane | 0.000782855 | -0.00621276 | -0.106869 | transport_out | -1.43168 | 1.32221 | -1.43168 | 0.100656 | 0 |
| 5 | n_Butane | 0.000745394 | -0.00333363 | 0.13984 | transport_in | 0.860169 | 0.860169 | -0.724714 | -0.143174 | 0 |
| 10 | n_Butane | 0.000741129 | -0.00460609 | 0.00271621 | transport_in | 1.06893 | 1.06893 | -1.06529 | -0.00732229 | 0 |
| 7 | n_Propane | 0.000737699 | -0.00549238 | -0.0719399 | transport_out | -1.32221 | 1.25089 | -1.32221 | 0.0664476 | 0 |
| 14 | n_Propane | 0.000736023 | -0.00416754 | -0.111713 | transport_out | -0.955868 | 0.845938 | -0.955868 | 0.107545 | 0 |

## Top Interior Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 19 | n_Propane | 0.00117584 | -0.00353178 | -0.131996 | transport_out | -0.356574 | 0.22532 | -0.356574 | 0.128464 | 0 |
| 3 | n_Propane | 0.00112909 | -0.012038 | -0.218349 | transport_out | -2.05343 | 1.80701 | -2.05343 | 0.206311 | 0 |
| 19 | n_Pentane | 0.000938535 | -0.00179994 | 0.075341 | transport_in | 0.239021 | 0.239021 | -0.16334 | -0.0771409 | 0 |
| 11 | n_Butane | 0.000895798 | -0.00557179 | -0.0157289 | transport_out | -1.06893 | 1.05237 | -1.06893 | 0.0101571 | 0 |
| 5 | n_Propane | 0.000860903 | -0.00743128 | -0.151569 | transport_out | -1.59289 | 1.43168 | -1.59289 | 0.144138 | 0 |
| 4 | n_Propane | 0.000820144 | -0.00783489 | -0.194145 | transport_out | -1.80701 | 1.59289 | -1.80701 | 0.186311 | 0 |
| 18 | n_Propane | 0.000801068 | -0.00294505 | -0.120661 | transport_out | -0.47645 | 0.356574 | -0.47645 | 0.117716 | 0 |
| 6 | n_Propane | 0.000782855 | -0.00621276 | -0.106869 | transport_out | -1.43168 | 1.32221 | -1.43168 | 0.100656 | 0 |
| 5 | n_Butane | 0.000745394 | -0.00333363 | 0.13984 | transport_in | 0.860169 | 0.860169 | -0.724714 | -0.143174 | 0 |
| 10 | n_Butane | 0.000741129 | -0.00460609 | 0.00271621 | transport_in | 1.06893 | 1.06893 | -1.06529 | -0.00732229 | 0 |
| 7 | n_Propane | 0.000737699 | -0.00549238 | -0.0719399 | transport_out | -1.32221 | 1.25089 | -1.32221 | 0.0664476 | 0 |
| 14 | n_Propane | 0.000736023 | -0.00416754 | -0.111713 | transport_out | -0.955868 | 0.845938 | -0.955868 | 0.107545 | 0 |

## Top Stage Terms
| stage_1based | max_abs_final_rhs_lbmolps | dominant_stage_term | dominant_stage_term_abs_lbmolps |
|---|---|---|---|
| 3 | 0.012038 | transport_out | 2.05343 |
| 4 | 0.00783489 | transport_out | 1.80701 |
| 5 | 0.00743128 | transport_out | 1.59289 |
| 6 | 0.00621276 | transport_out | 1.43168 |
| 11 | 0.00557179 | transport_out | 1.14304 |
| 7 | 0.00549238 | transport_out | 1.32221 |
| 8 | 0.00511685 | transport_out | 1.25089 |
| 9 | 0.00494748 | transport_out | 1.20416 |
| 10 | 0.00476892 | transport_out | 1.17101 |
| 17 | 0.00449844 | transport_in | 1.63271 |
| 13 | 0.004398 | transport_in | 1.21622 |
| 16 | 0.00437007 | transport_in | 1.53166 |
