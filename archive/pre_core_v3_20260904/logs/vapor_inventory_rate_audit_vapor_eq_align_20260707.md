# Vapor Inventory Rate Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_vapor_eq_align_smoke_20260707\column_profile_20260707_105625.csv`
Window: `0` to `0.2` s

## Summary
| n_stages | max_abs_relative_inventory_rate_per_s | max_abs_relative_inventory_rate_per_s_interior | max_abs_dn_dt_lbmolps | max_abs_convective_lbmolps_est | max_abs_unaccounted_lbmolps_est |
|---|---|---|---|---|---|
| 20 | 1.30168 | 1.30168 | 3.77941 | 2.02317 | 3.77941 |

## Interpretation
- The relative inventory rate is the same finite-difference family used by the dynamic smoke detector.
- Large estimated convective terms indicate startup motion driven by adjacent vapor composition/flow mismatch.
- Large unaccounted terms indicate effects outside simple vapor convection, such as phase transfer, total vapor holdup changes, or boundary coupling.

## Top Component Rates
| stage_1based | component | relative_inventory_rate_per_s | dn_dt_lbmolps | convective_lbmolps_est | unaccounted_lbmolps_est | MV_final_lbmol | V_in_lbmolph_est | V_out_lbmolph | y_in_minus_y |
|---|---|---|---|---|---|---|---|---|---|
| 3 | n_Butane | 1.30168 | -3.45017 | 0.201001 | -3.65117 | 11.8575 | 8452.9 | 8607.27 | 0.0881465 |
| 20 | n_Propane | 1.25891 | 3.77941 | 0 | 3.77941 | 12.6862 | 8030.03 | 8030.03 | 0 |
| 4 | n_Butane | 0.762633 | -2.784 | 0.178744 | -2.96274 | 11.6585 | 8308.19 | 8452.9 | 0.0814112 |
| 5 | n_Butane | 0.428866 | -1.95429 | 0.137953 | -2.09224 | 11.52 | 8220.28 | 8308.19 | 0.0637171 |
| 20 | n_Pentane | 0.424811 | -0.88596 | 0 | -0.88596 | 12.6862 | 8030.03 | 8030.03 | 0 |
| 17 | n_Propane | 0.342376 | 1.52862 | -0.122233 | 1.65086 | 12.7333 | 8085.28 | 8086.38 | -0.0543877 |
| 16 | n_Propane | 0.334286 | 1.73579 | -0.120767 | 1.85656 | 12.7724 | 8086.38 | 8027.72 | -0.056146 |
| 18 | n_Pentane | 0.331439 | -0.573067 | 0.0377496 | -0.610817 | 12.6994 | 8077.03 | 8085.28 | 0.016884 |
| 15 | n_Propane | 0.316748 | 1.66548 | -0.112714 | 1.77819 | 11.1615 | 8027.72 | 7970.86 | -0.0532482 |
| 3 | n_Propane | 0.308251 | 3.45445 | -0.244048 | 3.6985 | 11.8575 | 8452.9 | 8607.27 | -0.0882176 |
| 2 | n_Butane | 0.293278 | -2.08213 | -0.0170357 | -2.0651 | 41.3738 | 8607.27 | 8543.03 | -0.00822555 |
| 17 | n_Pentane | 0.283327 | -0.457781 | 0.0203102 | -0.478092 | 12.7333 | 8085.28 | 8086.38 | 0.00904979 |

## Top Interior Component Rates
| stage_1based | component | relative_inventory_rate_per_s | dn_dt_lbmolps | convective_lbmolps_est | unaccounted_lbmolps_est | MV_final_lbmol | V_in_lbmolph_est | V_out_lbmolph | y_in_minus_y |
|---|---|---|---|---|---|---|---|---|---|
| 3 | n_Butane | 1.30168 | -3.45017 | 0.201001 | -3.65117 | 11.8575 | 8452.9 | 8607.27 | 0.0881465 |
| 4 | n_Butane | 0.762633 | -2.784 | 0.178744 | -2.96274 | 11.6585 | 8308.19 | 8452.9 | 0.0814112 |
| 5 | n_Butane | 0.428866 | -1.95429 | 0.137953 | -2.09224 | 11.52 | 8220.28 | 8308.19 | 0.0637171 |
| 17 | n_Propane | 0.342376 | 1.52862 | -0.122233 | 1.65086 | 12.7333 | 8085.28 | 8086.38 | -0.0543877 |
| 16 | n_Propane | 0.334286 | 1.73579 | -0.120767 | 1.85656 | 12.7724 | 8086.38 | 8027.72 | -0.056146 |
| 18 | n_Pentane | 0.331439 | -0.573067 | 0.0377496 | -0.610817 | 12.6994 | 8077.03 | 8085.28 | 0.016884 |
| 15 | n_Propane | 0.316748 | 1.66548 | -0.112714 | 1.77819 | 11.1615 | 8027.72 | 7970.86 | -0.0532482 |
| 3 | n_Propane | 0.308251 | 3.45445 | -0.244048 | 3.6985 | 11.8575 | 8452.9 | 8607.27 | -0.0882176 |
| 2 | n_Butane | 0.293278 | -2.08213 | -0.0170357 | -2.0651 | 41.3738 | 8607.27 | 8543.03 | -0.00822555 |
| 17 | n_Pentane | 0.283327 | -0.457781 | 0.0203102 | -0.478092 | 12.7333 | 8085.28 | 8086.38 | 0.00904979 |
| 4 | n_Propane | 0.27928 | 2.79471 | -0.219351 | 3.01406 | 11.6585 | 8308.19 | 8452.9 | -0.0815901 |
| 11 | n_Pentane | 0.27874 | -0.324249 | 0.0380374 | -0.362286 | 11.2984 | 7997.75 | 8066.59 | 0.017246 |

## Top Stage Rates
| stage_1based | max_abs_relative_inventory_rate_per_s | max_abs_dn_dt_lbmolps | max_abs_convective_lbmolps_est | max_abs_unaccounted_lbmolps_est | stage_mass_balance_resid_lbmolps | eq_phase_change_lbmolps_tray |
|---|---|---|---|---|---|---|
| 3 | 1.30168 | 3.45445 | 0.244048 | 3.6985 | 0.0205816 | -1.06382e-15 |
| 20 | 1.25891 | 3.77941 | 0 | 3.77941 | 0 | 0 |
| 4 | 0.762633 | 2.79471 | 0.219351 | 3.01406 | -0.00224791 | -7.76289e-17 |
| 5 | 0.428866 | 1.97995 | 0.163241 | 2.14319 | -0.00870052 | -1.06252e-15 |
| 17 | 0.342376 | 1.52862 | 0.122233 | 1.65086 | -0.0207675 | -1.77636e-15 |
| 16 | 0.334286 | 1.73579 | 0.12388 | 1.85656 | -0.00290195 | 4.21885e-15 |
| 18 | 0.331439 | 1.03613 | 0.104241 | 1.14037 | -0.0195359 | -2.66454e-15 |
| 15 | 0.316748 | 1.66548 | 0.119267 | 1.77819 | -0.00249658 | -3.21965e-15 |
| 2 | 0.293278 | 2.08213 | 0.0348613 | 2.0651 | 0.126737 | 2.07462e-14 |
| 11 | 0.27874 | 0.460744 | 0.0456223 | 0.472283 | -0.0052814 | -3.27516e-15 |
| 14 | 0.278341 | 1.61461 | 0.102378 | 1.71607 | -0.00665931 | 4.32987e-15 |
| 6 | 0.236788 | 1.27685 | 0.111045 | 1.38789 | -0.0108082 | -1.28196e-15 |
