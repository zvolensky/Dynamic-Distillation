# Vapor RHS Material Terms Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_dd053_unchanged_operating_point_hold_300s_20260712\column_profile_20260712_092336.csv`
Time: `300` s

## Summary
| n_stages | max_relative_rhs_per_s | max_relative_rhs_per_s_interior | max_abs_final_rhs_lbmolps |
|---|---|---|---|
| 20 | 0.000941546 | 0.000941546 | 0.00648974 |

## Interpretation
- `final_rhs` is the live RHS contribution to explicit tray vapor component inventory.
- `pre_equilibrium_rhs` is transport/feed/terminal/holdup behavior before equilibrium transfer.
- Dominant terms identify whether the motion is transport, feed, terminal handling, holdup relaxation, or equilibrium transfer.

## Top Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 19 | n_Propane | 0.000941546 | 0.00315582 | -0.118487 | transport_out | -0.259337 | 0.141733 | -0.259337 | 0.121643 | 0 |
| 19 | n_Pentane | 0.00079468 | 0.00179945 | 0.0674017 | transport_in | 0.207304 | 0.207304 | -0.139428 | -0.0656023 | 0 |
| 18 | n_Pentane | 0.00049906 | 0.00102171 | 0.0243826 | transport_in | 0.139428 | 0.139428 | -0.114063 | -0.0233608 | 0 |
| 18 | n_Butane | 0.000390784 | -0.00648974 | 0.111151 | transport_in | 1.8256 | 1.8256 | -1.69982 | -0.117641 | 0 |
| 19 | n_Butane | 0.000361039 | -0.0063381 | 0.0497025 | transport_in | 1.88153 | 1.88153 | -1.8256 | -0.0560406 | 0 |
| 17 | n_Pentane | 0.00029705 | 0.000582562 | 0.00965452 | transport_in | 0.114063 | 0.114063 | -0.103126 | -0.00907196 | 0 |
| 16 | n_Butane | 0.000282121 | -0.00401836 | 0.127712 | transport_in | 1.55031 | 1.55031 | -1.40392 | -0.13173 | 0 |
| 15 | n_Butane | 0.000270124 | -0.00327355 | 0.115308 | transport_in | 1.40392 | 1.40392 | -1.27411 | -0.118582 | 0 |
| 14 | n_Butane | 0.000253066 | -0.00283453 | 0.0997828 | transport_in | 1.27411 | 1.27411 | -1.16386 | -0.102617 | 0 |
| 10 | n_Butane | 0.000251919 | -0.00246167 | 0.00468766 | transport_in | 1.00243 | 1.00243 | -1.00019 | -0.00714933 | 0 |
| 17 | n_Butane | 0.000251801 | -0.00389011 | 0.130234 | transport_in | 1.69982 | 1.69982 | -1.55031 | -0.134125 | 0 |
| 10 | n_Propane | 0.000248093 | -0.0025948 | -0.027817 | transport_out | -1.07855 | 1.0481 | -1.07855 | 0.0252222 | 0 |
| 18 | n_Propane | 0.000245658 | 0.00113838 | -0.139863 | transport_out | -0.395793 | 0.259337 | -0.395793 | 0.141002 | 0 |
| 4 | n_Propane | 0.000245546 | -0.00374152 | -0.180157 | transport_out | -1.67879 | 1.4745 | -1.67879 | 0.176416 | 0 |
| 13 | n_Butane | 0.000243202 | -0.00254159 | 0.0820512 | transport_in | 1.16386 | 1.16386 | -1.07342 | -0.0845928 | 0 |
| 12 | n_Butane | 0.000238946 | -0.00238575 | 0.0652832 | transport_in | 1.07342 | 1.07342 | -0.987531 | -0.0676689 | 0 |
| 5 | n_Propane | 0.000237041 | -0.00324665 | -0.140095 | transport_out | -1.4745 | 1.32121 | -1.4745 | 0.136848 | 0 |
| 11 | n_Butane | 0.000235126 | -0.00230153 | -0.00864144 | transport_out | -1.00243 | 0.987531 | -1.00243 | 0.00633991 | 0 |
| 7 | n_Propane | 0.000232465 | -0.00272261 | -0.0665545 | transport_out | -1.22091 | 1.15526 | -1.22091 | 0.0638319 | 0 |
| 6 | n_Propane | 0.000232273 | -0.0029154 | -0.0985167 | transport_out | -1.32121 | 1.22091 | -1.32121 | 0.0956013 | 0 |

