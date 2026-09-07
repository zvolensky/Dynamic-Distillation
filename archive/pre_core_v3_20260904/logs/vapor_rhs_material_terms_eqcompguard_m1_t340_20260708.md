# Vapor RHS Material Terms Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_liq_eq_vap_linearsteady_600s_eqcompguard_m1_20260708\column_profile_20260708_083203.csv`
Time: `340` s

## Summary
| n_stages | max_relative_rhs_per_s | max_relative_rhs_per_s_interior | max_abs_final_rhs_lbmolps |
|---|---|---|---|
| 20 | 0.0305741 | 0.0305741 | 0.210587 |

## Interpretation
- `final_rhs` is the live RHS contribution to explicit tray vapor component inventory.
- `pre_equilibrium_rhs` is transport/feed/terminal/holdup behavior before equilibrium transfer.
- Dominant terms identify whether the motion is transport, feed, terminal handling, holdup relaxation, or equilibrium transfer.

## Top Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 17 | n_Propane | 0.0305741 | 0.143283 | 0.143283 | transport_in | 0.772617 | 0.772617 | -0.639147 | -0 | 0 |
| 17 | n_Butane | 0.0289977 | 0.206269 | 0.206269 | transport_in | 1.24991 | 1.24991 | -1.05992 | 0 | 0 |
| 18 | n_Butane | 0.0226494 | -0.210587 | -0.210587 | transport_in | 1.25822 | 1.25822 | -1.24991 | 0 | 0 |
| 18 | n_Propane | 0.0182463 | -0.111833 | -0.111833 | transport_in | 0.796092 | 0.796092 | -0.772617 | -0 | 0 |
| 17 | n_Pentane | 0.0119673 | 0.0194022 | 0.0194022 | transport_in | 0.125462 | 0.125462 | -0.107714 | 0 | 0 |
| 18 | n_Pentane | 0.0116538 | -0.0213601 | -0.0213601 | transport_in | 0.126074 | 0.126074 | -0.125462 | 0 | 0 |
| 12 | n_Propane | 0.00367129 | 0.0147917 | 0.0147917 | transport_in | 0.615784 | 0.615784 | -0.600236 | 0 | 0 |
| 14 | n_Propane | 0.00339499 | 0.0136525 | 0.0136525 | transport_in | 0.628752 | 0.628752 | -0.622381 | 0 | 0 |
| 16 | n_Propane | 0.00337606 | 0.0156859 | 0.0156859 | transport_in | 0.639147 | 0.639147 | -0.632874 | 0 | 0 |
| 13 | n_Propane | 0.00334702 | 0.0133573 | 0.0133573 | transport_in | 0.622381 | 0.622381 | -0.615784 | 0 | 0 |
| 15 | n_Propane | 0.00324021 | 0.0130892 | 0.0130892 | transport_in | 0.632874 | 0.632874 | -0.628752 | 0 | 0 |
| 9 | n_Propane | 0.00323395 | 0.0124597 | 0.0124597 | transport_in | 0.605457 | 0.605457 | -0.600046 | 0 | 0 |
| 10 | n_Propane | 0.00320122 | 0.0124543 | 0.0124543 | transport_in | 0.610831 | 0.610831 | -0.605457 | 0 | 0 |
| 11 | n_Propane | 0.0029229 | 0.0110547 | 0.0110547 | transport_out | -0.610831 | 0.600236 | -0.610831 | 0 | 0 |
| 19 | n_Propane | 0.00263786 | 0.0129129 | 0.0129129 | transport_in | 0.821915 | 0.821915 | -0.796092 | -0 | 0 |
| 8 | n_Propane | 0.0024248 | 0.00931217 | 0.00931217 | transport_in | 0.600046 | 0.600046 | -0.595337 | 0 | 0 |
| 3 | n_Butane | 0.00240817 | 0.0136808 | 0.144303 | transport_in | 0.971532 | 0.971532 | -0.844979 | -0.130622 | 0 |
| 2 | n_Pentane | 0.00193604 | 0.00325284 | 0.0293388 | transport_in | 0.0603606 | 0.0603606 | -0.0321317 | -0.026086 | 0 |
| 6 | n_Butane | 0.00181721 | 0.0133868 | 0.0332878 | transport_in | 1.20169 | 1.20169 | -1.16439 | -0.0199011 | 0 |
| 6 | n_Pentane | 0.00168955 | 0.00273704 | 0.00671783 | transport_in | 0.120496 | 0.120496 | -0.113387 | -0.00398079 | 0 |

