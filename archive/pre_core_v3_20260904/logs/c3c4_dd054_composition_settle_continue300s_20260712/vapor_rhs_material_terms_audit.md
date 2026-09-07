# Vapor RHS Material Terms Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_dd054_composition_settle_continue300s_20260712\column_profile_20260712_101442.csv`
Time: `300` s

## Summary
| n_stages | max_relative_rhs_per_s | max_relative_rhs_per_s_interior | max_abs_final_rhs_lbmolps |
|---|---|---|---|
| 20 | 0.000447708 | 0.000447708 | 0.0055149 |

## Interpretation
- `final_rhs` is the live RHS contribution to explicit tray vapor component inventory.
- `pre_equilibrium_rhs` is transport/feed/terminal/holdup behavior before equilibrium transfer.
- Dominant terms identify whether the motion is transport, feed, terminal handling, holdup relaxation, or equilibrium transfer.

## Top Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 19 | n_Propane | 0.000447708 | 0.00190337 | 0.0441694 | transport_in | 0.413143 | 0.413143 | -0.364083 | -0.042266 | 0 |
| 19 | n_Pentane | 0.000400923 | 0.00110612 | -0.0278571 | transport_out | -0.196962 | 0.17175 | -0.196962 | 0.0289633 | 0 |
| 19 | n_Butane | 0.000351999 | -0.0055149 | -0.0188176 | transport_in | 1.64567 | 1.64567 | -1.64242 | 0.0133027 | 0 |
| 18 | n_Pentane | 0.00033576 | 0.000797213 | 0.0428544 | transport_in | 0.196962 | 0.196962 | -0.152254 | -0.0420572 | 0 |
| 18 | n_Butane | 0.00028905 | -0.00439538 | 0.0494654 | transport_in | 1.64242 | 1.64242 | -1.5738 | -0.0538608 | 0 |
| 17 | n_Butane | 0.000227002 | -0.0032778 | 0.0861731 | transport_in | 1.5738 | 1.5738 | -1.46784 | -0.0894508 | 0 |
| 17 | n_Pentane | 0.000219371 | 0.000469473 | 0.0260568 | transport_in | 0.152254 | 0.152254 | -0.124518 | -0.0255873 | 0 |
| 18 | n_Propane | 0.000202234 | 0.00103001 | -0.094888 | transport_out | -0.453449 | 0.364083 | -0.453449 | 0.095918 | 0 |
| 16 | n_Butane | 0.000181457 | -0.00244828 | 0.101093 | transport_in | 1.46784 | 1.46784 | -1.35002 | -0.103541 | 0 |
| 15 | n_Butane | 0.000166644 | -0.00192592 | 0.100761 | transport_in | 1.35002 | 1.35002 | -1.23611 | -0.102687 | 0 |
| 14 | n_Butane | 0.000149894 | -0.00160907 | 0.0924006 | transport_in | 1.23611 | 1.23611 | -1.13431 | -0.0940097 | 0 |
| 9 | n_Butane | 0.000144663 | -0.00134057 | 0.0175957 | transport_in | 0.978619 | 0.978619 | -0.962255 | -0.0189363 | 0 |
| 11 | n_Butane | 0.000143529 | -0.00135012 | -0.00647365 | transport_out | -0.979891 | 0.966194 | -0.979891 | 0.00512353 | 0 |
| 13 | n_Butane | 0.000140863 | -0.0014129 | 0.0784162 | transport_in | 1.13431 | 1.13431 | -1.04968 | -0.0798291 | 0 |
| 10 | n_Butane | 0.000138757 | -0.00130449 | 0.0048008 | transport_in | 0.979891 | 0.979891 | -0.978619 | -0.00610528 | 0 |

## Top Interior Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 19 | n_Propane | 0.000447708 | 0.00190337 | 0.0441694 | transport_in | 0.413143 | 0.413143 | -0.364083 | -0.042266 | 0 |
| 19 | n_Pentane | 0.000400923 | 0.00110612 | -0.0278571 | transport_out | -0.196962 | 0.17175 | -0.196962 | 0.0289633 | 0 |
| 19 | n_Butane | 0.000351999 | -0.0055149 | -0.0188176 | transport_in | 1.64567 | 1.64567 | -1.64242 | 0.0133027 | 0 |
| 18 | n_Pentane | 0.00033576 | 0.000797213 | 0.0428544 | transport_in | 0.196962 | 0.196962 | -0.152254 | -0.0420572 | 0 |
| 18 | n_Butane | 0.00028905 | -0.00439538 | 0.0494654 | transport_in | 1.64242 | 1.64242 | -1.5738 | -0.0538608 | 0 |
| 17 | n_Butane | 0.000227002 | -0.0032778 | 0.0861731 | transport_in | 1.5738 | 1.5738 | -1.46784 | -0.0894508 | 0 |
| 17 | n_Pentane | 0.000219371 | 0.000469473 | 0.0260568 | transport_in | 0.152254 | 0.152254 | -0.124518 | -0.0255873 | 0 |
| 18 | n_Propane | 0.000202234 | 0.00103001 | -0.094888 | transport_out | -0.453449 | 0.364083 | -0.453449 | 0.095918 | 0 |
| 16 | n_Butane | 0.000181457 | -0.00244828 | 0.101093 | transport_in | 1.46784 | 1.46784 | -1.35002 | -0.103541 | 0 |
| 15 | n_Butane | 0.000166644 | -0.00192592 | 0.100761 | transport_in | 1.35002 | 1.35002 | -1.23611 | -0.102687 | 0 |
| 14 | n_Butane | 0.000149894 | -0.00160907 | 0.0924006 | transport_in | 1.23611 | 1.23611 | -1.13431 | -0.0940097 | 0 |
| 9 | n_Butane | 0.000144663 | -0.00134057 | 0.0175957 | transport_in | 0.978619 | 0.978619 | -0.962255 | -0.0189363 | 0 |
| 11 | n_Butane | 0.000143529 | -0.00135012 | -0.00647365 | transport_out | -0.979891 | 0.966194 | -0.979891 | 0.00512353 | 0 |
| 13 | n_Butane | 0.000140863 | -0.0014129 | 0.0784162 | transport_in | 1.13431 | 1.13431 | -1.04968 | -0.0798291 | 0 |
| 10 | n_Butane | 0.000138757 | -0.00130449 | 0.0048008 | transport_in | 0.979891 | 0.979891 | -0.978619 | -0.00610528 | 0 |

## Top Stage Terms
| stage_1based | max_abs_final_rhs_lbmolps | dominant_stage_term | dominant_stage_term_abs_lbmolps |
|---|---|---|---|
| 19 | 0.0055149 | transport_in | 1.64567 |
| 18 | 0.00439538 | transport_in | 1.64242 |
| 17 | 0.0032778 | transport_in | 1.5738 |
| 16 | 0.00244828 | transport_in | 1.46784 |
| 15 | 0.00192592 | transport_in | 1.35002 |
| 3 | 0.00180694 | transport_out | 1.89161 |
| 14 | 0.00160907 | transport_in | 1.23611 |
| 4 | 0.00151704 | transport_out | 1.65322 |
| 5 | 0.0014744 | transport_out | 1.44826 |
| 13 | 0.0014129 | transport_in | 1.13431 |
| 11 | 0.00135012 | transport_out | 1.03612 |
| 9 | 0.00134057 | transport_out | 1.09758 |
| 6 | 0.00132729 | transport_out | 1.30004 |
| 10 | 0.00130449 | transport_out | 1.06521 |
| 2 | 0.00124988 | transport_out | 2.12622 |
