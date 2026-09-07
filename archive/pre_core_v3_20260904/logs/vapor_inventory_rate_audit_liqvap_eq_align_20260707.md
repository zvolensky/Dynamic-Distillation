# Vapor Inventory Rate Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_liqvap_eq_align_smoke_20260707\column_profile_20260707_110130.csv`
Window: `0` to `0.2` s

## Summary
| n_stages | max_abs_relative_inventory_rate_per_s | max_abs_relative_inventory_rate_per_s_interior | max_abs_dn_dt_lbmolps | max_abs_convective_lbmolps_est | max_abs_unaccounted_lbmolps_est |
|---|---|---|---|---|---|
| 20 | 1.30136 | 1.30136 | 3.45831 | 2.02824 | 3.7008 |

## Interpretation
- The relative inventory rate is the same finite-difference family used by the dynamic smoke detector.
- Large estimated convective terms indicate startup motion driven by adjacent vapor composition/flow mismatch.
- Large unaccounted terms indicate effects outside simple vapor convection, such as phase transfer, total vapor holdup changes, or boundary coupling.

## Top Component Rates
| stage_1based | component | relative_inventory_rate_per_s | dn_dt_lbmolps | convective_lbmolps_est | unaccounted_lbmolps_est | MV_final_lbmol | V_in_lbmolph_est | V_out_lbmolph | y_in_minus_y |
|---|---|---|---|---|---|---|---|---|---|
| 3 | n_Butane | 1.30136 | -3.44951 | 0.202968 | -3.65248 | 11.8584 | 8511.47 | 8653.18 | 0.0881648 |
| 4 | n_Butane | 0.762277 | -2.78287 | 0.179983 | -2.96285 | 11.6585 | 8364.87 | 8511.47 | 0.0814443 |
| 5 | n_Butane | 0.428145 | -1.95126 | 0.138922 | -2.09018 | 11.52 | 8275.65 | 8364.87 | 0.063762 |
| 17 | n_Propane | 0.335746 | 1.49689 | -0.121677 | 1.61857 | 12.7332 | 8069.84 | 8079.08 | -0.05397 |
| 18 | n_Pentane | 0.333387 | -0.576224 | 0.0399202 | -0.616144 | 12.6993 | 8050.71 | 8069.84 | 0.0179873 |
| 16 | n_Propane | 0.325332 | 1.68606 | -0.126355 | 1.81241 | 12.7703 | 8079.08 | 8088.59 | -0.0559175 |
| 3 | n_Propane | 0.308574 | 3.45831 | -0.242487 | 3.7008 | 11.8584 | 8511.47 | 8653.18 | -0.0882305 |
| 15 | n_Propane | 0.30661 | 1.60869 | -0.120833 | 1.72953 | 11.1583 | 8088.59 | 8103.81 | -0.0530631 |
| 20 | n_Pentane | 0.302011 | 0.7273 | 0 | 0.7273 | 12.6862 | 8030.03 | 8030.03 | 0 |
| 17 | n_Pentane | 0.294398 | -0.474674 | 0.0206465 | -0.495321 | 12.7332 | 8069.84 | 8079.08 | 0.00926561 |
| 20 | n_Propane | 0.28851 | 0.687751 | 0 | 0.687751 | 12.6862 | 8030.03 | 8030.03 | 0 |
| 4 | n_Propane | 0.279224 | 2.79411 | -0.221093 | 3.01521 | 11.6585 | 8364.87 | 8511.47 | -0.0816131 |

