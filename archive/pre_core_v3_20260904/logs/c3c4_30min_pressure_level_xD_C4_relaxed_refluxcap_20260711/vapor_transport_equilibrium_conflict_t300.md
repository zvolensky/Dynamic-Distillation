# Vapor Transport / Equilibrium Conflict Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_30min_pressure_level_xD_C4_relaxed_refluxcap_20260711\column_profile_20260711_083447.csv`
Time: `300` s

## Summary
| n_stages | n_components | max_abs_final_rhs_lbmolps | max_abs_required_target_delta | fraction_required_components_feasible | median_cancellation_coverage |
|---|---|---|---|---|---|
| 20 | 3 | 0.0153988 | 0.374006 | 1 | -0 |

## Interpretation
- `cancellation_coverage = -equilibrium_transfer / pre_equilibrium_rhs`; `1` would cancel the pre-equilibrium vapor RHS.
- `required_y_target_to_cancel_pre_rhs` is the component target implied by zeroing the pre-equilibrium RHS at the inferred/default relaxation time.
- Large `required_target_delta` means the material transport cancellation demand is far from the logged equilibrium target.

## Top Final RHS Conflicts
| stage_1based | stage_kind | component | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | equilibrium_transfer_lbmolps | cancellation_coverage | y | y_target | required_y_target_to_cancel_pre_rhs | required_target_delta | required_target_component_feasible |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2 | interior | n_Butane | 0.0153988 | 0.264663 | -0.249264 | 0.941817 | 0.337519 | 0.193571 | 0.184678 | -0.00889267 | 1 |
| 16 | interior | n_Propane | 0.0135941 | 0.0135941 | -0 | 0 | 0.468027 | 0.425636 | 0.467767 | 0.0421311 | 1 |
| 19 | interior | n_Propane | 0.0133679 | 0.0133679 | -0 | 0 | 0.471359 | 0.417286 | 0.471102 | 0.0538158 | 1 |
| 18 | interior | n_Propane | 0.0132393 | 0.0132393 | -0 | 0 | 0.470267 | 0.41896 | 0.470015 | 0.0510549 | 1 |
| 17 | interior | n_Propane | 0.013062 | 0.013062 | -0 | 0 | 0.469153 | 0.425027 | 0.468905 | 0.0438778 | 1 |
| 15 | interior | n_Propane | 0.0126765 | 0.0126765 | -0 | 0 | 0.466975 | 0.427569 | 0.466714 | 0.0391457 | 1 |
| 14 | interior | n_Propane | 0.0125715 | 0.0125715 | -0 | 0 | 0.465934 | 0.457095 | 0.465676 | 0.00858121 | 1 |
| 13 | interior | n_Propane | 0.0125208 | 0.0125208 | 0 | -0 | 0.464907 | 0.486303 | 0.464649 | -0.0216537 | 1 |
| 7 | interior | n_Propane | 0.0124962 | 0.0124962 | 0 | -0 | 0.458912 | 0.619894 | 0.458653 | -0.161242 | 1 |
| 12 | interior | n_Propane | 0.0123444 | 0.0123444 | 0 | -0 | 0.463882 | 0.511679 | 0.463629 | -0.0480493 | 1 |
| 10 | interior | n_Propane | 0.0123189 | 0.0123189 | 0 | -0 | 0.461873 | 0.556775 | 0.461616 | -0.0951585 | 1 |
| 11 | interior | n_Propane | 0.0122584 | 0.0122584 | 0 | -0 | 0.46287 | 0.538164 | 0.462615 | -0.0755495 | 1 |
| 9 | interior | n_Propane | 0.011864 | 0.011864 | 0 | -0 | 0.460884 | 0.573543 | 0.460637 | -0.112906 | 1 |
| 4 | interior | n_Propane | 0.0117742 | 0.0117742 | 0 | -0 | 0.455904 | 0.739154 | 0.455668 | -0.283486 | 1 |
| 3 | interior | n_Propane | 0.0116433 | 0.0116433 | 0 | -0 | 0.454837 | 0.747131 | 0.454606 | -0.292525 | 1 |
| 8 | interior | n_Propane | 0.0114613 | 0.0114613 | 0 | -0 | 0.459898 | 0.593138 | 0.45966 | -0.133478 | 1 |
| 5 | interior | n_Propane | 0.0109185 | 0.0109185 | 0 | -0 | 0.45693 | 0.715665 | 0.456704 | -0.258962 | 1 |
| 6 | interior | n_Propane | 0.0106728 | 0.0106728 | 0 | -0 | 0.457923 | 0.659181 | 0.457702 | -0.201479 | 1 |
| 7 | interior | n_Butane | 0.00956019 | 0.00956019 | -0 | 0 | 0.480867 | 0.35185 | 0.480669 | 0.128818 | 1 |
| 16 | interior | n_Butane | 0.00949712 | 0.00949712 | 0 | -0 | 0.472625 | 0.496037 | 0.472444 | -0.0235931 | 1 |

