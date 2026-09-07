# Vapor RHS Material Terms Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_liq_eq_vap_linearsteady_1800s_eqcompguard_m1_20260708\column_profile_20260708_190111.csv`
Time: `1240` s

## Summary
| n_stages | max_relative_rhs_per_s | max_relative_rhs_per_s_interior | max_abs_final_rhs_lbmolps |
|---|---|---|---|
| 20 | 0.0165137 | 0.0165137 | 0.339323 |

## Interpretation
- `final_rhs` is the live RHS contribution to explicit tray vapor component inventory.
- `pre_equilibrium_rhs` is transport/feed/terminal/holdup behavior before equilibrium transfer.
- Dominant terms identify whether the motion is transport, feed, terminal handling, holdup relaxation, or equilibrium transfer.

## Top Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 12 | n_Propane | 0.0165137 | 0.339323 | 0.339323 | transport_in | 1.14836 | 1.14836 | -0.755474 | 0 | 0 |
| 12 | n_Butane | 0.016172 | 0.283858 | 0.283858 | transport_in | 0.968918 | 0.968918 | -0.639707 | 0 | 0 |
| 12 | n_Pentane | 0.0112988 | 0.0331708 | 0.0331708 | transport_in | 0.113287 | 0.113287 | -0.0748124 | 0 | 0 |
| 13 | n_Butane | 0.00937508 | -0.146545 | -0.146545 | transport_out | -0.968918 | 0.672237 | -0.968918 | -0 | 0 |
| 13 | n_Propane | 0.00931345 | -0.170818 | -0.170818 | transport_out | -1.14836 | 0.799599 | -1.14836 | 0 | 0 |
| 13 | n_Pentane | 0.00633091 | -0.0171613 | -0.0171613 | transport_out | -0.113287 | 0.0785717 | -0.113287 | -0 | 0 |
| 5 | n_Propane | 0.00132348 | 0.025818 | 0.025818 | transport_out | -0.711313 | 0.699347 | -0.711313 | 0 | 0 |
| 5 | n_Butane | 0.00117565 | 0.0201147 | 0.0201147 | transport_out | -0.619141 | 0.606367 | -0.619141 | -0 | 0 |
| 6 | n_Propane | 0.00111199 | 0.0217718 | 0.0217718 | transport_out | -0.699347 | 0.692486 | -0.699347 | 0 | 0 |
| 15 | n_Propane | 0.00111099 | 0.0218199 | 0.0218199 | transport_out | -0.765023 | 0.753688 | -0.765023 | -0 | 0 |
| 7 | n_Propane | 0.00110971 | 0.0217612 | 0.0217612 | transport_out | -0.692486 | 0.688475 | -0.692486 | 0 | 0 |
| 8 | n_Propane | 0.00110669 | 0.0217427 | 0.0217427 | transport_out | -0.688475 | 0.686493 | -0.688475 | 0 | 0 |
| 19 | n_Butane | 0.00105012 | 0.018394 | 0.018394 | transport_in | 0.963081 | 0.963081 | -0.916713 | 0 | 0 |
| 17 | n_Propane | 0.00102334 | 0.0213395 | 0.0213395 | transport_in | 1.0566 | 1.0566 | -1.0177 | -0 | 0 |
| 3 | n_Propane | 0.00102307 | 0.021227 | 0.021227 | transport_in | 0.695422 | 0.695422 | -0.682436 | 0 | 0 |
| 4 | n_Propane | 0.00101867 | 0.0207963 | 0.0207963 | transport_in | 0.711313 | 0.711313 | -0.695422 | 0 | 0 |
| 18 | n_Propane | 0.00100661 | 0.0209687 | 0.0209687 | transport_in | 1.10145 | 1.10145 | -1.0566 | -0 | 0 |
| 18 | n_Butane | 0.000992753 | 0.0173795 | 0.0173795 | transport_in | 0.916713 | 0.916713 | -0.879461 | 0 | 0 |
| 15 | n_Butane | 0.000980323 | 0.0162879 | 0.0162879 | transport_out | -0.640864 | 0.629378 | -0.640864 | 0 | 0 |
| 19 | n_Propane | 0.000970489 | 0.0202293 | 0.0202293 | transport_in | 1.15529 | 1.15529 | -1.10145 | -0 | 0 |

