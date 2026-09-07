# Vapor Transport / Equilibrium Conflict Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_30min_pressure_level_xD_C4_relaxed_refluxcap_20260711\column_profile_20260711_083447.csv`
Time: `50` s

## Summary
| n_stages | n_components | max_abs_final_rhs_lbmolps | max_abs_required_target_delta | fraction_required_components_feasible | median_cancellation_coverage |
|---|---|---|---|---|---|
| 20 | 3 | 0.0108449 | 0.351556 | 1 | 0 |

## Interpretation
- `cancellation_coverage = -equilibrium_transfer / pre_equilibrium_rhs`; `1` would cancel the pre-equilibrium vapor RHS.
- `required_y_target_to_cancel_pre_rhs` is the component target implied by zeroing the pre-equilibrium RHS at the inferred/default relaxation time.
- Large `required_target_delta` means the material transport cancellation demand is far from the logged equilibrium target.

## Top Final RHS Conflicts
| stage_1based | stage_kind | component | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | equilibrium_transfer_lbmolps | cancellation_coverage | y | y_target | required_y_target_to_cancel_pre_rhs | required_target_delta | required_target_component_feasible |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2 | interior | n_Butane | 0.0108449 | 0.378041 | -0.367196 | 0.971313 | 0.29525 | 0.194112 | 0.191125 | -0.00298708 | 1 |
| 19 | interior | n_Propane | 0.010175 | 0.010175 | -0 | 0 | 0.448995 | 0.395236 | 0.448752 | 0.0535162 | 1 |
| 18 | interior | n_Propane | 0.00986405 | 0.00986405 | -0 | 0 | 0.448027 | 0.396713 | 0.447794 | 0.0510807 | 1 |
| 17 | interior | n_Propane | 0.00977592 | 0.00977592 | -0 | 0 | 0.447163 | 0.401887 | 0.446933 | 0.0450456 | 1 |
| 16 | interior | n_Propane | 0.00899607 | 0.00899607 | -0 | 0 | 0.446465 | 0.402347 | 0.446249 | 0.043902 | 1 |
| 3 | interior | n_Propane | 0.00888593 | 0.00888593 | 0 | -0 | 0.436203 | 0.717501 | 0.435986 | -0.281515 | 1 |
| 8 | interior | n_Propane | 0.00877707 | 0.00877707 | 0 | -0 | 0.440986 | 0.589133 | 0.440757 | -0.148376 | 1 |
| 9 | interior | n_Propane | 0.00876089 | 0.00876089 | 0 | -0 | 0.441859 | 0.568867 | 0.441631 | -0.127236 | 1 |
| 10 | interior | n_Propane | 0.00874754 | 0.00874754 | 0 | -0 | 0.442705 | 0.551297 | 0.442476 | -0.108821 | 1 |
| 7 | interior | n_Propane | 0.0087329 | 0.0087329 | 0 | -0 | 0.440093 | 0.616858 | 0.439867 | -0.176992 | 1 |
| 15 | interior | n_Propane | 0.00869426 | 0.00869426 | -0 | 0 | 0.445931 | 0.418235 | 0.445706 | 0.027471 | 1 |
| 11 | interior | n_Propane | 0.00868421 | 0.00868421 | 0 | -0 | 0.443505 | 0.531633 | 0.443277 | -0.0883559 | 1 |
| 13 | interior | n_Propane | 0.00859038 | 0.00859038 | 0 | -0 | 0.444884 | 0.481823 | 0.44466 | -0.0371621 | 1 |
| 12 | interior | n_Propane | 0.00854464 | 0.00854464 | 0 | -0 | 0.444238 | 0.508082 | 0.444019 | -0.0640629 | 1 |
| 14 | interior | n_Propane | 0.00853025 | 0.00853025 | 0 | -0 | 0.44543 | 0.451325 | 0.445209 | -0.00611636 | 1 |
| 4 | interior | n_Propane | 0.00825237 | 0.00825237 | 0 | -0 | 0.437247 | 0.705131 | 0.437042 | -0.268089 | 1 |
| 5 | interior | n_Propane | 0.00810865 | 0.00810865 | 0 | -0 | 0.43824 | 0.695165 | 0.438035 | -0.25713 | 1 |
| 6 | interior | n_Propane | 0.00772 | 0.00772 | 0 | -0 | 0.439185 | 0.657205 | 0.438985 | -0.21822 | 1 |
| 15 | interior | n_Butane | 0.00734881 | 0.00734881 | 0 | -0 | 0.49267 | 0.507492 | 0.49248 | -0.0150115 | 1 |
| 14 | interior | n_Butane | 0.00732602 | 0.00732602 | -0 | 0 | 0.493216 | 0.486978 | 0.493026 | 0.00604777 | 1 |