## Top Required Target Conflicts
| stage_1based | stage_kind | component | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | equilibrium_transfer_lbmolps | cancellation_coverage | y | y_target | required_y_target_to_cancel_pre_rhs | required_target_delta | required_target_component_feasible |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 20 | bottom | n_Propane | 0 | 0 | 0 |  | 0.472428 | 0.098422 | 0.472428 | 0.374006 | 1 |
| 20 | bottom | n_Butane | 0 | 0 | 0 |  | 0.468657 | 0.802308 | 0.468657 | -0.333651 | 1 |
| 3 | interior | n_Propane | 0.0116433 | 0.0116433 | 0 | -0 | 0.454837 | 0.747131 | 0.454606 | -0.292525 | 1 |
| 4 | interior | n_Propane | 0.0117742 | 0.0117742 | 0 | -0 | 0.455904 | 0.739154 | 0.455668 | -0.283486 | 1 |
| 5 | interior | n_Propane | 0.0109185 | 0.0109185 | 0 | -0 | 0.45693 | 0.715665 | 0.456704 | -0.258962 | 1 |
| 3 | interior | n_Butane | 0.00864663 | 0.00864663 | -0 | 0 | 0.484535 | 0.238665 | 0.484364 | 0.245698 | 1 |
| 4 | interior | n_Butane | 0.00878258 | 0.00878258 | -0 | 0 | 0.483575 | 0.245887 | 0.483399 | 0.237512 | 1 |
| 5 | interior | n_Butane | 0.00796724 | 0.00796724 | -0 | 0 | 0.482652 | 0.267194 | 0.482487 | 0.215293 | 1 |
| 6 | interior | n_Propane | 0.0106728 | 0.0106728 | 0 | -0 | 0.457923 | 0.659181 | 0.457702 | -0.201479 | 1 |
| 6 | interior | n_Butane | 0.00768495 | 0.00768495 | -0 | 0 | 0.481758 | 0.317741 | 0.481599 | 0.163858 | 1 |
| 7 | interior | n_Propane | 0.0124962 | 0.0124962 | 0 | -0 | 0.458912 | 0.619894 | 0.458653 | -0.161242 | 1 |
| 8 | interior | n_Propane | 0.0114613 | 0.0114613 | 0 | -0 | 0.459898 | 0.593138 | 0.45966 | -0.133478 | 1 |
| 7 | interior | n_Butane | 0.00956019 | 0.00956019 | -0 | 0 | 0.480867 | 0.35185 | 0.480669 | 0.128818 | 1 |
| 9 | interior | n_Propane | 0.011864 | 0.011864 | 0 | -0 | 0.460884 | 0.573543 | 0.460637 | -0.112906 | 1 |
| 8 | interior | n_Butane | 0.00843592 | 0.00843592 | -0 | 0 | 0.479977 | 0.374442 | 0.479802 | 0.10536 | 1 |
| 10 | interior | n_Propane | 0.0123189 | 0.0123189 | 0 | -0 | 0.461873 | 0.556775 | 0.461616 | -0.0951585 | 1 |
| 9 | interior | n_Butane | 0.00880468 | 0.00880468 | -0 | 0 | 0.479087 | 0.390689 | 0.478904 | 0.0882147 | 1 |
| 11 | interior | n_Propane | 0.0122584 | 0.0122584 | 0 | -0 | 0.46287 | 0.538164 | 0.462615 | -0.0755495 | 1 |
| 10 | interior | n_Butane | 0.00921215 | 0.00921215 | -0 | 0 | 0.478193 | 0.404218 | 0.478001 | 0.0737828 | 1 |
| 11 | interior | n_Butane | 0.00907592 | 0.00907592 | -0 | 0 | 0.47729 | 0.418713 | 0.477101 | 0.0583883 | 1 |

