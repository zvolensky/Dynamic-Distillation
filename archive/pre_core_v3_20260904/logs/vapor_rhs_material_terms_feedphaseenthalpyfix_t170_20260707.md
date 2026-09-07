# Vapor RHS Material Terms Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_liq_eq_vap_linearsteady_180s_feedphaseenthalpyfix_20260707\column_profile_20260707_215312.csv`
Time: `170` s

## Summary
| n_stages | max_relative_rhs_per_s | max_relative_rhs_per_s_interior | max_abs_final_rhs_lbmolps |
|---|---|---|---|
| 20 | 0.071686 | 0.071686 | 0.138248 |

## Interpretation
- `final_rhs` is the live RHS contribution to explicit tray vapor component inventory.
- `pre_equilibrium_rhs` is transport/feed/terminal/holdup behavior before equilibrium transfer.
- Dominant terms identify whether the motion is transport, feed, terminal handling, holdup relaxation, or equilibrium transfer.

## Top Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 19 | n_Propane | 0.071686 | -0.138248 | 0.0219306 | transport_in | 0.202941 | 0.202941 | -0.183754 | -0.160179 | 0 |
| 19 | n_Pentane | 0.0527646 | 0.119125 | -0.0402199 | transport_out | -0.248892 | 0.204956 | -0.248892 | 0.159345 | 0 |
| 18 | n_Pentane | 0.0230597 | 0.0370452 | 0.129536 | transport_in | 0.248892 | 0.248892 | -0.118813 | -0.0924904 | 0 |
| 18 | n_Propane | 0.0124161 | -0.039932 | -0.252375 | transport_out | -0.434145 | 0.183754 | -0.434145 | 0.212443 | 0 |
| 19 | n_Butane | 0.00497325 | 0.0502118 | 0.0493781 | transport_in | 1.82266 | 1.82266 | -1.80016 | 0.000833752 | 0 |
| 17 | n_Pentane | 0.00203669 | 0.00305096 | 0.0209454 | transport_in | 0.118813 | 0.118813 | -0.0973762 | -0.0178944 | 0 |
| 17 | n_Propane | 0.0019833 | -0.00778973 | -0.141202 | transport_out | -0.572457 | 0.434145 | -0.572457 | 0.133413 | 0 |
| 18 | n_Butane | 0.00170852 | 0.0161552 | 0.136108 | transport_in | 1.80016 | 1.80016 | -1.65648 | -0.119952 | 0 |
| 15 | n_Butane | 0.0011103 | -0.0074369 | 0.106997 | transport_in | 1.42249 | 1.42249 | -1.3108 | -0.114434 | 0 |
| 14 | n_Butane | 0.0011075 | -0.00690821 | 0.0982188 | transport_in | 1.3108 | 1.3108 | -1.20963 | -0.105127 | 0 |
| 13 | n_Butane | 0.00109136 | -0.00638911 | 0.0837827 | transport_in | 1.20963 | 1.20963 | -1.12324 | -0.0901718 | 0 |
| 12 | n_Butane | 0.00105442 | -0.00592713 | 0.0682932 | transport_in | 1.12324 | 1.12324 | -1.04431 | -0.0742203 | 0 |
| 5 | n_Butane | 0.00104797 | -0.00424861 | 0.137722 | transport_in | 0.855738 | 0.855738 | -0.722082 | -0.141971 | 0 |
| 4 | n_Butane | 0.00104392 | -0.00343605 | 0.18131 | transport_in | 0.722082 | 0.722082 | -0.54586 | -0.184746 | 0 |
| 6 | n_Butane | 0.00103618 | -0.00483214 | 0.092999 | transport_in | 0.947877 | 0.947877 | -0.855738 | -0.0978311 | 0 |
| 7 | n_Butane | 0.0010268 | -0.00522158 | 0.0572343 | transport_in | 1.00654 | 1.00654 | -0.947877 | -0.0624558 | 0 |
| 3 | n_Butane | 0.00102525 | -0.00250574 | 0.20258 | transport_in | 0.54586 | 0.54586 | -0.348664 | -0.205085 | 0 |
| 8 | n_Butane | 0.0010198 | -0.00545854 | 0.0315326 | transport_in | 1.04066 | 1.04066 | -1.00654 | -0.0369911 | 0 |
| 10 | n_Butane | 0.00101469 | -0.00563341 | 0.000666697 | transport_in | 1.05749 | 1.05749 | -1.0568 | -0.00630011 | 0 |
| 9 | n_Butane | 0.00101323 | -0.00557791 | 0.0133995 | transport_in | 1.0568 | 1.0568 | -1.04066 | -0.0189774 | 0 |