## Top Required Target Conflicts
| stage_1based | stage_kind | component | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | equilibrium_transfer_lbmolps | cancellation_coverage | y | y_target | required_y_target_to_cancel_pre_rhs | required_target_delta | required_target_component_feasible |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 20 | bottom | n_Propane | 0 | 0 | 0 |  | 0.449978 | 0.098422 | 0.449978 | 0.351556 | 1 |
| 20 | bottom | n_Butane | 0 | 0 | 0 |  | 0.488862 | 0.802308 | 0.488862 | -0.313446 | 1 |
| 3 | interior | n_Propane | 0.00888593 | 0.00888593 | 0 | -0 | 0.436203 | 0.717501 | 0.435986 | -0.281515 | 1 |
| 4 | interior | n_Propane | 0.00825237 | 0.00825237 | 0 | -0 | 0.437247 | 0.705131 | 0.437042 | -0.268089 | 1 |
| 5 | interior | n_Propane | 0.00810865 | 0.00810865 | 0 | -0 | 0.43824 | 0.695165 | 0.438035 | -0.25713 | 1 |
| 3 | interior | n_Butane | 0.00628993 | 0.00628993 | -0 | 0 | 0.501916 | 0.266349 | 0.501762 | 0.235413 | 1 |
| 4 | interior | n_Butane | 0.00566413 | 0.00566413 | -0 | 0 | 0.500964 | 0.277601 | 0.500823 | 0.223222 | 1 |
| 6 | interior | n_Propane | 0.00772 | 0.00772 | 0 | -0 | 0.439185 | 0.657205 | 0.438985 | -0.21822 | 1 |
| 5 | interior | n_Butane | 0.00557813 | 0.00557813 | -0 | 0 | 0.500056 | 0.286603 | 0.499915 | 0.213312 | 1 |
| 6 | interior | n_Butane | 0.00525132 | 0.00525132 | -0 | 0 | 0.499188 | 0.320906 | 0.499052 | 0.178146 | 1 |
| 7 | interior | n_Propane | 0.0087329 | 0.0087329 | 0 | -0 | 0.440093 | 0.616858 | 0.439867 | -0.176992 | 1 |
| 8 | interior | n_Propane | 0.00877707 | 0.00877707 | 0 | -0 | 0.440986 | 0.589133 | 0.440757 | -0.148376 | 1 |
| 7 | interior | n_Butane | 0.00643162 | 0.00643162 | -0 | 0 | 0.498351 | 0.356721 | 0.498184 | 0.141463 | 1 |
| 9 | interior | n_Propane | 0.00876089 | 0.00876089 | 0 | -0 | 0.441859 | 0.568867 | 0.441631 | -0.127236 | 1 |
| 8 | interior | n_Butane | 0.00651652 | 0.00651652 | -0 | 0 | 0.497527 | 0.380844 | 0.497357 | 0.116513 | 1 |
| 10 | interior | n_Propane | 0.00874754 | 0.00874754 | 0 | -0 | 0.442705 | 0.551297 | 0.442476 | -0.108821 | 1 |
| 9 | interior | n_Butane | 0.0065706 | 0.0065706 | -0 | 0 | 0.496715 | 0.398199 | 0.496544 | 0.0983449 | 1 |
| 11 | interior | n_Propane | 0.00868421 | 0.00868421 | 0 | -0 | 0.443505 | 0.531633 | 0.443277 | -0.0883559 | 1 |
| 10 | interior | n_Butane | 0.0066921 | 0.0066921 | -0 | 0 | 0.495923 | 0.413017 | 0.495748 | 0.0827307 | 1 |
| 11 | interior | n_Butane | 0.0068414 | 0.0068414 | -0 | 0 | 0.495163 | 0.429205 | 0.494983 | 0.0657785 | 1 |

