# Vapor Inventory Rate Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_interior_liq_vapor_eq_align_smoke_loggingfix_20260707\column_profile_20260707_112554.csv`
Window: `0` to `0.2` s

## Summary
| n_stages | max_abs_relative_inventory_rate_per_s | max_abs_relative_inventory_rate_per_s_interior | max_abs_dn_dt_lbmolps | max_abs_convective_lbmolps_est | max_abs_unaccounted_lbmolps_est |
|---|---|---|---|---|---|
| 20 | 0.710818 | 0.0782449 | 1.71178 | 2.02824 | 2.02824 |

## Interpretation
- The relative inventory rate is the same finite-difference family used by the dynamic smoke detector.
- Large estimated convective terms indicate startup motion driven by adjacent vapor composition/flow mismatch.
- Large unaccounted terms indicate effects outside simple vapor convection, such as phase transfer, total vapor holdup changes, or boundary coupling.

## Top Component Rates
| stage_1based | component | relative_inventory_rate_per_s | dn_dt_lbmolps | convective_lbmolps_est | unaccounted_lbmolps_est | MV_final_lbmol | V_in_lbmolph_est | V_out_lbmolph | y_in_minus_y |
|---|---|---|---|---|---|---|---|---|---|
| 20 | n_Pentane | 0.710818 | 1.71178 | 0 | 1.71178 | 12.6862 | 8030.03 | 8030.03 | 0 |
| 20 | n_Butane | 0.15047 | -1.63925 | 0 | -1.63925 | 12.6862 | 8030.03 | 8030.03 | 0 |
| 3 | n_Butane | 0.0782449 | 0.207403 | 0.202968 | 0.00443489 | 11.8584 | 8511.47 | 8653.18 | 0.0881648 |
| 4 | n_Butane | 0.052223 | 0.190652 | 0.179983 | 0.0106688 | 11.6585 | 8364.87 | 8511.47 | 0.0814443 |
| 19 | n_Propane | 0.0464843 | -0.146543 | -0.136993 | -0.00955039 | 12.6576 | 8030.03 | 8050.71 | -0.0609782 |
| 2 | n_Butane | 0.0432769 | -0.315874 | -0.0296767 | -0.286197 | 41.3718 | 8653.18 | 8613.15 | -0.0130508 |
| 19 | n_Pentane | 0.0404907 | 0.0791057 | 0.0791039 | 1.78566e-06 | 12.6576 | 8030.03 | 8050.71 | 0.0356577 |
| 5 | n_Butane | 0.0339265 | 0.154619 | 0.138922 | 0.0156967 | 11.52 | 8275.65 | 8364.87 | 0.063762 |
| 20 | n_Propane | 0.0304281 | -0.0725345 | 0 | -0.0725345 | 12.6862 | 8030.03 | 8030.03 | 0 |
| 18 | n_Propane | 0.0269132 | -0.101296 | -0.107554 | 0.00625772 | 12.6993 | 8050.71 | 8069.84 | -0.0475774 |
| 17 | n_Propane | 0.024056 | -0.107251 | -0.121677 | 0.0144264 | 12.7332 | 8069.84 | 8079.08 | -0.05397 |
| 18 | n_Pentane | 0.0233177 | 0.0403022 | 0.0399202 | 0.000381979 | 12.6993 | 8050.71 | 8069.84 | 0.0179873 |

