# Vapor RHS Material Terms Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\initializer_orchestrator_end_to_end_smoke2_20260708\dynamic_gate\coupled-vle-topL\column_profile_20260708_134221.csv`
Time: `1` s

## Summary
| n_stages | max_relative_rhs_per_s | max_relative_rhs_per_s_interior | max_abs_final_rhs_lbmolps |
|---|---|---|---|
| 20 | 0.0462821 | 0.0462821 | 0.253127 |

## Interpretation
- `final_rhs` is the live RHS contribution to explicit tray vapor component inventory.
- `pre_equilibrium_rhs` is transport/feed/terminal/holdup behavior before equilibrium transfer.
- Dominant terms identify whether the motion is transport, feed, terminal handling, holdup relaxation, or equilibrium transfer.

## Top Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 3 | n_Butane | 0.0462821 | 0.162303 | 0.162303 | transport_in | 0.67558 | 0.67558 | -0.513277 |  | 0 |
| 4 | n_Butane | 0.0275794 | 0.119471 | 0.119471 | transport_in | 0.795051 | 0.795051 | -0.67558 |  | 0 |
| 2 | n_Butane | 0.026053 | 0.20054 | 0.20054 | transport_in | 0.513277 | 0.513277 | -0.312736 |  | 0 |
| 4 | n_Propane | 0.0226159 | -0.208826 | -0.208826 | transport_out | -1.66946 | 1.46063 | -1.66946 |  | 0 |
| 3 | n_Propane | 0.0224521 | -0.230829 | -0.230829 | transport_out | -1.90029 | 1.66946 | -1.90029 |  | 0 |
| 5 | n_Propane | 0.0198518 | -0.166615 | -0.166615 | transport_out | -1.46063 | 1.29402 | -1.46063 |  | 0 |
| 19 | n_Propane | 0.0198484 | 0.0634925 | 0.0634925 | transport_in | 0.426358 | 0.426358 | -0.362865 |  | 0 |
| 15 | n_Propane | 0.0181619 | -0.0878419 | -0.0878419 | transport_out | -0.622099 | 0.534257 | -0.622099 |  | 0 |

## Top Interior Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 3 | n_Butane | 0.0462821 | 0.162303 | 0.162303 | transport_in | 0.67558 | 0.67558 | -0.513277 |  | 0 |
| 4 | n_Butane | 0.0275794 | 0.119471 | 0.119471 | transport_in | 0.795051 | 0.795051 | -0.67558 |  | 0 |
| 2 | n_Butane | 0.026053 | 0.20054 | 0.20054 | transport_in | 0.513277 | 0.513277 | -0.312736 |  | 0 |
| 4 | n_Propane | 0.0226159 | -0.208826 | -0.208826 | transport_out | -1.66946 | 1.46063 | -1.66946 |  | 0 |
| 3 | n_Propane | 0.0224521 | -0.230829 | -0.230829 | transport_out | -1.90029 | 1.66946 | -1.90029 |  | 0 |
| 5 | n_Propane | 0.0198518 | -0.166615 | -0.166615 | transport_out | -1.46063 | 1.29402 | -1.46063 |  | 0 |
| 19 | n_Propane | 0.0198484 | 0.0634925 | 0.0634925 | transport_in | 0.426358 | 0.426358 | -0.362865 |  | 0 |
| 15 | n_Propane | 0.0181619 | -0.0878419 | -0.0878419 | transport_out | -0.622099 | 0.534257 | -0.622099 |  | 0 |

## Top Stage Terms
| stage_1based | max_abs_final_rhs_lbmolps | dominant_stage_term | dominant_stage_term_abs_lbmolps |
|---|---|---|---|
| 2 | 0.253127 | transport_in | 1.90029 |
| 3 | 0.230829 | transport_out | 1.90029 |
| 4 | 0.208826 | transport_out | 1.66946 |
| 5 | 0.166615 | transport_out | 1.46063 |
| 16 | 0.136009 | transport_in | 1.33351 |
| 17 | 0.134857 | transport_in | 1.46837 |
| 6 | 0.124361 | transport_out | 1.29402 |
| 18 | 0.114859 | transport_in | 1.58323 |