## Top Interior Final RHS Conflicts
| stage_1based | stage_kind | component | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | equilibrium_transfer_lbmolps | cancellation_coverage | y | y_target | required_y_target_to_cancel_pre_rhs | required_target_delta | required_target_component_feasible |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2 | interior | n_Butane | 0.0108449 | 0.378041 | -0.367196 | 0.971313 | 0.29525 | 0.194112 | 0.191125 | -0.00298708 | 1 |
| 19 | interior | n_Propane | 0.010175 | 0.010175 | -0 | 0 | 0.448995 | 0.395236 | 0.448752 | 0.0535162 | 1 |
| 18 | interior | n_Propane | 0.00986405 | 0.00986405 | -0 | 0 | 0.448027 | 0.396713 | 0.447794 | 0.0510807 | 1 |
| 17 | interior | n_Propane | 0.00977592 | 0.00977592 | -0 | 0 | 0.447163 | 0.401887 | 0.446933 | 0.0450456 | 1 |
| 16 | interior | n_Propane | 0.00899607 | 0.00899607 | -0 | 0 | 0.446465 | 0.402347 | 0.446249 | 0.043902 | 1 |
| 3 | interior | n_Propane | 0.00888593 | 0.00888593 | 0 | -0 | 0.436203 | 0.717501 | 0.435986 | -0.281515 | 1 |
| 8 | interior | n_Propane | 0.00877707 | 0.00877707 | 0 | -0 | 0.440986 | 0.589133 | 0.440757 | -0.148376 | 1 |
| 9 | interior | n_Propane | 0.00876089 | 0.00876089 | 0 | -0 | 0.441859 | 0.568867 | 0.441631 | -0.127236 | 1 |
| 10 | interior | n_Propane | 0.00874754 | 0.00874754 | 0 | -0 | 0.442705 | 0.551297 | 0.442476 | -0.108821 | 1 |
| 7 | interior | n_Propane | 0.0087329 | 0.0087329 | 0 | -0 | 0.440093 | 0.616858 | 0.439867 | -0.176992 | 1 |
| 15 | interior | n_Propane | 0.00869426 | 0.00869426 | -0 | 0 | 0.445931 | 0.418235 | 0.445706 | 0.027471 | 1 |
| 11 | interior | n_Propane | 0.00868421 | 0.00868421 | 0 | -0 | 0.443505 | 0.531633 | 0.443277 | -0.0883559 | 1 |
| 13 | interior | n_Propane | 0.00859038 | 0.00859038 | 0 | -0 | 0.444884 | 0.481823 | 0.44466 | -0.0371621 | 1 |
| 12 | interior | n_Propane | 0.00854464 | 0.00854464 | 0 | -0 | 0.444238 | 0.508082 | 0.444019 | -0.0640629 | 1 |
| 14 | interior | n_Propane | 0.00853025 | 0.00853025 | 0 | -0 | 0.44543 | 0.451325 | 0.445209 | -0.00611636 | 1 |
| 4 | interior | n_Propane | 0.00825237 | 0.00825237 | 0 | -0 | 0.437247 | 0.705131 | 0.437042 | -0.268089 | 1 |
| 5 | interior | n_Propane | 0.00810865 | 0.00810865 | 0 | -0 | 0.43824 | 0.695165 | 0.438035 | -0.25713 | 1 |
| 6 | interior | n_Propane | 0.00772 | 0.00772 | 0 | -0 | 0.439185 | 0.657205 | 0.438985 | -0.21822 | 1 |
| 15 | interior | n_Butane | 0.00734881 | 0.00734881 | 0 | -0 | 0.49267 | 0.507492 | 0.49248 | -0.0150115 | 1 |
| 14 | interior | n_Butane | 0.00732602 | 0.00732602 | -0 | 0 | 0.493216 | 0.486978 | 0.493026 | 0.00604777 | 1 |

## Top Stage Conflicts
| stage_1based | stage_kind | max_abs_required_target_delta | max_abs_final_rhs_lbmolps |
|---|---|---|---|
| 2 | interior | 0.00298708 | 0.0108449 |
| 19 | interior | 0.0535162 | 0.010175 |
| 18 | interior | 0.0510807 | 0.00986405 |
| 17 | interior | 0.0450456 | 0.00977592 |
| 16 | interior | 0.043902 | 0.00899607 |
| 3 | interior | 0.281515 | 0.00888593 |
| 8 | interior | 0.148376 | 0.00877707 |
| 9 | interior | 0.127236 | 0.00876089 |
| 10 | interior | 0.108821 | 0.00874754 |
| 7 | interior | 0.176992 | 0.0087329 |
| 15 | interior | 0.027471 | 0.00869426 |
| 11 | interior | 0.0883559 | 0.00868421 |
| 13 | interior | 0.0371621 | 0.00859038 |
| 12 | interior | 0.0640629 | 0.00854464 |
| 14 | interior | 0.00611636 | 0.00853025 |
| 4 | interior | 0.268089 | 0.00825237 |
| 5 | interior | 0.25713 | 0.00810865 |
| 6 | interior | 0.21822 | 0.00772 |
| 1 | top | 0 | 0 |
| 20 | bottom | 0.351556 | 0 |
