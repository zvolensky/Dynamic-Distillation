# Vapor RHS Material Terms Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_liq_eq_vap_linearsteady_60s_20260707\column_profile_20260707_171839.csv`
Time: `40` s

## Summary
| n_stages | max_relative_rhs_per_s | max_relative_rhs_per_s_interior | max_abs_final_rhs_lbmolps |
|---|---|---|---|
| 20 | 0.00172378 | 0.00172378 | 0.0178632 |

## Interpretation
- `final_rhs` is the live RHS contribution to explicit tray vapor component inventory.
- `pre_equilibrium_rhs` is transport/feed/terminal/holdup behavior before equilibrium transfer.
- Dominant terms identify whether the motion is transport, feed, terminal handling, holdup relaxation, or equilibrium transfer.

## Top Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 3 | n_Propane | 0.00172378 | -0.0178632 | -0.305361 | transport_out | -2.86657 | 2.52098 | -2.86657 | 0.287497 | 0 |
| 12 | n_Butane | 0.00162211 | -0.0102731 | 0.122769 | transport_out | -1.51129 | 1.0998 | -1.51129 | -0.133042 | 0 |
| 12 | n_Propane | 0.00155213 | -0.0100213 | -0.21382 | transport_out | -1.54623 | 1.019 | -1.54623 | 0.203799 | 0 |
| 11 | n_Butane | 0.00143529 | -0.00874891 | 0.0115178 | transport_in | 1.51129 | 1.51129 | -1.5034 | -0.0202667 | 0 |
| 3 | n_Butane | 0.00112636 | -0.00296914 | 0.2842 | transport_in | 0.778071 | 0.778071 | -0.500901 | -0.287169 | 0 |
| 10 | n_Butane | 0.00111243 | -0.00679664 | 0.00347338 | transport_in | 1.5034 | 1.5034 | -1.5005 | -0.01027 | 0 |
| 19 | n_Propane | 0.00110165 | -0.00325301 | -0.131433 | transport_out | -0.351048 | 0.220742 | -0.351048 | 0.12818 | 0 |
| 4 | n_Propane | 0.00103163 | -0.00967451 | -0.268848 | transport_out | -2.52098 | 2.23013 | -2.52098 | 0.259173 | 0 |
| 9 | n_Butane | 0.000914759 | -0.00553488 | 0.019648 | transport_in | 1.5005 | 1.5005 | -1.47982 | -0.0251829 | 0 |
| 18 | n_Propane | 0.000879804 | -0.00319367 | -0.123008 | transport_out | -0.472874 | 0.351048 | -0.472874 | 0.119814 | 0 |
| 19 | n_Pentane | 0.000855788 | -0.00161936 | 0.0743038 | transport_in | 0.235212 | 0.235212 | -0.160393 | -0.0759231 | 0 |
| 4 | n_Butane | 0.000835466 | -0.00299575 | 0.255415 | transport_in | 1.02669 | 1.02669 | -0.778071 | -0.258411 | 0 |

## Top Interior Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 3 | n_Propane | 0.00172378 | -0.0178632 | -0.305361 | transport_out | -2.86657 | 2.52098 | -2.86657 | 0.287497 | 0 |
| 12 | n_Butane | 0.00162211 | -0.0102731 | 0.122769 | transport_out | -1.51129 | 1.0998 | -1.51129 | -0.133042 | 0 |
| 12 | n_Propane | 0.00155213 | -0.0100213 | -0.21382 | transport_out | -1.54623 | 1.019 | -1.54623 | 0.203799 | 0 |
| 11 | n_Butane | 0.00143529 | -0.00874891 | 0.0115178 | transport_in | 1.51129 | 1.51129 | -1.5034 | -0.0202667 | 0 |
| 3 | n_Butane | 0.00112636 | -0.00296914 | 0.2842 | transport_in | 0.778071 | 0.778071 | -0.500901 | -0.287169 | 0 |
| 10 | n_Butane | 0.00111243 | -0.00679664 | 0.00347338 | transport_in | 1.5034 | 1.5034 | -1.5005 | -0.01027 | 0 |
| 19 | n_Propane | 0.00110165 | -0.00325301 | -0.131433 | transport_out | -0.351048 | 0.220742 | -0.351048 | 0.12818 | 0 |
| 4 | n_Propane | 0.00103163 | -0.00967451 | -0.268848 | transport_out | -2.52098 | 2.23013 | -2.52098 | 0.259173 | 0 |
| 9 | n_Butane | 0.000914759 | -0.00553488 | 0.019648 | transport_in | 1.5005 | 1.5005 | -1.47982 | -0.0251829 | 0 |
| 18 | n_Propane | 0.000879804 | -0.00319367 | -0.123008 | transport_out | -0.472874 | 0.351048 | -0.472874 | 0.119814 | 0 |
| 19 | n_Pentane | 0.000855788 | -0.00161936 | 0.0743038 | transport_in | 0.235212 | 0.235212 | -0.160393 | -0.0759231 | 0 |
| 4 | n_Butane | 0.000835466 | -0.00299575 | 0.255415 | transport_in | 1.02669 | 1.02669 | -0.778071 | -0.258411 | 0 |

## Top Stage Terms
| stage_1based | max_abs_final_rhs_lbmolps | dominant_stage_term | dominant_stage_term_abs_lbmolps |
|---|---|---|---|
| 3 | 0.0178632 | transport_out | 2.86657 |
| 12 | 0.0102731 | transport_out | 1.54623 |
| 4 | 0.00967451 | transport_out | 2.52098 |
| 11 | 0.00874891 | transport_out | 1.62229 |
| 10 | 0.00679664 | transport_out | 1.66323 |
| 5 | 0.00616557 | transport_out | 2.23013 |
| 9 | 0.00553488 | transport_out | 1.70661 |
| 2 | 0.00533725 | transport_out | 2.87566 |
| 6 | 0.00524829 | transport_out | 2.01357 |
| 17 | 0.00511561 | transport_in | 1.63712 |
| 18 | 0.00491712 | transport_in | 1.72134 |
| 13 | 0.00487367 | transport_in | 1.20181 |
