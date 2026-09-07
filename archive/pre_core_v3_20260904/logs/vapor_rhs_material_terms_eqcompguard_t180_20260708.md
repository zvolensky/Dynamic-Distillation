# Vapor RHS Material Terms Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_liq_eq_vap_linearsteady_180s_eqcompguard_20260708\column_profile_20260708_081150.csv`
Time: `180` s

## Summary
| n_stages | max_relative_rhs_per_s | max_relative_rhs_per_s_interior | max_abs_final_rhs_lbmolps |
|---|---|---|---|
| 20 | 0.00246384 | 0.00246384 | 0.0087094 |

## Interpretation
- `final_rhs` is the live RHS contribution to explicit tray vapor component inventory.
- `pre_equilibrium_rhs` is transport/feed/terminal/holdup behavior before equilibrium transfer.
- Dominant terms identify whether the motion is transport, feed, terminal handling, holdup relaxation, or equilibrium transfer.

## Top Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 19 | n_Propane | 0.00246384 | -0.00636555 | -0.143412 | transport_out | -0.31378 | 0.172488 | -0.31378 | 0.137047 | 0 |
| 18 | n_Propane | 0.00115284 | -0.0037061 | -0.132744 | transport_out | -0.446543 | 0.31378 | -0.446543 | 0.129038 | 0 |
| 3 | n_Propane | 0.000881107 | -0.00825452 | -0.215229 | transport_out | -2.06549 | 1.81665 | -2.06549 | 0.206975 | 0 |
| 4 | n_Propane | 0.000869316 | -0.00735516 | -0.193943 | transport_out | -1.81665 | 1.60429 | -1.81665 | 0.186588 | 0 |
| 18 | n_Butane | 0.000867179 | -0.00809821 | 0.0905912 | transport_in | 1.77177 | 1.77177 | -1.68125 | -0.0986894 | 0 |
| 5 | n_Propane | 0.000864492 | -0.00660015 | -0.150194 | transport_out | -1.60429 | 1.44346 | -1.60429 | 0.143594 | 0 |
| 9 | n_Butane | 0.000854062 | -0.00457995 | 0.0325331 | transport_in | 1.07238 | 1.07238 | -1.04375 | -0.037113 | 0 |
| 6 | n_Propane | 0.000846341 | -0.00595905 | -0.105274 | transport_out | -1.44346 | 1.33512 | -1.44346 | 0.0993151 | 0 |
| 9 | n_Propane | 0.000837132 | -0.00510436 | -0.0583874 | transport_out | -1.21958 | 1.15663 | -1.21958 | 0.0532831 | 0 |
| 15 | n_Propane | 0.000836251 | -0.00380575 | -0.126121 | transport_out | -0.835675 | 0.711682 | -0.835675 | 0.122315 | 0 |
| 14 | n_Propane | 0.000835345 | -0.00419427 | -0.115587 | transport_out | -0.9499 | 0.835675 | -0.9499 | 0.111393 | 0 |
| 13 | n_Propane | 0.000833997 | -0.00452735 | -0.0995307 | transport_out | -1.04806 | 0.9499 | -1.04806 | 0.0950034 | 0 |
| 11 | n_Propane | 0.000833578 | -0.00486904 | -0.0261718 | transport_out | -1.14928 | 1.12076 | -1.14928 | 0.0213027 | 0 |
| 7 | n_Propane | 0.000830695 | -0.00550251 | -0.0698006 | transport_out | -1.33512 | 1.26569 | -1.33512 | 0.0642981 | 0 |
| 11 | n_Butane | 0.000827965 | -0.00457944 | -0.012675 | transport_out | -1.07565 | 1.06077 | -1.07565 | 0.00809556 | 0 |
| 12 | n_Propane | 0.000823408 | -0.00481661 | -0.0828298 | transport_out | -1.12076 | 1.04806 | -1.12076 | 0.0780132 | 0 |
| 17 | n_Propane | 0.000819265 | -0.00319386 | -0.135104 | transport_out | -0.57949 | 0.446543 | -0.57949 | 0.13191 | 0 |
| 8 | n_Propane | 0.000818481 | -0.00519529 | -0.0476152 | transport_out | -1.26569 | 1.21958 | -1.26569 | 0.0424199 | 0 |
| 8 | n_Butane | 0.000814784 | -0.00430153 | 0.0296777 | transport_in | 1.04375 | 1.04375 | -1.01287 | -0.0339792 | 0 |
| 14 | n_Butane | 0.000811387 | -0.00503134 | 0.10103 | transport_in | 1.33143 | 1.33143 | -1.22864 | -0.106061 | 0 |

