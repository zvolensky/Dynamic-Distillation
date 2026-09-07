# Vapor RHS Material Terms Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_liq_eq_vap_linearsteady_60s_dt005_20260707\column_profile_20260707_172123.csv`
Time: `25` s

## Summary
| n_stages | max_relative_rhs_per_s | max_relative_rhs_per_s_interior | max_abs_final_rhs_lbmolps |
|---|---|---|---|
| 20 | 0.00196333 | 0.00196333 | 0.0208276 |

## Interpretation
- `final_rhs` is the live RHS contribution to explicit tray vapor component inventory.
- `pre_equilibrium_rhs` is transport/feed/terminal/holdup behavior before equilibrium transfer.
- Dominant terms identify whether the motion is transport, feed, terminal handling, holdup relaxation, or equilibrium transfer.

## Top Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 3 | n_Propane | 0.00196333 | -0.0208276 | -0.309876 | transport_out | -2.88382 | 2.54587 | -2.88382 | 0.289048 | 0 |
| 11 | n_Pentane | 0.00174233 | 0.00209941 | 0.0498542 | transport_in | 0.109705 | 0.109705 | -0.0599098 | -0.0477548 | 0 |
| 11 | n_Butane | 0.00147452 | -0.00916832 | -0.00666669 | transport_out | -1.52529 | 1.51711 | -1.52529 | -0.00250163 | 0 |
| 10 | n_Butane | 0.00138149 | -0.00858266 | 0.00409292 | transport_in | 1.52529 | 1.52529 | -1.52085 | -0.0126756 | 0 |
| 19 | n_Propane | 0.00124413 | -0.00373669 | -0.132289 | transport_out | -0.356644 | 0.225291 | -0.356644 | 0.128553 | 0 |
| 5 | n_Propane | 0.00121452 | -0.0104433 | -0.21198 | transport_out | -2.25401 | 2.03239 | -2.25401 | 0.201536 | 0 |
| 4 | n_Propane | 0.00120152 | -0.0114255 | -0.272038 | transport_out | -2.54587 | 2.25401 | -2.54587 | 0.260612 | 0 |
| 10 | n_Pentane | 0.00100762 | 0.00112503 | 0.0259054 | transport_in | 0.0599098 | 0.0599098 | -0.0339967 | -0.0247804 | 0 |

## Top Interior Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 3 | n_Propane | 0.00196333 | -0.0208276 | -0.309876 | transport_out | -2.88382 | 2.54587 | -2.88382 | 0.289048 | 0 |
| 11 | n_Pentane | 0.00174233 | 0.00209941 | 0.0498542 | transport_in | 0.109705 | 0.109705 | -0.0599098 | -0.0477548 | 0 |
| 11 | n_Butane | 0.00147452 | -0.00916832 | -0.00666669 | transport_out | -1.52529 | 1.51711 | -1.52529 | -0.00250163 | 0 |
| 10 | n_Butane | 0.00138149 | -0.00858266 | 0.00409292 | transport_in | 1.52529 | 1.52529 | -1.52085 | -0.0126756 | 0 |
| 19 | n_Propane | 0.00124413 | -0.00373669 | -0.132289 | transport_out | -0.356644 | 0.225291 | -0.356644 | 0.128553 | 0 |
| 5 | n_Propane | 0.00121452 | -0.0104433 | -0.21198 | transport_out | -2.25401 | 2.03239 | -2.25401 | 0.201536 | 0 |
| 4 | n_Propane | 0.00120152 | -0.0114255 | -0.272038 | transport_out | -2.54587 | 2.25401 | -2.54587 | 0.260612 | 0 |
| 10 | n_Pentane | 0.00100762 | 0.00112503 | 0.0259054 | transport_in | 0.0599098 | 0.0599098 | -0.0339967 | -0.0247804 | 0 |

## Top Stage Terms
| stage_1based | max_abs_final_rhs_lbmolps | dominant_stage_term | dominant_stage_term_abs_lbmolps |
|---|---|---|---|
| 3 | 0.0208276 | transport_out | 2.88382 |
| 2 | 0.0205661 | transport_out | 2.89463 |
| 4 | 0.0114255 | transport_out | 2.54587 |
| 5 | 0.0104433 | transport_out | 2.25401 |
| 11 | 0.00916832 | transport_out | 1.62866 |
| 10 | 0.00858266 | transport_out | 1.67113 |
| 6 | 0.00785559 | transport_out | 2.03239 |
| 7 | 0.00621246 | transport_out | 1.88107 |
