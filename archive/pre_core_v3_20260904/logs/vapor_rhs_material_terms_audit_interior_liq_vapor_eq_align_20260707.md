# Vapor RHS Material Terms Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_interior_liq_vapor_eq_align_rhs_terms_20260707\column_profile_20260707_153257.csv`
Time: `0.2` s

## Summary
| n_stages | max_relative_rhs_per_s | max_relative_rhs_per_s_interior | max_abs_final_rhs_lbmolps |
|---|---|---|---|
| 20 | 0.0453789 | 0.0453789 | 0.161902 |

## Interpretation
- `final_rhs` is the live RHS contribution to explicit tray vapor component inventory.
- `pre_equilibrium_rhs` is transport/feed/terminal/holdup behavior before equilibrium transfer.
- Dominant terms identify whether the motion is transport, feed, terminal handling, holdup relaxation, or equilibrium transfer.

## Top Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 3 | n_Butane | 0.0453789 | 0.120286 | 0.202942 | transport_in | 0.537559 | 0.537559 | -0.334591 | -0.0826568 | 0 |
| 4 | n_Butane | 0.0283641 | 0.10355 | 0.179402 | transport_in | 0.717542 | 0.717542 | -0.537559 | -0.0758519 | 0 |
| 19 | n_Propane | 0.0274448 | -0.0865203 | -0.135882 | transport_out | -0.380301 | 0.243309 | -0.380301 | 0.049362 | 0 |
| 19 | n_Pentane | 0.0224827 | 0.043924 | 0.0795959 | transport_in | 0.247597 | 0.247597 | -0.168493 | -0.0356719 | 0 |
| 5 | n_Butane | 0.0171789 | 0.0782924 | 0.137523 | transport_in | 0.856465 | 0.856465 | -0.717542 | -0.0592302 | 0 |
| 18 | n_Propane | 0.0167696 | -0.0631176 | -0.106274 | transport_out | -0.487855 | 0.380301 | -0.487855 | 0.0431561 | 0 |
| 2 | n_Butane | 0.0148678 | -0.108519 | -0.0232203 | transport_out | -0.364267 | 0.334591 | -0.364267 | -0.0852984 | 0 |
| 17 | n_Propane | 0.0147084 | -0.0655761 | -0.120452 | transport_out | -0.609533 | 0.487855 | -0.609533 | 0.054876 | 0 |
| 4 | n_Propane | 0.0147062 | -0.147161 | -0.22307 | transport_out | -1.82653 | 1.60543 | -1.82653 | 0.0759095 | 0 |
| 18 | n_Pentane | 0.0146463 | 0.0253145 | 0.0402577 | transport_in | 0.168493 | 0.168493 | -0.128573 | -0.0149432 | 0 |
| 3 | n_Propane | 0.0142732 | -0.159965 | -0.242647 | transport_out | -2.06901 | 1.82653 | -2.06901 | 0.0826817 | 0 |
| 11 | n_Pentane | 0.0138662 | 0.0162141 | 0.0363987 | transport_in | 0.0703204 | 0.0703204 | -0.0338244 | -0.0201846 | 0 |

## Top Interior Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 3 | n_Butane | 0.0453789 | 0.120286 | 0.202942 | transport_in | 0.537559 | 0.537559 | -0.334591 | -0.0826568 | 0 |
| 4 | n_Butane | 0.0283641 | 0.10355 | 0.179402 | transport_in | 0.717542 | 0.717542 | -0.537559 | -0.0758519 | 0 |
| 19 | n_Propane | 0.0274448 | -0.0865203 | -0.135882 | transport_out | -0.380301 | 0.243309 | -0.380301 | 0.049362 | 0 |
| 19 | n_Pentane | 0.0224827 | 0.043924 | 0.0795959 | transport_in | 0.247597 | 0.247597 | -0.168493 | -0.0356719 | 0 |
| 5 | n_Butane | 0.0171789 | 0.0782924 | 0.137523 | transport_in | 0.856465 | 0.856465 | -0.717542 | -0.0592302 | 0 |
| 18 | n_Propane | 0.0167696 | -0.0631176 | -0.106274 | transport_out | -0.487855 | 0.380301 | -0.487855 | 0.0431561 | 0 |
| 2 | n_Butane | 0.0148678 | -0.108519 | -0.0232203 | transport_out | -0.364267 | 0.334591 | -0.364267 | -0.0852984 | 0 |
| 17 | n_Propane | 0.0147084 | -0.0655761 | -0.120452 | transport_out | -0.609533 | 0.487855 | -0.609533 | 0.054876 | 0 |
| 4 | n_Propane | 0.0147062 | -0.147161 | -0.22307 | transport_out | -1.82653 | 1.60543 | -1.82653 | 0.0759095 | 0 |
| 18 | n_Pentane | 0.0146463 | 0.0253145 | 0.0402577 | transport_in | 0.168493 | 0.168493 | -0.128573 | -0.0149432 | 0 |
| 3 | n_Propane | 0.0142732 | -0.159965 | -0.242647 | transport_out | -2.06901 | 1.82653 | -2.06901 | 0.0826817 | 0 |
| 11 | n_Pentane | 0.0138662 | 0.0162141 | 0.0363987 | transport_in | 0.0703204 | 0.0703204 | -0.0338244 | -0.0201846 | 0 |

## Top Stage Terms
| stage_1based | max_abs_final_rhs_lbmolps | dominant_stage_term | dominant_stage_term_abs_lbmolps |
|---|---|---|---|
| 2 | 0.161902 | transport_in | 2.06901 |
| 3 | 0.159965 | transport_out | 2.06901 |
| 4 | 0.147161 | transport_out | 1.82653 |
| 5 | 0.108324 | transport_out | 1.60543 |
| 19 | 0.0865203 | transport_in | 1.73966 |
| 6 | 0.0734991 | transport_out | 1.44088 |
| 16 | 0.069553 | transport_in | 1.52673 |
| 17 | 0.0655761 | transport_in | 1.62519 |
| 15 | 0.0648159 | transport_in | 1.41563 |
| 18 | 0.0631176 | transport_in | 1.68751 |
| 14 | 0.0589481 | transport_in | 1.30774 |
| 13 | 0.0509793 | transport_in | 1.21069 |
