# Vapor Transport Pulse Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\initializer_orchestrator_end_to_end_smoke2_20260708\dynamic_gate\coupled-vle-topL\column_profile_20260708_134221.csv`
Time: `1` s

## Summary
| n_stages | max_relative_rhs_per_s | max_abs_final_rhs_lbmolps | transport_driver_counts |
|---|---|---|---|
| 20 | 0.0462821 | 0.253127 | {'mixed': 44, 'net_transport': 9, 'composition_gradient': 7} |

## Interpretation
- `composition_gradient` means the vapor entering from the upstream stage has a different composition than the receiving stage.
- `flow_magnitude` means the in/out vapor rates differ enough to explain the component pulse.
- `relative_rhs_per_s` scales the live component RHS by local vapor component inventory plus the configured floor.

## Top Component Transport Pulses
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | equilibrium_transfer_lbmolps | eq_cancellation_coverage | transport_driver | V_in_lbmolph_est | V_out_lbmolph | y_upstream_minus_stage | transport_gradient_term_est_lbmolps | transport_flow_term_est_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 3 | n_Butane | 0.0462821 | 0.162303 | 0.162303 |  |  | mixed | 8443.01 | 8689.14 | 0.0754039 | 0.176843 | -0.0145397 |
| 4 | n_Butane | 0.0275794 | 0.119471 | 0.119471 |  |  | mixed | 8122.6 | 8443.01 | 0.0643134 | 0.145109 | -0.0256378 |
| 2 | n_Butane | 0.026053 | 0.20054 | 0.20054 |  |  | net_transport | 8689.14 | 7055.69 | 0.0530894 | 0.104051 | 0.072401 |
| 4 | n_Propane | 0.0226159 | -0.208826 | -0.208826 |  |  | mixed | 8122.6 | 8443.01 | -0.0644741 | -0.145471 | -0.063355 |
| 3 | n_Propane | 0.0224521 | -0.230829 | -0.230829 |  |  | mixed | 8443.01 | 8689.14 | -0.0754703 | -0.176999 | -0.0538298 |
| 5 | n_Propane | 0.0198518 | -0.166615 | -0.166615 |  |  | mixed | 7783.78 | 8122.6 | -0.0488803 | -0.105687 | -0.0609277 |
| 19 | n_Propane | 0.0198484 | 0.0634925 | 0.0634925 |  |  | mixed | 8030.03 | 7591.93 | 0.0190775 | 0.0402319 | 0.020939 |
| 15 | n_Propane | 0.0181619 | -0.0878419 | -0.0878419 |  |  | mixed | 6554.91 | 6513.24 | -0.0504295 | -0.0912387 | 0.00398062 |

## Top Interior Component Transport Pulses
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | equilibrium_transfer_lbmolps | eq_cancellation_coverage | transport_driver | V_in_lbmolph_est | V_out_lbmolph | y_upstream_minus_stage | transport_gradient_term_est_lbmolps | transport_flow_term_est_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 3 | n_Butane | 0.0462821 | 0.162303 | 0.162303 |  |  | mixed | 8443.01 | 8689.14 | 0.0754039 | 0.176843 | -0.0145397 |
| 4 | n_Butane | 0.0275794 | 0.119471 | 0.119471 |  |  | mixed | 8122.6 | 8443.01 | 0.0643134 | 0.145109 | -0.0256378 |
| 2 | n_Butane | 0.026053 | 0.20054 | 0.20054 |  |  | net_transport | 8689.14 | 7055.69 | 0.0530894 | 0.104051 | 0.072401 |
| 4 | n_Propane | 0.0226159 | -0.208826 | -0.208826 |  |  | mixed | 8122.6 | 8443.01 | -0.0644741 | -0.145471 | -0.063355 |
| 3 | n_Propane | 0.0224521 | -0.230829 | -0.230829 |  |  | mixed | 8443.01 | 8689.14 | -0.0754703 | -0.176999 | -0.0538298 |
| 5 | n_Propane | 0.0198518 | -0.166615 | -0.166615 |  |  | mixed | 7783.78 | 8122.6 | -0.0488803 | -0.105687 | -0.0609277 |
| 19 | n_Propane | 0.0198484 | 0.0634925 | 0.0634925 |  |  | mixed | 8030.03 | 7591.93 | 0.0190775 | 0.0402319 | 0.020939 |
| 15 | n_Propane | 0.0181619 | -0.0878419 | -0.0878419 |  |  | mixed | 6554.91 | 6513.24 | -0.0504295 | -0.0912387 | 0.00398062 |

## Top Stage Transport Pulses
| stage_1based | max_abs_relative_rhs_per_s | max_abs_final_rhs_lbmolps | dominant_transport_driver | V_in_lbmolph_est | V_out_lbmolph | V_in_minus_out_lbmolph_est | eq_component_transfer_guard_scale_tray | eq_component_transfer_guard_limit_lbmolps_tray |
|---|---|---|---|---|---|---|---|---|
| 3 | 0.0462821 | 0.230829 | mixed | 8443.01 | 8689.14 | -246.139 |  |  |
| 4 | 0.0275794 | 0.208826 | mixed | 8122.6 | 8443.01 | -320.407 |  |  |
| 2 | 0.026053 | 0.253127 | net_transport | 8689.14 | 7055.69 | 1633.45 |  |  |
| 5 | 0.0198518 | 0.166615 | mixed | 7783.78 | 8122.6 | -338.82 |  |  |
| 19 | 0.0198484 | 0.0746927 | mixed | 8030.03 | 7591.93 | 438.09 |  |  |
| 15 | 0.0181619 | 0.0885668 | mixed | 6554.91 | 6513.24 | 41.6762 |  |  |
| 14 | 0.01629 | 0.0878098 | mixed | 6513.24 | 6507.7 | 5.54305 |  |  |
| 16 | 0.0160087 | 0.136009 | mixed | 6840.97 | 6554.91 | 286.059 |  |  |