## Top Interior Component Rates
| stage_1based | component | relative_inventory_rate_per_s | dn_dt_lbmolps | convective_lbmolps_est | unaccounted_lbmolps_est | MV_final_lbmol | V_in_lbmolph_est | V_out_lbmolph | y_in_minus_y |
|---|---|---|---|---|---|---|---|---|---|
| 3 | n_Butane | 0.0782449 | 0.207403 | 0.202968 | 0.00443489 | 11.8584 | 8511.47 | 8653.18 | 0.0881648 |
| 4 | n_Butane | 0.052223 | 0.190652 | 0.179983 | 0.0106688 | 11.6585 | 8364.87 | 8511.47 | 0.0814443 |
| 19 | n_Propane | 0.0464843 | -0.146543 | -0.136993 | -0.00955039 | 12.6576 | 8030.03 | 8050.71 | -0.0609782 |
| 2 | n_Butane | 0.0432769 | -0.315874 | -0.0296767 | -0.286197 | 41.3718 | 8653.18 | 8613.15 | -0.0130508 |
| 19 | n_Pentane | 0.0404907 | 0.0791057 | 0.0791039 | 1.78566e-06 | 12.6576 | 8030.03 | 8050.71 | 0.0356577 |
| 5 | n_Butane | 0.0339265 | 0.154619 | 0.138922 | 0.0156967 | 11.52 | 8275.65 | 8364.87 | 0.063762 |
| 18 | n_Propane | 0.0269132 | -0.101296 | -0.107554 | 0.00625772 | 12.6993 | 8050.71 | 8069.84 | -0.0475774 |
| 17 | n_Propane | 0.024056 | -0.107251 | -0.121677 | 0.0144264 | 12.7332 | 8069.84 | 8079.08 | -0.05397 |
| 18 | n_Pentane | 0.0233177 | 0.0403022 | 0.0399202 | 0.000381979 | 12.6993 | 8050.71 | 8069.84 | 0.0179873 |
| 11 | n_Pentane | 0.0228269 | 0.0266921 | 0.036496 | -0.00980392 | 11.2986 | 8088.19 | 8125.2 | 0.0163127 |
| 6 | n_Butane | 0.0218628 | 0.115007 | 0.096207 | 0.0188003 | 11.4352 | 8224.94 | 8275.65 | 0.0444065 |
| 16 | n_Propane | 0.0192706 | -0.0998712 | -0.126355 | 0.0264834 | 12.7703 | 8079.08 | 8088.59 | -0.0559175 |

## Top Stage Rates
| stage_1based | max_abs_relative_inventory_rate_per_s | max_abs_dn_dt_lbmolps | max_abs_convective_lbmolps_est | max_abs_unaccounted_lbmolps_est | stage_mass_balance_resid_lbmolps | eq_phase_change_lbmolps_tray |
|---|---|---|---|---|---|---|
| 20 | 0.710818 | 1.71178 | 0 | 1.71178 | 0 | 0 |
| 3 | 0.0782449 | 0.207403 | 0.242487 | 0.0437012 | 0.0235638 | 4.27653e-15 |
| 4 | 0.052223 | 0.190652 | 0.221093 | 0.0420787 | -0.00322365 | 2.69012e-15 |
| 19 | 0.0464843 | 0.146543 | 0.136993 | 0.0198653 | -0.00970743 | 6.66134e-16 |
| 2 | 0.0432769 | 0.428484 | 0.0407694 | 0.469254 | 0.127464 | 9.86841e-16 |
| 5 | 0.0339265 | 0.154619 | 0.164549 | 0.0388527 | -0.00952348 | -1.63498e-15 |
| 18 | 0.0269132 | 0.101296 | 0.107554 | 0.00625772 | -0.0229732 | -1.9984e-15 |
| 17 | 0.024056 | 0.107251 | 0.121677 | 0.0144264 | -0.0233647 | -2.66454e-15 |
| 11 | 0.0228269 | 0.0266921 | 0.036496 | 0.0578057 | 0.00289433 | -3.66374e-15 |
| 6 | 0.0218628 | 0.115007 | 0.112001 | 0.0357633 | -0.0116041 | 3.44863e-15 |
| 16 | 0.0192706 | 0.107686 | 0.126355 | 0.0264834 | -0.0219382 | 3.10862e-15 |
| 15 | 0.0157413 | 0.117782 | 0.120833 | 0.0419227 | -0.0224997 | 1.9984e-15 |
