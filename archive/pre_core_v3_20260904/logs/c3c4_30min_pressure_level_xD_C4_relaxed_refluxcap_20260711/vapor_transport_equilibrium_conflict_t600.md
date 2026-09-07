# Vapor Transport / Equilibrium Conflict Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_30min_pressure_level_xD_C4_relaxed_refluxcap_20260711\column_profile_20260711_083447.csv`
Time: `600` s

## Summary
| n_stages | n_components | max_abs_final_rhs_lbmolps | max_abs_required_target_delta | fraction_required_components_feasible | median_cancellation_coverage |
|---|---|---|---|---|---|
| 20 | 3 | 0.0233743 | 0.39889 | 1 | 0 |

## Interpretation
- `cancellation_coverage = -equilibrium_transfer / pre_equilibrium_rhs`; `1` would cancel the pre-equilibrium vapor RHS.
- `required_y_target_to_cancel_pre_rhs` is the component target implied by zeroing the pre-equilibrium RHS at the inferred/default relaxation time.
- Large `required_target_delta` means the material transport cancellation demand is far from the logged equilibrium target.

## Top Final RHS Conflicts
| stage_1based | stage_kind | component | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | equilibrium_transfer_lbmolps | cancellation_coverage | y | y_target | required_y_target_to_cancel_pre_rhs | required_target_delta | required_target_component_feasible |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2 | interior | n_Butane | 0.0233743 | 0.129933 | -0.106558 | 0.820104 | 0.397501 | 0.206053 | 0.164058 | -0.0419955 | 1 |
| 8 | interior | n_Propane | 0.0164899 | 0.0164899 | 0 | -0 | 0.484994 | 0.597411 | 0.484733 | -0.112678 | 1 |
| 15 | interior | n_Propane | 0.0158615 | 0.0158615 | -0 | 0 | 0.492166 | 0.455397 | 0.491918 | 0.0365208 | 1 |
| 13 | interior | n_Propane | 0.0157472 | 0.0157472 | 0 | -0 | 0.489799 | 0.491687 | 0.489552 | -0.00213548 | 1 |
| 14 | interior | n_Propane | 0.0155876 | 0.0155876 | -0 | 0 | 0.491004 | 0.464265 | 0.490759 | 0.0264942 | 1 |
| 12 | interior | n_Propane | 0.0155563 | 0.0155563 | 0 | -0 | 0.490064 | 0.515873 | 0.489818 | -0.0260548 | 1 |
| 17 | interior | n_Propane | 0.015529 | 0.015529 | -0 | 0 | 0.494391 | 0.453775 | 0.494162 | 0.040387 | 1 |
| 16 | interior | n_Propane | 0.0155184 | 0.0155184 | -0 | 0 | 0.493282 | 0.45384 | 0.493053 | 0.039213 | 1 |
| 18 | interior | n_Propane | 0.0155152 | 0.0155152 | -0 | 0 | 0.495428 | 0.44758 | 0.495199 | 0.0476188 | 1 |
| 19 | interior | n_Propane | 0.0154812 | 0.0154812 | -0 | 0 | 0.4964 | 0.446379 | 0.49617 | 0.0497913 | 1 |
| 5 | interior | n_Propane | 0.0152631 | 0.0152631 | 0 | -0 | 0.480907 | 0.716466 | 0.480664 | -0.235802 | 1 |
| 11 | interior | n_Propane | 0.0151201 | 0.0151201 | 0 | -0 | 0.488844 | 0.545973 | 0.488606 | -0.0573672 | 1 |
| 10 | interior | n_Propane | 0.0150995 | 0.0150995 | 0 | -0 | 0.487592 | 0.563205 | 0.487354 | -0.0758514 | 1 |
| 3 | interior | n_Propane | 0.0150268 | 0.0150268 | 0 | -0 | 0.47806 | 0.761605 | 0.477828 | -0.283778 | 1 |
| 4 | interior | n_Propane | 0.0146166 | 0.0146166 | 0 | -0 | 0.479505 | 0.755758 | 0.479275 | -0.276483 | 1 |
| 9 | interior | n_Propane | 0.0143678 | 0.0143678 | 0 | -0 | 0.486309 | 0.578957 | 0.486082 | -0.092875 | 1 |
| 6 | interior | n_Propane | 0.0129525 | 0.0129525 | 0 | -0 | 0.482286 | 0.661044 | 0.48208 | -0.178963 | 1 |
| 7 | interior | n_Propane | 0.0128567 | 0.0128567 | 0 | -0 | 0.48365 | 0.623063 | 0.483446 | -0.139616 | 1 |
| 8 | interior | n_Butane | 0.0109919 | 0.0109919 | -0 | 0 | 0.457496 | 0.367587 | 0.457322 | 0.0897347 | 1 |
| 15 | interior | n_Butane | 0.0105961 | 0.0105961 | 0 | -0 | 0.45056 | 0.4711 | 0.450395 | -0.0207058 | 1 |