## Top Interior Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 12 | n_Propane | 0.0165137 | 0.339323 | 0.339323 | transport_in | 1.14836 | 1.14836 | -0.755474 | 0 | 0 |
| 12 | n_Butane | 0.016172 | 0.283858 | 0.283858 | transport_in | 0.968918 | 0.968918 | -0.639707 | 0 | 0 |
| 12 | n_Pentane | 0.0112988 | 0.0331708 | 0.0331708 | transport_in | 0.113287 | 0.113287 | -0.0748124 | 0 | 0 |
| 13 | n_Butane | 0.00937508 | -0.146545 | -0.146545 | transport_out | -0.968918 | 0.672237 | -0.968918 | -0 | 0 |
| 13 | n_Propane | 0.00931345 | -0.170818 | -0.170818 | transport_out | -1.14836 | 0.799599 | -1.14836 | 0 | 0 |
| 13 | n_Pentane | 0.00633091 | -0.0171613 | -0.0171613 | transport_out | -0.113287 | 0.0785717 | -0.113287 | -0 | 0 |
| 5 | n_Propane | 0.00132348 | 0.025818 | 0.025818 | transport_out | -0.711313 | 0.699347 | -0.711313 | 0 | 0 |
| 5 | n_Butane | 0.00117565 | 0.0201147 | 0.0201147 | transport_out | -0.619141 | 0.606367 | -0.619141 | -0 | 0 |
| 6 | n_Propane | 0.00111199 | 0.0217718 | 0.0217718 | transport_out | -0.699347 | 0.692486 | -0.699347 | 0 | 0 |
| 15 | n_Propane | 0.00111099 | 0.0218199 | 0.0218199 | transport_out | -0.765023 | 0.753688 | -0.765023 | -0 | 0 |
| 7 | n_Propane | 0.00110971 | 0.0217612 | 0.0217612 | transport_out | -0.692486 | 0.688475 | -0.692486 | 0 | 0 |
| 8 | n_Propane | 0.00110669 | 0.0217427 | 0.0217427 | transport_out | -0.688475 | 0.686493 | -0.688475 | 0 | 0 |
| 19 | n_Butane | 0.00105012 | 0.018394 | 0.018394 | transport_in | 0.963081 | 0.963081 | -0.916713 | 0 | 0 |
| 17 | n_Propane | 0.00102334 | 0.0213395 | 0.0213395 | transport_in | 1.0566 | 1.0566 | -1.0177 | -0 | 0 |
| 3 | n_Propane | 0.00102307 | 0.021227 | 0.021227 | transport_in | 0.695422 | 0.695422 | -0.682436 | 0 | 0 |
| 4 | n_Propane | 0.00101867 | 0.0207963 | 0.0207963 | transport_in | 0.711313 | 0.711313 | -0.695422 | 0 | 0 |
| 18 | n_Propane | 0.00100661 | 0.0209687 | 0.0209687 | transport_in | 1.10145 | 1.10145 | -1.0566 | -0 | 0 |
| 18 | n_Butane | 0.000992753 | 0.0173795 | 0.0173795 | transport_in | 0.916713 | 0.916713 | -0.879461 | 0 | 0 |
| 15 | n_Butane | 0.000980323 | 0.0162879 | 0.0162879 | transport_out | -0.640864 | 0.629378 | -0.640864 | 0 | 0 |
| 19 | n_Propane | 0.000970489 | 0.0202293 | 0.0202293 | transport_in | 1.15529 | 1.15529 | -1.10145 | -0 | 0 |

## Top Stage Terms
| stage_1based | max_abs_final_rhs_lbmolps | dominant_stage_term | dominant_stage_term_abs_lbmolps |
|---|---|---|---|
| 12 | 0.339323 | transport_in | 1.14836 |
| 13 | 0.170818 | transport_out | 1.14836 |
| 2 | 0.0266558 | transport_in | 0.682436 |
| 5 | 0.025818 | transport_out | 0.711313 |
| 15 | 0.0218199 | transport_out | 0.765023 |
| 6 | 0.0217718 | transport_out | 0.699347 |
| 7 | 0.0217612 | transport_out | 0.692486 |
| 8 | 0.0217427 | transport_out | 0.688475 |
| 17 | 0.0213395 | transport_in | 1.0566 |
| 3 | 0.021227 | transport_in | 0.695422 |
| 18 | 0.0209687 | transport_in | 1.10145 |
| 4 | 0.0207963 | transport_in | 0.711313 |
| 19 | 0.0202293 | transport_in | 1.15529 |
| 16 | 0.0198396 | transport_in | 1.0177 |
| 10 | 0.0165151 | transport_in | 0.763769 |
| 14 | 0.0129647 | transport_out | 0.799599 |
| 9 | 0.0123325 | transport_in | 0.686793 |
| 11 | 0.00937181 | transport_out | 0.763769 |
| 1 | 0 | transport_in | 0.668342 |
| 20 | 0 | transport_in | 1.7973 |
