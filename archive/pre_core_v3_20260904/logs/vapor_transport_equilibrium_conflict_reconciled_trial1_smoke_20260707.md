# Vapor Transport / Equilibrium Conflict Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_vapor_material_reconciled_trial1_smoke_20260707\column_profile_20260707_154658.csv`
Time: `0.2` s

## Summary
| n_stages | n_components | max_abs_final_rhs_lbmolps | max_abs_required_target_delta | fraction_required_components_feasible | median_cancellation_coverage |
|---|---|---|---|---|---|
| 20 | 3 | 0.324984 | 0.0142694 | 1 | 3.25876 |

## Interpretation
- `cancellation_coverage = -equilibrium_transfer / pre_equilibrium_rhs`; `1` would cancel the pre-equilibrium vapor RHS.
- `required_y_target_to_cancel_pre_rhs` is the component target implied by zeroing the pre-equilibrium RHS at the inferred/default relaxation time.
- Large `required_target_delta` means the material transport cancellation demand is far from the logged equilibrium target.

## Top Final RHS Conflicts
| stage_1based | stage_kind | component | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | equilibrium_transfer_lbmolps | cancellation_coverage | y | y_target | required_y_target_to_cancel_pre_rhs | required_target_delta | required_target_component_feasible |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 7 | interior | n_Butane | -0.324984 | 0.0587067 | -0.383691 | 6.53573 | 0.409237 | 0.39239 | 0.40666 | 0.0142694 | 1 |
| 6 | interior | n_Butane | -0.3238 | 0.0939048 | -0.417705 | 4.44817 | 0.365939 | 0.347675 | 0.361833 | 0.0141577 | 1 |
| 8 | interior | n_Butane | -0.319698 | 0.0323023 | -0.352 | 10.8971 | 0.436898 | 0.421406 | 0.435477 | 0.014071 | 1 |
| 7 | interior | n_Propane | 0.315673 | -0.0724752 | 0.388149 | 5.35561 | 0.589371 | 0.606414 | 0.592553 | -0.0138606 | 1 |
| 5 | interior | n_Butane | -0.315449 | 0.136665 | -0.452114 | 3.30819 | 0.303675 | 0.284053 | 0.297744 | 0.0136908 | 1 |
| 8 | interior | n_Propane | 0.313045 | -0.0485604 | 0.361605 | 7.44651 | 0.560173 | 0.576089 | 0.56231 | -0.0137782 | 1 |
| 6 | interior | n_Propane | 0.310143 | -0.109324 | 0.419467 | 3.83692 | 0.633448 | 0.651789 | 0.638228 | -0.0135605 | 1 |
| 9 | interior | n_Butane | -0.307853 | 0.0167609 | -0.324614 | 19.3673 | 0.453083 | 0.438771 | 0.452344 | 0.0135729 | 1 |
| 9 | interior | n_Propane | 0.303653 | -0.0377164 | 0.34137 | 9.05097 | 0.541244 | 0.556295 | 0.542907 | -0.0133878 | 1 |
| 4 | interior | n_Butane | -0.298311 | 0.179111 | -0.477423 | 2.66551 | 0.223837 | 0.203363 | 0.216156 | 0.012793 | 1 |
| 5 | interior | n_Propane | 0.293804 | -0.15902 | 0.452823 | 2.84759 | 0.696079 | 0.715732 | 0.70298 | -0.0127514 | 1 |
| 10 | interior | n_Butane | -0.2908 | 0.0147008 | -0.305501 | 20.7812 | 0.462855 | 0.449363 | 0.462206 | 0.0128427 | 1 |

