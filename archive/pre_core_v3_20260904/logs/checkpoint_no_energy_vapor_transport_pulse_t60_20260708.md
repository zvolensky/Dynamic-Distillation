# Vapor Transport Pulse Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\checkpoint_no_energy_reload_60s_20260708\column_profile_20260708_140811.csv`
Time: `60` s

## Summary
| n_stages | max_relative_rhs_per_s | max_abs_final_rhs_lbmolps | transport_driver_counts |
|---|---|---|---|
| 20 | 0.00178286 | 0.0278355 | {'mixed': 54, 'net_transport': 6} |

## Interpretation
- `composition_gradient` means the vapor entering from the upstream stage has a different composition than the receiving stage.
- `flow_magnitude` means the in/out vapor rates differ enough to explain the component pulse.
- `relative_rhs_per_s` scales the live component RHS by local vapor component inventory plus the configured floor.

## Top Component Transport Pulses
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | equilibrium_transfer_lbmolps | eq_cancellation_coverage | transport_driver | V_in_lbmolph_est | V_out_lbmolph | y_upstream_minus_stage | transport_gradient_term_est_lbmolps | transport_flow_term_est_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 3 | n_Propane | 0.00178286 | 0.0253025 | 0.0253025 |  |  | mixed | 5466.74 | 5361.87 | 0.00276038 | 0.00411132 | 0.0140267 |
| 4 | n_Propane | 0.00176806 | 0.024797 | 0.024797 |  |  | mixed | 5540.3 | 5466.74 | 0.00255135 | 0.00387432 | 0.00989597 |
| 5 | n_Propane | 0.00175723 | 0.0244943 | 0.0244943 |  |  | mixed | 5606.7 | 5540.3 | 0.00234206 | 0.00360437 | 0.00897862 |
| 6 | n_Propane | 0.00174822 | 0.0242716 | 0.0242716 |  |  | mixed | 5643.53 | 5606.7 | 0.00214437 | 0.00333968 | 0.00500371 |
| 7 | n_Propane | 0.00173345 | 0.0240377 | 0.0240377 |  |  | mixed | 5663.87 | 5643.53 | 0.00196693 | 0.00308345 | 0.00277642 |
| 8 | n_Propane | 0.00171876 | 0.0238222 | 0.0238222 |  |  | mixed | 5666.24 | 5663.87 | 0.00181963 | 0.00286281 | 0.000324611 |
| 10 | n_Propane | 0.00168854 | 0.0234486 | 0.0234486 |  |  | mixed | 5712.29 | 5700.06 | 0.00156302 | 0.0024748 | 0.00168799 |
| 9 | n_Propane | 0.00168302 | 0.0234117 | 0.0234117 |  |  | mixed | 5700.06 | 5666.24 | 0.00168963 | 0.0026594 | 0.00465156 |
| 11 | n_Propane | 0.00167888 | 0.0232799 | 0.0232799 |  |  | mixed | 5709.54 | 5712.29 | 0.00143682 | 0.00227877 | -0.000380922 |
| 13 | n_Propane | 0.00163922 | 0.0230973 | 0.0230973 |  |  | mixed | 6087.19 | 5977.08 | 0.00111322 | 0.00184828 | 0.0153248 |
| 12 | n_Propane | 0.00163532 | 0.0233694 | 0.0233694 |  |  | mixed | 5977.08 | 5709.54 | 0.00128354 | 0.00203568 | 0.0371426 |
| 14 | n_Propane | 0.00162807 | 0.0229548 | 0.0229548 |  |  | mixed | 6220.75 | 6087.19 | 0.000983866 | 0.0016636 | 0.0186313 |