## Top Interior Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 19 | n_Propane | 0.071686 | -0.138248 | 0.0219306 | transport_in | 0.202941 | 0.202941 | -0.183754 | -0.160179 | 0 |
| 19 | n_Pentane | 0.0527646 | 0.119125 | -0.0402199 | transport_out | -0.248892 | 0.204956 | -0.248892 | 0.159345 | 0 |
| 18 | n_Pentane | 0.0230597 | 0.0370452 | 0.129536 | transport_in | 0.248892 | 0.248892 | -0.118813 | -0.0924904 | 0 |
| 18 | n_Propane | 0.0124161 | -0.039932 | -0.252375 | transport_out | -0.434145 | 0.183754 | -0.434145 | 0.212443 | 0 |
| 19 | n_Butane | 0.00497325 | 0.0502118 | 0.0493781 | transport_in | 1.82266 | 1.82266 | -1.80016 | 0.000833752 | 0 |
| 17 | n_Pentane | 0.00203669 | 0.00305096 | 0.0209454 | transport_in | 0.118813 | 0.118813 | -0.0973762 | -0.0178944 | 0 |
| 17 | n_Propane | 0.0019833 | -0.00778973 | -0.141202 | transport_out | -0.572457 | 0.434145 | -0.572457 | 0.133413 | 0 |
| 18 | n_Butane | 0.00170852 | 0.0161552 | 0.136108 | transport_in | 1.80016 | 1.80016 | -1.65648 | -0.119952 | 0 |
| 15 | n_Butane | 0.0011103 | -0.0074369 | 0.106997 | transport_in | 1.42249 | 1.42249 | -1.3108 | -0.114434 | 0 |
| 14 | n_Butane | 0.0011075 | -0.00690821 | 0.0982188 | transport_in | 1.3108 | 1.3108 | -1.20963 | -0.105127 | 0 |
| 13 | n_Butane | 0.00109136 | -0.00638911 | 0.0837827 | transport_in | 1.20963 | 1.20963 | -1.12324 | -0.0901718 | 0 |
| 12 | n_Butane | 0.00105442 | -0.00592713 | 0.0682932 | transport_in | 1.12324 | 1.12324 | -1.04431 | -0.0742203 | 0 |
| 5 | n_Butane | 0.00104797 | -0.00424861 | 0.137722 | transport_in | 0.855738 | 0.855738 | -0.722082 | -0.141971 | 0 |
| 4 | n_Butane | 0.00104392 | -0.00343605 | 0.18131 | transport_in | 0.722082 | 0.722082 | -0.54586 | -0.184746 | 0 |
| 6 | n_Butane | 0.00103618 | -0.00483214 | 0.092999 | transport_in | 0.947877 | 0.947877 | -0.855738 | -0.0978311 | 0 |
| 7 | n_Butane | 0.0010268 | -0.00522158 | 0.0572343 | transport_in | 1.00654 | 1.00654 | -0.947877 | -0.0624558 | 0 |
| 3 | n_Butane | 0.00102525 | -0.00250574 | 0.20258 | transport_in | 0.54586 | 0.54586 | -0.348664 | -0.205085 | 0 |
| 8 | n_Butane | 0.0010198 | -0.00545854 | 0.0315326 | transport_in | 1.04066 | 1.04066 | -1.00654 | -0.0369911 | 0 |
| 10 | n_Butane | 0.00101469 | -0.00563341 | 0.000666697 | transport_in | 1.05749 | 1.05749 | -1.0568 | -0.00630011 | 0 |
| 9 | n_Butane | 0.00101323 | -0.00557791 | 0.0133995 | transport_in | 1.0568 | 1.0568 | -1.04066 | -0.0189774 | 0 |

## Top Stage Terms
| stage_1based | max_abs_final_rhs_lbmolps | dominant_stage_term | dominant_stage_term_abs_lbmolps |
|---|---|---|---|
| 19 | 0.138248 | transport_in | 1.82266 |
| 18 | 0.039932 | transport_in | 1.80016 |
| 2 | 0.0099766 | transport_in | 2.0389 |
| 3 | 0.00920996 | transport_out | 2.0389 |
| 4 | 0.00824054 | transport_out | 1.79286 |
| 16 | 0.00791043 | transport_in | 1.54096 |
| 17 | 0.00778973 | transport_in | 1.65648 |
| 5 | 0.00756124 | transport_out | 1.58259 |
| 15 | 0.0074369 | transport_in | 1.42249 |
| 6 | 0.00700362 | transport_out | 1.42304 |
| 14 | 0.00690821 | transport_in | 1.3108 |
| 7 | 0.00661866 | transport_out | 1.31478 |
| 13 | 0.00638911 | transport_in | 1.20963 |
| 8 | 0.00636148 | transport_out | 1.24419 |
| 9 | 0.00618751 | transport_out | 1.19799 |
| 10 | 0.00609722 | transport_out | 1.16573 |
| 12 | 0.00592713 | transport_in | 1.12324 |
| 11 | 0.0059158 | transport_out | 1.1361 |
| 1 | 0 | transport_in | 2.02355 |
| 20 | 0 | transport_out | 1.82266 |