## Top Required Target Conflicts
| stage_1based | stage_kind | component | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | equilibrium_transfer_lbmolps | cancellation_coverage | y | y_target | required_y_target_to_cancel_pre_rhs | required_target_delta | required_target_component_feasible |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 20 | bottom | n_Propane | 0 | 0 | 0 |  | 0.497312 | 0.098422 | 0.497312 | 0.39889 | 1 |
| 20 | bottom | n_Butane | 0 | 0 | 0 |  | 0.445689 | 0.802308 | 0.445689 | -0.356619 | 1 |
| 3 | interior | n_Propane | 0.0150268 | 0.0150268 | 0 | -0 | 0.47806 | 0.761605 | 0.477828 | -0.283778 | 1 |
| 4 | interior | n_Propane | 0.0146166 | 0.0146166 | 0 | -0 | 0.479505 | 0.755758 | 0.479275 | -0.276483 | 1 |
| 3 | interior | n_Butane | 0.00962774 | 0.00962774 | -0 | 0 | 0.46374 | 0.225085 | 0.463592 | 0.238507 | 1 |
| 5 | interior | n_Propane | 0.0152631 | 0.0152631 | 0 | -0 | 0.480907 | 0.716466 | 0.480664 | -0.235802 | 1 |
| 4 | interior | n_Butane | 0.00927141 | 0.00927141 | -0 | 0 | 0.462448 | 0.230357 | 0.462302 | 0.231945 | 1 |
| 5 | interior | n_Butane | 0.00989799 | 0.00989799 | -0 | 0 | 0.46119 | 0.265913 | 0.461033 | 0.19512 | 1 |
| 6 | interior | n_Propane | 0.0129525 | 0.0129525 | 0 | -0 | 0.482286 | 0.661044 | 0.48208 | -0.178963 | 1 |
| 6 | interior | n_Butane | 0.00766559 | 0.00766559 | -0 | 0 | 0.459949 | 0.314798 | 0.459827 | 0.145029 | 1 |
| 7 | interior | n_Propane | 0.0128567 | 0.0128567 | 0 | -0 | 0.48365 | 0.623063 | 0.483446 | -0.139616 | 1 |
| 8 | interior | n_Propane | 0.0164899 | 0.0164899 | 0 | -0 | 0.484994 | 0.597411 | 0.484733 | -0.112678 | 1 |
| 7 | interior | n_Butane | 0.00757729 | 0.00757729 | -0 | 0 | 0.458715 | 0.346769 | 0.458595 | 0.111826 | 1 |
| 9 | interior | n_Propane | 0.0143678 | 0.0143678 | 0 | -0 | 0.486309 | 0.578957 | 0.486082 | -0.092875 | 1 |
| 8 | interior | n_Butane | 0.0109919 | 0.0109919 | -0 | 0 | 0.457496 | 0.367587 | 0.457322 | 0.0897347 | 1 |
| 10 | interior | n_Propane | 0.0150995 | 0.0150995 | 0 | -0 | 0.487592 | 0.563205 | 0.487354 | -0.0758514 | 1 |
| 9 | interior | n_Butane | 0.00900942 | 0.00900942 | -0 | 0 | 0.456295 | 0.382001 | 0.456153 | 0.0741518 | 1 |
| 10 | interior | n_Butane | 0.00972468 | 0.00972468 | -0 | 0 | 0.455119 | 0.393901 | 0.454965 | 0.0610645 | 1 |
| 11 | interior | n_Propane | 0.0151201 | 0.0151201 | 0 | -0 | 0.488844 | 0.545973 | 0.488606 | -0.0573672 | 1 |
| 19 | interior | n_Propane | 0.0154812 | 0.0154812 | -0 | 0 | 0.4964 | 0.446379 | 0.49617 | 0.0497913 | 1 |