## Top Interior Component Rates
| stage_1based | component | relative_inventory_rate_per_s | dn_dt_lbmolps | convective_lbmolps_est | unaccounted_lbmolps_est | MV_final_lbmol | V_in_lbmolph_est | V_out_lbmolph | y_in_minus_y |
|---|---|---|---|---|---|---|---|---|---|
| 3 | n_Butane | 1.30136 | -3.44951 | 0.202968 | -3.65248 | 11.8584 | 8511.47 | 8653.18 | 0.0881648 |
| 4 | n_Butane | 0.762277 | -2.78287 | 0.179983 | -2.96285 | 11.6585 | 8364.87 | 8511.47 | 0.0814443 |
| 5 | n_Butane | 0.428145 | -1.95126 | 0.138922 | -2.09018 | 11.52 | 8275.65 | 8364.87 | 0.063762 |
| 17 | n_Propane | 0.335746 | 1.49689 | -0.121677 | 1.61857 | 12.7332 | 8069.84 | 8079.08 | -0.05397 |
| 18 | n_Pentane | 0.333387 | -0.576224 | 0.0399202 | -0.616144 | 12.6993 | 8050.71 | 8069.84 | 0.0179873 |
| 16 | n_Propane | 0.325332 | 1.68606 | -0.126355 | 1.81241 | 12.7703 | 8079.08 | 8088.59 | -0.0559175 |
| 3 | n_Propane | 0.308574 | 3.45831 | -0.242487 | 3.7008 | 11.8584 | 8511.47 | 8653.18 | -0.0882305 |
| 15 | n_Propane | 0.30661 | 1.60869 | -0.120833 | 1.72953 | 11.1583 | 8088.59 | 8103.81 | -0.0530631 |
| 17 | n_Pentane | 0.294398 | -0.474674 | 0.0206465 | -0.495321 | 12.7332 | 8069.84 | 8079.08 | 0.00926561 |
| 4 | n_Propane | 0.279224 | 2.79411 | -0.221093 | 3.01521 | 11.6585 | 8364.87 | 8511.47 | -0.0816131 |
| 18 | n_Propane | 0.273919 | 1.03098 | -0.107554 | 1.13854 | 12.6993 | 8050.71 | 8069.84 | -0.0475774 |
| 14 | n_Propane | 0.269501 | 1.56041 | -0.108841 | 1.66925 | 11.1902 | 8103.81 | 8120.54 | -0.0474674 |

## Top Stage Rates
| stage_1based | max_abs_relative_inventory_rate_per_s | max_abs_dn_dt_lbmolps | max_abs_convective_lbmolps_est | max_abs_unaccounted_lbmolps_est | stage_mass_balance_resid_lbmolps | eq_phase_change_lbmolps_tray |
|---|---|---|---|---|---|---|
| 3 | 1.30136 | 3.45831 | 0.242487 | 3.7008 | 0.0235638 | 4.27653e-15 |
| 4 | 0.762277 | 2.79411 | 0.221093 | 3.01521 | -0.00322365 | 2.69012e-15 |
| 5 | 0.428145 | 1.97802 | 0.164549 | 2.14257 | -0.00952348 | -1.63498e-15 |
| 17 | 0.335746 | 1.49689 | 0.121677 | 1.61857 | -0.0233647 | -2.66454e-15 |
| 18 | 0.333387 | 1.03098 | 0.107554 | 1.13854 | -0.0229732 | -1.9984e-15 |
| 16 | 0.325332 | 1.68606 | 0.126355 | 1.81241 | -0.0219382 | 3.10862e-15 |
| 15 | 0.30661 | 1.60869 | 0.120833 | 1.72953 | -0.0224997 | 1.9984e-15 |
| 20 | 0.302011 | 1.41505 | 0 | 1.41505 | 0 | 0 |
| 14 | 0.269501 | 1.56041 | 0.108841 | 1.66925 | -0.0198724 | 6.66134e-16 |
| 11 | 0.251379 | 0.523572 | 0.036496 | 0.535021 | 0.00289433 | -3.66374e-15 |
| 6 | 0.23568 | 1.27316 | 0.112001 | 1.38516 | -0.0116041 | 3.44863e-15 |
| 13 | 0.225327 | 1.40957 | 0.093378 | 1.50295 | -0.0177024 | -6.66134e-16 |