## Top Interior Component Transport Pulses
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | equilibrium_transfer_lbmolps | eq_cancellation_coverage | transport_driver | V_in_lbmolph_est | V_out_lbmolph | y_upstream_minus_stage | transport_gradient_term_est_lbmolps | transport_flow_term_est_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 3 | n_Propane | 0.00178286 | 0.0253025 | 0.0253025 |  |  | mixed | 5466.74 | 5361.87 | 0.00276038 | 0.00411132 | 0.0140267 |
| 4 | n_Propane | 0.00176806 | 0.024797 | 0.024797 |  |  | mixed | 5540.3 | 5466.74 | 0.00255135 | 0.00387432 | 0.00989597 |
| 5 | n_Propane | 0.00175723 | 0.0244943 | 0.0244943 |  |  | mixed | 5606.7 | 5540.3 | 0.00234206 | 0.00360437 | 0.00897862 |
| 6 | n_Propane | 0.00174822 | 0.0242716 | 0.0242716 |  |  | mixed | 5643.53 | 5606.7 | 0.00214437 | 0.00333968 | 0.00500371 |
| 7 | n_Propane | 0.00173345 | 0.0240377 | 0.0240377 |  |  | mixed | 5663.87 | 5643.53 | 0.00196693 | 0.00308345 | 0.00277642 |
| 8 | n_Propane | 0.00171876 | 0.0238222 | 0.0238222 |  |  | mixed | 5666.24 | 5663.87 | 0.00181963 | 0.00286281 | 0.000324611 |
| 10 | n_Propane | 0.00168854 | 0.0234486 | 0.0234486 |  |  | mixed | 5712.29 | 5700.06 | 0.00156302 | 0.0024748 | 0.00168799 |
| 9 | n_Propane | 0.00168302 | 0.0234117 | 0.0234117 |  |  | mixed | 5700.06 | 5666.24 | 0.00168963 | 0.0026594 | 0.00465156 |
| 11 | n_Propane | 0.00167888 | 0.0232799 | 0.0232799 |  |  | mixed | 5709.54 | 5712.29 | 0.00143682 | 0.00227877 | -0.000380922 |
| 13 | n_Propane | 0.00163922 | 0.0230973 | 0.0230973 |  |  | mixed | 6087.19 | 5977.08 | 0.00111322 | 0.00184828 | 0.0153248 |
| 12 | n_Propane | 0.00163532 | 0.0233694 | 0.0233694 |  |  | mixed | 5977.08 | 5709.54 | 0.00128354 | 0.00203568 | 0.0371426 |
| 14 | n_Propane | 0.00162807 | 0.0229548 | 0.0229548 |  |  | mixed | 6220.75 | 6087.19 | 0.000983866 | 0.0016636 | 0.0186313 |

## Top Stage Transport Pulses
| stage_1based | max_abs_relative_rhs_per_s | max_abs_final_rhs_lbmolps | dominant_transport_driver | V_in_lbmolph_est | V_out_lbmolph | V_in_minus_out_lbmolph_est | eq_component_transfer_guard_scale_tray | eq_component_transfer_guard_limit_lbmolps_tray |
|---|---|---|---|---|---|---|---|---|
| 3 | 0.00178286 | 0.0253025 | mixed | 5466.74 | 5361.87 | 104.87 |  |  |
| 4 | 0.00176806 | 0.024797 | mixed | 5540.3 | 5466.74 | 73.5653 |  |  |
| 5 | 0.00175723 | 0.0244943 | mixed | 5606.7 | 5540.3 | 66.3961 |  |  |
| 6 | 0.00174822 | 0.0242716 | mixed | 5643.53 | 5606.7 | 36.8249 |  |  |
| 7 | 0.00173345 | 0.0240377 | mixed | 5663.87 | 5643.53 | 20.3439 |  |  |
| 8 | 0.00171876 | 0.0238222 | mixed | 5666.24 | 5663.87 | 2.36906 |  |  |
| 10 | 0.00168854 | 0.0234486 | mixed | 5712.29 | 5700.06 | 12.2322 |  |  |
| 9 | 0.00168302 | 0.0234117 | mixed | 5700.06 | 5666.24 | 33.8231 |  |  |
| 11 | 0.00167888 | 0.0232799 | mixed | 5709.54 | 5712.29 | -2.75174 |  |  |
| 13 | 0.00163922 | 0.0230973 | mixed | 6087.19 | 5977.08 | 110.103 |  |  |
| 12 | 0.00163532 | 0.0233694 | mixed | 5977.08 | 5709.54 | 267.542 |  |  |
| 14 | 0.00162807 | 0.0229548 | mixed | 6220.75 | 6087.19 | 133.563 |  |  |