## Top Required Target Conflicts
| stage_1based | stage_kind | component | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | equilibrium_transfer_lbmolps | cancellation_coverage | y | y_target | required_y_target_to_cancel_pre_rhs | required_target_delta | required_target_component_feasible |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 7 | interior | n_Butane | -0.324984 | 0.0587067 | -0.383691 | 6.53573 | 0.409237 | 0.39239 | 0.40666 | 0.0142694 | 1 |
| 6 | interior | n_Butane | -0.3238 | 0.0939048 | -0.417705 | 4.44817 | 0.365939 | 0.347675 | 0.361833 | 0.0141577 | 1 |
| 8 | interior | n_Butane | -0.319698 | 0.0323023 | -0.352 | 10.8971 | 0.436898 | 0.421406 | 0.435477 | 0.014071 | 1 |
| 7 | interior | n_Propane | 0.315673 | -0.0724752 | 0.388149 | 5.35561 | 0.589371 | 0.606414 | 0.592553 | -0.0138606 | 1 |
| 8 | interior | n_Propane | 0.313045 | -0.0485604 | 0.361605 | 7.44651 | 0.560173 | 0.576089 | 0.56231 | -0.0137782 | 1 |
| 5 | interior | n_Butane | -0.315449 | 0.136665 | -0.452114 | 3.30819 | 0.303675 | 0.284053 | 0.297744 | 0.0136908 | 1 |
| 9 | interior | n_Butane | -0.307853 | 0.0167609 | -0.324614 | 19.3673 | 0.453083 | 0.438771 | 0.452344 | 0.0135729 | 1 |
| 6 | interior | n_Propane | 0.310143 | -0.109324 | 0.419467 | 3.83692 | 0.633448 | 0.651789 | 0.638228 | -0.0135605 | 1 |
| 9 | interior | n_Propane | 0.303653 | -0.0377164 | 0.34137 | 9.05097 | 0.541244 | 0.556295 | 0.542907 | -0.0133878 | 1 |
| 10 | interior | n_Butane | -0.2908 | 0.0147008 | -0.305501 | 20.7812 | 0.462855 | 0.449363 | 0.462206 | 0.0128427 | 1 |
| 4 | interior | n_Butane | -0.298311 | 0.179111 | -0.477423 | 2.66551 | 0.223837 | 0.203363 | 0.216156 | 0.012793 | 1 |
| 10 | interior | n_Propane | 0.289497 | -0.0412215 | 0.330719 | 8.02298 | 0.527379 | 0.541985 | 0.529199 | -0.0127851 | 1 |

## Top Interior Final RHS Conflicts
| stage_1based | stage_kind | component | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | equilibrium_transfer_lbmolps | cancellation_coverage | y | y_target | required_y_target_to_cancel_pre_rhs | required_target_delta | required_target_component_feasible |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 7 | interior | n_Butane | -0.324984 | 0.0587067 | -0.383691 | 6.53573 | 0.409237 | 0.39239 | 0.40666 | 0.0142694 | 1 |
| 6 | interior | n_Butane | -0.3238 | 0.0939048 | -0.417705 | 4.44817 | 0.365939 | 0.347675 | 0.361833 | 0.0141577 | 1 |
| 8 | interior | n_Butane | -0.319698 | 0.0323023 | -0.352 | 10.8971 | 0.436898 | 0.421406 | 0.435477 | 0.014071 | 1 |
| 7 | interior | n_Propane | 0.315673 | -0.0724752 | 0.388149 | 5.35561 | 0.589371 | 0.606414 | 0.592553 | -0.0138606 | 1 |
| 5 | interior | n_Butane | -0.315449 | 0.136665 | -0.452114 | 3.30819 | 0.303675 | 0.284053 | 0.297744 | 0.0136908 | 1 |
| 8 | interior | n_Propane | 0.313045 | -0.0485604 | 0.361605 | 7.44651 | 0.560173 | 0.576089 | 0.56231 | -0.0137782 | 1 |
| 6 | interior | n_Propane | 0.310143 | -0.109324 | 0.419467 | 3.83692 | 0.633448 | 0.651789 | 0.638228 | -0.0135605 | 1 |
| 9 | interior | n_Butane | -0.307853 | 0.0167609 | -0.324614 | 19.3673 | 0.453083 | 0.438771 | 0.452344 | 0.0135729 | 1 |
| 9 | interior | n_Propane | 0.303653 | -0.0377164 | 0.34137 | 9.05097 | 0.541244 | 0.556295 | 0.542907 | -0.0133878 | 1 |
| 4 | interior | n_Butane | -0.298311 | 0.179111 | -0.477423 | 2.66551 | 0.223837 | 0.203363 | 0.216156 | 0.012793 | 1 |
| 5 | interior | n_Propane | 0.293804 | -0.15902 | 0.452823 | 2.84759 | 0.696079 | 0.715732 | 0.70298 | -0.0127514 | 1 |
| 10 | interior | n_Butane | -0.2908 | 0.0147008 | -0.305501 | 20.7812 | 0.462855 | 0.449363 | 0.462206 | 0.0128427 | 1 |

## Top Stage Conflicts
| stage_1based | stage_kind | max_abs_required_target_delta | max_abs_final_rhs_lbmolps |
|---|---|---|---|
| 7 | interior | 0.0142694 | 0.324984 |
| 6 | interior | 0.0141577 | 0.3238 |
| 8 | interior | 0.014071 | 0.319698 |
| 5 | interior | 0.0136908 | 0.315449 |
| 9 | interior | 0.0135729 | 0.307853 |
| 4 | interior | 0.012793 | 0.298311 |
| 10 | interior | 0.0128427 | 0.2908 |
| 11 | interior | 0.0124374 | 0.281029 |
| 16 | interior | 0.0107676 | 0.274879 |
| 3 | interior | 0.0115021 | 0.272926 |
| 17 | interior | 0.0105307 | 0.268107 |
| 12 | interior | 0.0117247 | 0.263708 |