## Top Interior Final RHS Conflicts
| stage_1based | stage_kind | component | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | equilibrium_transfer_lbmolps | cancellation_coverage | y | y_target | required_y_target_to_cancel_pre_rhs | required_target_delta | required_target_component_feasible |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2 | interior | n_Butane | 0.0153988 | 0.264663 | -0.249264 | 0.941817 | 0.337519 | 0.193571 | 0.184678 | -0.00889267 | 1 |
| 16 | interior | n_Propane | 0.0135941 | 0.0135941 | -0 | 0 | 0.468027 | 0.425636 | 0.467767 | 0.0421311 | 1 |
| 19 | interior | n_Propane | 0.0133679 | 0.0133679 | -0 | 0 | 0.471359 | 0.417286 | 0.471102 | 0.0538158 | 1 |
| 18 | interior | n_Propane | 0.0132393 | 0.0132393 | -0 | 0 | 0.470267 | 0.41896 | 0.470015 | 0.0510549 | 1 |
| 17 | interior | n_Propane | 0.013062 | 0.013062 | -0 | 0 | 0.469153 | 0.425027 | 0.468905 | 0.0438778 | 1 |
| 15 | interior | n_Propane | 0.0126765 | 0.0126765 | -0 | 0 | 0.466975 | 0.427569 | 0.466714 | 0.0391457 | 1 |
| 14 | interior | n_Propane | 0.0125715 | 0.0125715 | -0 | 0 | 0.465934 | 0.457095 | 0.465676 | 0.00858121 | 1 |
| 13 | interior | n_Propane | 0.0125208 | 0.0125208 | 0 | -0 | 0.464907 | 0.486303 | 0.464649 | -0.0216537 | 1 |
| 7 | interior | n_Propane | 0.0124962 | 0.0124962 | 0 | -0 | 0.458912 | 0.619894 | 0.458653 | -0.161242 | 1 |
| 12 | interior | n_Propane | 0.0123444 | 0.0123444 | 0 | -0 | 0.463882 | 0.511679 | 0.463629 | -0.0480493 | 1 |
| 10 | interior | n_Propane | 0.0123189 | 0.0123189 | 0 | -0 | 0.461873 | 0.556775 | 0.461616 | -0.0951585 | 1 |
| 11 | interior | n_Propane | 0.0122584 | 0.0122584 | 0 | -0 | 0.46287 | 0.538164 | 0.462615 | -0.0755495 | 1 |
| 9 | interior | n_Propane | 0.011864 | 0.011864 | 0 | -0 | 0.460884 | 0.573543 | 0.460637 | -0.112906 | 1 |
| 4 | interior | n_Propane | 0.0117742 | 0.0117742 | 0 | -0 | 0.455904 | 0.739154 | 0.455668 | -0.283486 | 1 |
| 3 | interior | n_Propane | 0.0116433 | 0.0116433 | 0 | -0 | 0.454837 | 0.747131 | 0.454606 | -0.292525 | 1 |
| 8 | interior | n_Propane | 0.0114613 | 0.0114613 | 0 | -0 | 0.459898 | 0.593138 | 0.45966 | -0.133478 | 1 |
| 5 | interior | n_Propane | 0.0109185 | 0.0109185 | 0 | -0 | 0.45693 | 0.715665 | 0.456704 | -0.258962 | 1 |
| 6 | interior | n_Propane | 0.0106728 | 0.0106728 | 0 | -0 | 0.457923 | 0.659181 | 0.457702 | -0.201479 | 1 |
| 7 | interior | n_Butane | 0.00956019 | 0.00956019 | -0 | 0 | 0.480867 | 0.35185 | 0.480669 | 0.128818 | 1 |
| 16 | interior | n_Butane | 0.00949712 | 0.00949712 | 0 | -0 | 0.472625 | 0.496037 | 0.472444 | -0.0235931 | 1 |

## Top Stage Conflicts
| stage_1based | stage_kind | max_abs_required_target_delta | max_abs_final_rhs_lbmolps |
|---|---|---|---|
| 2 | interior | 0.00889267 | 0.0153988 |
| 16 | interior | 0.0421311 | 0.0135941 |
| 19 | interior | 0.0538158 | 0.0133679 |
| 18 | interior | 0.0510549 | 0.0132393 |
| 17 | interior | 0.0438778 | 0.013062 |
| 15 | interior | 0.0391457 | 0.0126765 |
| 14 | interior | 0.00858121 | 0.0125715 |
| 13 | interior | 0.0216537 | 0.0125208 |
| 7 | interior | 0.161242 | 0.0124962 |
| 12 | interior | 0.0480493 | 0.0123444 |
| 10 | interior | 0.0951585 | 0.0123189 |
| 11 | interior | 0.0755495 | 0.0122584 |
| 9 | interior | 0.112906 | 0.011864 |
| 4 | interior | 0.283486 | 0.0117742 |
| 3 | interior | 0.292525 | 0.0116433 |
| 8 | interior | 0.133478 | 0.0114613 |
| 5 | interior | 0.258962 | 0.0109185 |
| 6 | interior | 0.201479 | 0.0106728 |
| 1 | top | 0 | 0 |
| 20 | bottom | 0.374006 | 0 |