## Top Interior Final RHS Conflicts
| stage_1based | stage_kind | component | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | equilibrium_transfer_lbmolps | cancellation_coverage | y | y_target | required_y_target_to_cancel_pre_rhs | required_target_delta | required_target_component_feasible |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2 | interior | n_Butane | 0.0233743 | 0.129933 | -0.106558 | 0.820104 | 0.397501 | 0.206053 | 0.164058 | -0.0419955 | 1 |
| 8 | interior | n_Propane | 0.0164899 | 0.0164899 | 0 | -0 | 0.484994 | 0.597411 | 0.484733 | -0.112678 | 1 |
| 15 | interior | n_Propane | 0.0158615 | 0.0158615 | -0 | 0 | 0.492166 | 0.455397 | 0.491918 | 0.0365208 | 1 |
| 13 | interior | n_Propane | 0.0157472 | 0.0157472 | 0 | -0 | 0.489799 | 0.491687 | 0.489552 | -0.00213548 | 1 |
| 14 | interior | n_Propane | 0.0155876 | 0.0155876 | -0 | 0 | 0.491004 | 0.464265 | 0.490759 | 0.0264942 | 1 |
| 12 | interior | n_Propane | 0.0155563 | 0.0155563 | 0 | -0 | 0.490064 | 0.515873 | 0.489818 | -0.0260548 | 1 |
| 17 | interior | n_Propane | 0.015529 | 0.015529 | -0 | 0 | 0.494391 | 0.453775 | 0.494162 | 0.040387 | 1 |
| 16 | interior | n_Propane | 0.0155184 | 0.0155184 | -0 | 0 | 0.493282 | 0.45384 | 0.493053 | 0.039213 | 1 |
| 18 | interior | n_Propane | 0.0155152 | 0.0155152 | -0 | 0 | 0.495428 | 0.44758 | 0.495199 | 0.0476188 | 1 |
| 19 | interior | n_Propane | 0.0154812 | 0.0154812 | -0 | 0 | 0.4964 | 0.446379 | 0.49617 | 0.0497913 | 1 |
| 5 | interior | n_Propane | 0.0152631 | 0.0152631 | 0 | -0 | 0.480907 | 0.716466 | 0.480664 | -0.235802 | 1 |
| 11 | interior | n_Propane | 0.0151201 | 0.0151201 | 0 | -0 | 0.488844 | 0.545973 | 0.488606 | -0.0573672 | 1 |
| 10 | interior | n_Propane | 0.0150995 | 0.0150995 | 0 | -0 | 0.487592 | 0.563205 | 0.487354 | -0.0758514 | 1 |
| 3 | interior | n_Propane | 0.0150268 | 0.0150268 | 0 | -0 | 0.47806 | 0.761605 | 0.477828 | -0.283778 | 1 |
| 4 | interior | n_Propane | 0.0146166 | 0.0146166 | 0 | -0 | 0.479505 | 0.755758 | 0.479275 | -0.276483 | 1 |
| 9 | interior | n_Propane | 0.0143678 | 0.0143678 | 0 | -0 | 0.486309 | 0.578957 | 0.486082 | -0.092875 | 1 |
| 6 | interior | n_Propane | 0.0129525 | 0.0129525 | 0 | -0 | 0.482286 | 0.661044 | 0.48208 | -0.178963 | 1 |
| 7 | interior | n_Propane | 0.0128567 | 0.0128567 | 0 | -0 | 0.48365 | 0.623063 | 0.483446 | -0.139616 | 1 |
| 8 | interior | n_Butane | 0.0109919 | 0.0109919 | -0 | 0 | 0.457496 | 0.367587 | 0.457322 | 0.0897347 | 1 |
| 15 | interior | n_Butane | 0.0105961 | 0.0105961 | 0 | -0 | 0.45056 | 0.4711 | 0.450395 | -0.0207058 | 1 |

## Top Stage Conflicts
| stage_1based | stage_kind | max_abs_required_target_delta | max_abs_final_rhs_lbmolps |
|---|---|---|---|
| 2 | interior | 0.0419955 | 0.0233743 |
| 8 | interior | 0.112678 | 0.0164899 |
| 15 | interior | 0.0365208 | 0.0158615 |
| 13 | interior | 0.00321256 | 0.0157472 |
| 14 | interior | 0.0264942 | 0.0155876 |
| 12 | interior | 0.0260548 | 0.0155563 |
| 17 | interior | 0.040387 | 0.015529 |
| 16 | interior | 0.039213 | 0.0155184 |
| 18 | interior | 0.0476188 | 0.0155152 |
| 19 | interior | 0.0497913 | 0.0154812 |
| 5 | interior | 0.235802 | 0.0152631 |
| 11 | interior | 0.0573672 | 0.0151201 |
| 10 | interior | 0.0758514 | 0.0150995 |
| 3 | interior | 0.283778 | 0.0150268 |
| 4 | interior | 0.276483 | 0.0146166 |
| 9 | interior | 0.092875 | 0.0143678 |
| 6 | interior | 0.178963 | 0.0129525 |
| 7 | interior | 0.139616 | 0.0128567 |
| 1 | top | 0 | 0 |
| 20 | bottom | 0.39889 | 0 |
