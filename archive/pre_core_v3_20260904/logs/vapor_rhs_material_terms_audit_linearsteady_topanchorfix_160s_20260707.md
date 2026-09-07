# Vapor RHS Material Terms Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_liq_eq_vap_linearsteady_300s_topanchorfix_20260707\column_profile_20260707_203741.csv`
Time: `160` s

## Summary
| n_stages | max_relative_rhs_per_s | max_relative_rhs_per_s_interior | max_abs_final_rhs_lbmolps |
|---|---|---|---|
| 20 | 0.244222 | 0.244222 | 1.09035 |

## Interpretation
- `final_rhs` is the live RHS contribution to explicit tray vapor component inventory.
- `pre_equilibrium_rhs` is transport/feed/terminal/holdup behavior before equilibrium transfer.
- Dominant terms identify whether the motion is transport, feed, terminal handling, holdup relaxation, or equilibrium transfer.

## Top Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 12 | n_Propane | 0.244222 | -1.09035 | -0.0957952 | transport_out | -1.10282 | 0.657309 | -1.10282 | -0.994557 | 0 |
| 19 | n_Propane | 0.235034 | -0.490646 | -0.0164375 | equilibrium_transfer | -0.474209 | 0.196649 | -0.216452 | -0.474209 | 0 |
| 12 | n_Pentane | 0.189329 | 0.326549 | 0.0626582 | equilibrium_transfer | 0.263891 | 0.17915 | -0.230702 | 0.263891 | 0 |
| 19 | n_Pentane | 0.188765 | 0.403935 | -0.0121025 | equilibrium_transfer | 0.416037 | 0.211235 | -0.226865 | 0.416037 | 0 |
| 12 | n_Butane | 0.135179 | 0.90496 | 0.174294 | transport_out | -1.81262 | 1.4045 | -1.81262 | 0.730666 | 0 |
| 3 | n_Butane | 0.0846592 | -0.218491 | 0.253368 | transport_in | 0.781759 | 0.781759 | -0.533736 | -0.471858 | 0 |
| 11 | n_Pentane | 0.0498548 | 0.0614097 | 0.154737 | transport_in | 0.230702 | 0.230702 | -0.0760186 | -0.0933277 | 0 |
| 18 | n_Pentane | 0.0372037 | 0.0591997 | 0.110746 | transport_in | 0.226865 | 0.226865 | -0.115234 | -0.051546 | 0 |
| 11 | n_Propane | 0.0341469 | -0.199049 | -0.479988 | transport_out | -1.58394 | 1.10282 | -1.58394 | 0.280939 | 0 |
| 3 | n_Propane | 0.0216354 | 0.201941 | -0.270589 | transport_out | -2.81376 | 2.515 | -2.81376 | 0.47253 | 0 |
| 18 | n_Propane | 0.0215822 | -0.0703711 | -0.227535 | transport_out | -0.440604 | 0.216452 | -0.440604 | 0.157164 | 0 |
| 11 | n_Butane | 0.0211767 | 0.118513 | 0.306124 | transport_in | 1.81262 | 1.81262 | -1.50757 | -0.187611 | 0 |

## Top Interior Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 12 | n_Propane | 0.244222 | -1.09035 | -0.0957952 | transport_out | -1.10282 | 0.657309 | -1.10282 | -0.994557 | 0 |
| 19 | n_Propane | 0.235034 | -0.490646 | -0.0164375 | equilibrium_transfer | -0.474209 | 0.196649 | -0.216452 | -0.474209 | 0 |
| 12 | n_Pentane | 0.189329 | 0.326549 | 0.0626582 | equilibrium_transfer | 0.263891 | 0.17915 | -0.230702 | 0.263891 | 0 |
| 19 | n_Pentane | 0.188765 | 0.403935 | -0.0121025 | equilibrium_transfer | 0.416037 | 0.211235 | -0.226865 | 0.416037 | 0 |
| 12 | n_Butane | 0.135179 | 0.90496 | 0.174294 | transport_out | -1.81262 | 1.4045 | -1.81262 | 0.730666 | 0 |
| 3 | n_Butane | 0.0846592 | -0.218491 | 0.253368 | transport_in | 0.781759 | 0.781759 | -0.533736 | -0.471858 | 0 |
| 11 | n_Pentane | 0.0498548 | 0.0614097 | 0.154737 | transport_in | 0.230702 | 0.230702 | -0.0760186 | -0.0933277 | 0 |
| 18 | n_Pentane | 0.0372037 | 0.0591997 | 0.110746 | transport_in | 0.226865 | 0.226865 | -0.115234 | -0.051546 | 0 |
| 11 | n_Propane | 0.0341469 | -0.199049 | -0.479988 | transport_out | -1.58394 | 1.10282 | -1.58394 | 0.280939 | 0 |
| 3 | n_Propane | 0.0216354 | 0.201941 | -0.270589 | transport_out | -2.81376 | 2.515 | -2.81376 | 0.47253 | 0 |
| 18 | n_Propane | 0.0215822 | -0.0703711 | -0.227535 | transport_out | -0.440604 | 0.216452 | -0.440604 | 0.157164 | 0 |
| 11 | n_Butane | 0.0211767 | 0.118513 | 0.306124 | transport_in | 1.81262 | 1.81262 | -1.50757 | -0.187611 | 0 |

## Top Stage Terms
| stage_1based | max_abs_final_rhs_lbmolps | dominant_stage_term | dominant_stage_term_abs_lbmolps |
|---|---|---|---|
| 12 | 1.09035 | transport_out | 1.81262 |
| 19 | 0.490646 | transport_in | 1.82268 |
| 3 | 0.218491 | transport_out | 2.81376 |
| 11 | 0.199049 | transport_in | 1.81262 |
| 2 | 0.0954702 | transport_in | 2.81376 |
| 18 | 0.0703711 | transport_in | 1.79711 |
| 10 | 0.0414809 | transport_out | 1.65389 |
| 14 | 0.031511 | transport_in | 1.29923 |
| 9 | 0.0199555 | transport_out | 1.70026 |
| 13 | 0.0171958 | transport_out | 1.4045 |
| 4 | 0.0157449 | transport_out | 2.515 |
| 5 | 0.0154344 | transport_out | 2.21824 |