## Top Interior Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 19 | n_Propane | 0.00246384 | -0.00636555 | -0.143412 | transport_out | -0.31378 | 0.172488 | -0.31378 | 0.137047 | 0 |
| 18 | n_Propane | 0.00115284 | -0.0037061 | -0.132744 | transport_out | -0.446543 | 0.31378 | -0.446543 | 0.129038 | 0 |
| 3 | n_Propane | 0.000881107 | -0.00825452 | -0.215229 | transport_out | -2.06549 | 1.81665 | -2.06549 | 0.206975 | 0 |
| 4 | n_Propane | 0.000869316 | -0.00735516 | -0.193943 | transport_out | -1.81665 | 1.60429 | -1.81665 | 0.186588 | 0 |
| 18 | n_Butane | 0.000867179 | -0.00809821 | 0.0905912 | transport_in | 1.77177 | 1.77177 | -1.68125 | -0.0986894 | 0 |
| 5 | n_Propane | 0.000864492 | -0.00660015 | -0.150194 | transport_out | -1.60429 | 1.44346 | -1.60429 | 0.143594 | 0 |
| 9 | n_Butane | 0.000854062 | -0.00457995 | 0.0325331 | transport_in | 1.07238 | 1.07238 | -1.04375 | -0.037113 | 0 |
| 6 | n_Propane | 0.000846341 | -0.00595905 | -0.105274 | transport_out | -1.44346 | 1.33512 | -1.44346 | 0.0993151 | 0 |
| 9 | n_Propane | 0.000837132 | -0.00510436 | -0.0583874 | transport_out | -1.21958 | 1.15663 | -1.21958 | 0.0532831 | 0 |
| 15 | n_Propane | 0.000836251 | -0.00380575 | -0.126121 | transport_out | -0.835675 | 0.711682 | -0.835675 | 0.122315 | 0 |
| 14 | n_Propane | 0.000835345 | -0.00419427 | -0.115587 | transport_out | -0.9499 | 0.835675 | -0.9499 | 0.111393 | 0 |
| 13 | n_Propane | 0.000833997 | -0.00452735 | -0.0995307 | transport_out | -1.04806 | 0.9499 | -1.04806 | 0.0950034 | 0 |
| 11 | n_Propane | 0.000833578 | -0.00486904 | -0.0261718 | transport_out | -1.14928 | 1.12076 | -1.14928 | 0.0213027 | 0 |
| 7 | n_Propane | 0.000830695 | -0.00550251 | -0.0698006 | transport_out | -1.33512 | 1.26569 | -1.33512 | 0.0642981 | 0 |
| 11 | n_Butane | 0.000827965 | -0.00457944 | -0.012675 | transport_out | -1.07565 | 1.06077 | -1.07565 | 0.00809556 | 0 |
| 12 | n_Propane | 0.000823408 | -0.00481661 | -0.0828298 | transport_out | -1.12076 | 1.04806 | -1.12076 | 0.0780132 | 0 |
| 17 | n_Propane | 0.000819265 | -0.00319386 | -0.135104 | transport_out | -0.57949 | 0.446543 | -0.57949 | 0.13191 | 0 |
| 8 | n_Propane | 0.000818481 | -0.00519529 | -0.0476152 | transport_out | -1.26569 | 1.21958 | -1.26569 | 0.0424199 | 0 |
| 8 | n_Butane | 0.000814784 | -0.00430153 | 0.0296777 | transport_in | 1.04375 | 1.04375 | -1.01287 | -0.0339792 | 0 |
| 14 | n_Butane | 0.000811387 | -0.00503134 | 0.10103 | transport_in | 1.33143 | 1.33143 | -1.22864 | -0.106061 | 0 |

## Top Stage Terms
| stage_1based | max_abs_final_rhs_lbmolps | dominant_stage_term | dominant_stage_term_abs_lbmolps |
|---|---|---|---|
| 2 | 0.0087094 | transport_in | 2.06549 |
| 3 | 0.00825452 | transport_out | 2.06549 |
| 18 | 0.00809821 | transport_in | 1.77177 |
| 4 | 0.00735516 | transport_out | 1.81665 |
| 5 | 0.00660015 | transport_out | 1.60429 |
| 19 | 0.00636555 | transport_in | 1.83692 |
| 17 | 0.00597776 | transport_in | 1.68125 |
| 6 | 0.00595905 | transport_out | 1.44346 |
| 16 | 0.00569124 | transport_in | 1.56527 |
| 7 | 0.00550251 | transport_out | 1.33512 |
| 15 | 0.00539084 | transport_in | 1.44487 |
| 8 | 0.00519529 | transport_out | 1.26569 |
| 9 | 0.00510436 | transport_out | 1.21958 |
| 14 | 0.00503134 | transport_in | 1.33143 |
| 11 | 0.00486904 | transport_out | 1.14928 |
| 12 | 0.00481661 | transport_in | 1.14085 |
| 13 | 0.00469604 | transport_in | 1.22864 |
| 10 | 0.00460819 | transport_out | 1.15663 |
| 1 | 0 | transport_in | 2.05198 |
| 20 | 0 | transport_out | 1.83692 |
