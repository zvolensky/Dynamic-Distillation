# Vapor RHS Material Terms Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_liq_eq_vap_linearsteady_300s_topanchorfix_20260707\column_profile_20260707_203741.csv`
Time: `120` s

## Summary
| n_stages | max_relative_rhs_per_s | max_relative_rhs_per_s_interior | max_abs_final_rhs_lbmolps |
|---|---|---|---|
| 20 | 0.00113996 | 0.00113996 | 0.00858377 |

## Interpretation
- `final_rhs` is the live RHS contribution to explicit tray vapor component inventory.
- `pre_equilibrium_rhs` is transport/feed/terminal/holdup behavior before equilibrium transfer.
- Dominant terms identify whether the motion is transport, feed, terminal handling, holdup relaxation, or equilibrium transfer.

## Top Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 18 | n_Propane | 0.00113996 | -0.00388733 | -0.129907 | transport_out | -0.457199 | 0.329917 | -0.457199 | 0.12602 | 0 |
| 17 | n_Propane | 0.000881548 | -0.00361011 | -0.132475 | transport_out | -0.586597 | 0.457199 | -0.586597 | 0.128865 | 0 |
| 18 | n_Butane | 0.000877088 | -0.00858106 | 0.0850625 | transport_in | 1.76091 | 1.76091 | -1.66628 | -0.0936435 | 0 |
| 3 | n_Propane | 0.00084596 | -0.00835117 | -0.215329 | transport_out | -2.06322 | 1.81467 | -2.06322 | 0.206978 | 0 |
| 19 | n_Propane | 0.000830376 | -0.00224947 | -0.135881 | transport_out | -0.329917 | 0.193216 | -0.329917 | 0.133631 | 0 |
| 5 | n_Propane | 0.000822746 | -0.0066097 | -0.15101 | transport_out | -1.6014 | 1.43987 | -1.6014 | 0.1444 | 0 |
| 15 | n_Propane | 0.000818679 | -0.00391835 | -0.124684 | transport_out | -0.838201 | 0.716017 | -0.838201 | 0.120766 | 0 |
| 4 | n_Propane | 0.000816952 | -0.00727183 | -0.194174 | transport_out | -1.81467 | 1.6014 | -1.81467 | 0.186902 | 0 |
| 14 | n_Propane | 0.000811756 | -0.0042861 | -0.114522 | transport_out | -0.95104 | 0.838201 | -0.95104 | 0.110236 | 0 |
| 6 | n_Propane | 0.000808114 | -0.00598007 | -0.106798 | transport_out | -1.43987 | 1.33017 | -1.43987 | 0.100818 | 0 |
| 13 | n_Propane | 0.000807861 | -0.00461144 | -0.0987897 | transport_out | -1.04821 | 0.95104 | -1.04821 | 0.0941783 | 0 |
| 11 | n_Propane | 0.000796952 | -0.00489613 | -0.0267959 | transport_out | -1.14962 | 1.12043 | -1.14962 | 0.0218998 | 0 |

## Top Interior Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 18 | n_Propane | 0.00113996 | -0.00388733 | -0.129907 | transport_out | -0.457199 | 0.329917 | -0.457199 | 0.12602 | 0 |
| 17 | n_Propane | 0.000881548 | -0.00361011 | -0.132475 | transport_out | -0.586597 | 0.457199 | -0.586597 | 0.128865 | 0 |
| 18 | n_Butane | 0.000877088 | -0.00858106 | 0.0850625 | transport_in | 1.76091 | 1.76091 | -1.66628 | -0.0936435 | 0 |
| 3 | n_Propane | 0.00084596 | -0.00835117 | -0.215329 | transport_out | -2.06322 | 1.81467 | -2.06322 | 0.206978 | 0 |
| 19 | n_Propane | 0.000830376 | -0.00224947 | -0.135881 | transport_out | -0.329917 | 0.193216 | -0.329917 | 0.133631 | 0 |
| 5 | n_Propane | 0.000822746 | -0.0066097 | -0.15101 | transport_out | -1.6014 | 1.43987 | -1.6014 | 0.1444 | 0 |
| 15 | n_Propane | 0.000818679 | -0.00391835 | -0.124684 | transport_out | -0.838201 | 0.716017 | -0.838201 | 0.120766 | 0 |
| 4 | n_Propane | 0.000816952 | -0.00727183 | -0.194174 | transport_out | -1.81467 | 1.6014 | -1.81467 | 0.186902 | 0 |
| 14 | n_Propane | 0.000811756 | -0.0042861 | -0.114522 | transport_out | -0.95104 | 0.838201 | -0.95104 | 0.110236 | 0 |
| 6 | n_Propane | 0.000808114 | -0.00598007 | -0.106798 | transport_out | -1.43987 | 1.33017 | -1.43987 | 0.100818 | 0 |
| 13 | n_Propane | 0.000807861 | -0.00461144 | -0.0987897 | transport_out | -1.04821 | 0.95104 | -1.04821 | 0.0941783 | 0 |
| 11 | n_Propane | 0.000796952 | -0.00489613 | -0.0267959 | transport_out | -1.14962 | 1.12043 | -1.14962 | 0.0218998 | 0 |

## Top Stage Terms
| stage_1based | max_abs_final_rhs_lbmolps | dominant_stage_term | dominant_stage_term_abs_lbmolps |
|---|---|---|---|
| 2 | 0.00858377 | transport_in | 2.06322 |
| 18 | 0.00858106 | transport_in | 1.76091 |
| 3 | 0.00835117 | transport_out | 2.06322 |
| 4 | 0.00727183 | transport_out | 1.81467 |
| 5 | 0.0066097 | transport_out | 1.6014 |
| 17 | 0.00652951 | transport_in | 1.66628 |
| 6 | 0.00598007 | transport_out | 1.43987 |
| 16 | 0.00568125 | transport_in | 1.55317 |
| 7 | 0.00553353 | transport_out | 1.33017 |
| 15 | 0.00542147 | transport_in | 1.43544 |
| 8 | 0.00523294 | transport_out | 1.2586 |
| 14 | 0.00509313 | transport_in | 1.32385 |