## Top Interior Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 17 | n_Propane | 0.0305741 | 0.143283 | 0.143283 | transport_in | 0.772617 | 0.772617 | -0.639147 | -0 | 0 |
| 17 | n_Butane | 0.0289977 | 0.206269 | 0.206269 | transport_in | 1.24991 | 1.24991 | -1.05992 | 0 | 0 |
| 18 | n_Butane | 0.0226494 | -0.210587 | -0.210587 | transport_in | 1.25822 | 1.25822 | -1.24991 | 0 | 0 |
| 18 | n_Propane | 0.0182463 | -0.111833 | -0.111833 | transport_in | 0.796092 | 0.796092 | -0.772617 | -0 | 0 |
| 17 | n_Pentane | 0.0119673 | 0.0194022 | 0.0194022 | transport_in | 0.125462 | 0.125462 | -0.107714 | 0 | 0 |
| 18 | n_Pentane | 0.0116538 | -0.0213601 | -0.0213601 | transport_in | 0.126074 | 0.126074 | -0.125462 | 0 | 0 |
| 12 | n_Propane | 0.00367129 | 0.0147917 | 0.0147917 | transport_in | 0.615784 | 0.615784 | -0.600236 | 0 | 0 |
| 14 | n_Propane | 0.00339499 | 0.0136525 | 0.0136525 | transport_in | 0.628752 | 0.628752 | -0.622381 | 0 | 0 |
| 16 | n_Propane | 0.00337606 | 0.0156859 | 0.0156859 | transport_in | 0.639147 | 0.639147 | -0.632874 | 0 | 0 |
| 13 | n_Propane | 0.00334702 | 0.0133573 | 0.0133573 | transport_in | 0.622381 | 0.622381 | -0.615784 | 0 | 0 |
| 15 | n_Propane | 0.00324021 | 0.0130892 | 0.0130892 | transport_in | 0.632874 | 0.632874 | -0.628752 | 0 | 0 |
| 9 | n_Propane | 0.00323395 | 0.0124597 | 0.0124597 | transport_in | 0.605457 | 0.605457 | -0.600046 | 0 | 0 |
| 10 | n_Propane | 0.00320122 | 0.0124543 | 0.0124543 | transport_in | 0.610831 | 0.610831 | -0.605457 | 0 | 0 |
| 11 | n_Propane | 0.0029229 | 0.0110547 | 0.0110547 | transport_out | -0.610831 | 0.600236 | -0.610831 | 0 | 0 |
| 19 | n_Propane | 0.00263786 | 0.0129129 | 0.0129129 | transport_in | 0.821915 | 0.821915 | -0.796092 | -0 | 0 |
| 8 | n_Propane | 0.0024248 | 0.00931217 | 0.00931217 | transport_in | 0.600046 | 0.600046 | -0.595337 | 0 | 0 |
| 3 | n_Butane | 0.00240817 | 0.0136808 | 0.144303 | transport_in | 0.971532 | 0.971532 | -0.844979 | -0.130622 | 0 |
| 2 | n_Pentane | 0.00193604 | 0.00325284 | 0.0293388 | transport_in | 0.0603606 | 0.0603606 | -0.0321317 | -0.026086 | 0 |
| 6 | n_Butane | 0.00181721 | 0.0133868 | 0.0332878 | transport_in | 1.20169 | 1.20169 | -1.16439 | -0.0199011 | 0 |
| 6 | n_Pentane | 0.00168955 | 0.00273704 | 0.00671783 | transport_in | 0.120496 | 0.120496 | -0.113387 | -0.00398079 | 0 |

## Top Stage Terms
| stage_1based | max_abs_final_rhs_lbmolps | dominant_stage_term | dominant_stage_term_abs_lbmolps |
|---|---|---|---|
| 18 | 0.210587 | transport_in | 1.25822 |
| 17 | 0.206269 | transport_in | 1.24991 |
| 2 | 0.0210525 | transport_out | 1.32794 |
| 16 | 0.0156859 | transport_out | 1.07664 |
| 12 | 0.0147917 | transport_in | 1.11963 |
| 3 | 0.0136808 | transport_out | 1.03584 |
| 14 | 0.0136525 | transport_out | 1.10727 |
| 6 | 0.0133868 | transport_in | 1.20169 |
| 13 | 0.0133573 | transport_out | 1.11963 |
| 15 | 0.0130892 | transport_out | 1.09386 |
| 19 | 0.0129129 | transport_in | 1.28007 |
| 9 | 0.0124597 | transport_out | 1.18454 |
| 10 | 0.0124543 | transport_out | 1.17104 |
| 11 | 0.0110547 | transport_out | 1.15766 |
| 5 | 0.0109196 | transport_in | 1.16439 |
| 7 | 0.010598 | transport_out | 1.20169 |
| 4 | 0.00987176 | transport_in | 1.07753 |
| 8 | 0.00931217 | transport_out | 1.20007 |
| 1 | 0 | transport_in | 1.32794 |
| 20 | 0 | transport_in | 1.7973 |