## Top Interior Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 19 | n_Propane | 0.000941546 | 0.00315582 | -0.118487 | transport_out | -0.259337 | 0.141733 | -0.259337 | 0.121643 | 0 |
| 19 | n_Pentane | 0.00079468 | 0.00179945 | 0.0674017 | transport_in | 0.207304 | 0.207304 | -0.139428 | -0.0656023 | 0 |
| 18 | n_Pentane | 0.00049906 | 0.00102171 | 0.0243826 | transport_in | 0.139428 | 0.139428 | -0.114063 | -0.0233608 | 0 |
| 18 | n_Butane | 0.000390784 | -0.00648974 | 0.111151 | transport_in | 1.8256 | 1.8256 | -1.69982 | -0.117641 | 0 |
| 19 | n_Butane | 0.000361039 | -0.0063381 | 0.0497025 | transport_in | 1.88153 | 1.88153 | -1.8256 | -0.0560406 | 0 |
| 17 | n_Pentane | 0.00029705 | 0.000582562 | 0.00965452 | transport_in | 0.114063 | 0.114063 | -0.103126 | -0.00907196 | 0 |
| 16 | n_Butane | 0.000282121 | -0.00401836 | 0.127712 | transport_in | 1.55031 | 1.55031 | -1.40392 | -0.13173 | 0 |
| 15 | n_Butane | 0.000270124 | -0.00327355 | 0.115308 | transport_in | 1.40392 | 1.40392 | -1.27411 | -0.118582 | 0 |
| 14 | n_Butane | 0.000253066 | -0.00283453 | 0.0997828 | transport_in | 1.27411 | 1.27411 | -1.16386 | -0.102617 | 0 |
| 10 | n_Butane | 0.000251919 | -0.00246167 | 0.00468766 | transport_in | 1.00243 | 1.00243 | -1.00019 | -0.00714933 | 0 |
| 17 | n_Butane | 0.000251801 | -0.00389011 | 0.130234 | transport_in | 1.69982 | 1.69982 | -1.55031 | -0.134125 | 0 |
| 10 | n_Propane | 0.000248093 | -0.0025948 | -0.027817 | transport_out | -1.07855 | 1.0481 | -1.07855 | 0.0252222 | 0 |
| 18 | n_Propane | 0.000245658 | 0.00113838 | -0.139863 | transport_out | -0.395793 | 0.259337 | -0.395793 | 0.141002 | 0 |
| 4 | n_Propane | 0.000245546 | -0.00374152 | -0.180157 | transport_out | -1.67879 | 1.4745 | -1.67879 | 0.176416 | 0 |
| 13 | n_Butane | 0.000243202 | -0.00254159 | 0.0820512 | transport_in | 1.16386 | 1.16386 | -1.07342 | -0.0845928 | 0 |
| 12 | n_Butane | 0.000238946 | -0.00238575 | 0.0652832 | transport_in | 1.07342 | 1.07342 | -0.987531 | -0.0676689 | 0 |
| 5 | n_Propane | 0.000237041 | -0.00324665 | -0.140095 | transport_out | -1.4745 | 1.32121 | -1.4745 | 0.136848 | 0 |
| 11 | n_Butane | 0.000235126 | -0.00230153 | -0.00864144 | transport_out | -1.00243 | 0.987531 | -1.00243 | 0.00633991 | 0 |
| 7 | n_Propane | 0.000232465 | -0.00272261 | -0.0665545 | transport_out | -1.22091 | 1.15526 | -1.22091 | 0.0638319 | 0 |
| 6 | n_Propane | 0.000232273 | -0.0029154 | -0.0985167 | transport_out | -1.32121 | 1.22091 | -1.32121 | 0.0956013 | 0 |

## Top Stage Terms
| stage_1based | max_abs_final_rhs_lbmolps | dominant_stage_term | dominant_stage_term_abs_lbmolps |
|---|---|---|---|
| 18 | 0.00648974 | transport_in | 1.8256 |
| 19 | 0.0063381 | transport_in | 1.88153 |
| 2 | 0.00465026 | transport_out | 2.16321 |
| 16 | 0.00401836 | transport_in | 1.55031 |
| 17 | 0.00389011 | transport_in | 1.69982 |
| 3 | 0.00381531 | transport_out | 1.92303 |
| 4 | 0.00374152 | transport_out | 1.67879 |
| 15 | 0.00327355 | transport_in | 1.40392 |
| 5 | 0.00324665 | transport_out | 1.4745 |
| 6 | 0.0029154 | transport_out | 1.32121 |
| 14 | 0.00283453 | transport_in | 1.27411 |
| 7 | 0.00272261 | transport_out | 1.22091 |
| 10 | 0.0025948 | transport_out | 1.07855 |
| 8 | 0.00258599 | transport_out | 1.15526 |
| 13 | 0.00254159 | transport_in | 1.16386 |
| 12 | 0.00238575 | transport_in | 1.07342 |
| 11 | 0.00232411 | transport_out | 1.0481 |
| 9 | 0.00229882 | transport_out | 1.11116 |
| 1 | 0 | transport_in | 2.16321 |
| 20 | 0 | transport_out | 1.88153 |
