# Vapor Transport / Equilibrium Conflict Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_interior_liq_vapor_eq_align_rhs_terms_20260707\column_profile_20260707_153257.csv`
Time: `0.2` s

## Summary
| n_stages | n_components | max_abs_final_rhs_lbmolps | max_abs_required_target_delta | fraction_required_components_feasible | median_cancellation_coverage |
|---|---|---|---|---|---|
| 20 | 3 | 0.161902 | 0.0269866 | 1 | 0.370778 |

## Interpretation
- `cancellation_coverage = -equilibrium_transfer / pre_equilibrium_rhs`; `1` would cancel the pre-equilibrium vapor RHS.
- `required_y_target_to_cancel_pre_rhs` is the component target implied by zeroing the pre-equilibrium RHS at the inferred/default relaxation time.
- Large `required_target_delta` means the material transport cancellation demand is far from the logged equilibrium target.

## Top Final RHS Conflicts
| stage_1based | stage_kind | component | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | equilibrium_transfer_lbmolps | cancellation_coverage | y | y_target | required_y_target_to_cancel_pre_rhs | required_target_delta | required_target_component_feasible |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2 | interior | n_Propane | 0.161902 | 0.0767185 | 0.0851839 | -1.11034 | 0.847736 | 0.848765 | 0.846809 | -0.00195668 | 1 |
| 3 | interior | n_Propane | -0.159965 | -0.242647 | 0.0826817 | 0.340749 | 0.860775 | 0.864262 | 0.871006 | 0.00674483 | 1 |
| 4 | interior | n_Propane | -0.147161 | -0.22307 | 0.0759095 | 0.340294 | 0.772545 | 0.7758 | 0.782112 | 0.00631132 | 1 |
| 3 | interior | n_Butane | 0.120286 | 0.202942 | -0.0826568 | 0.407292 | 0.1392 | 0.135715 | 0.130643 | -0.00507175 | 1 |
| 2 | interior | n_Butane | -0.108519 | -0.0232203 | -0.0852984 | -3.67344 | 0.152251 | 0.15122 | 0.152532 | 0.00131151 | 1 |
| 5 | interior | n_Propane | -0.108324 | -0.167681 | 0.059357 | 0.353988 | 0.690932 | 0.693508 | 0.69821 | 0.00470158 | 1 |
| 4 | interior | n_Butane | 0.10355 | 0.179402 | -0.0758519 | 0.422805 | 0.227365 | 0.224112 | 0.219671 | -0.00444096 | 1 |
| 19 | interior | n_Propane | -0.0865203 | -0.135882 | 0.049362 | 0.36327 | 0.170058 | 0.172008 | 0.175425 | 0.00341772 | 1 |
| 5 | interior | n_Butane | 0.0782924 | 0.137523 | -0.0592302 | 0.430694 | 0.308809 | 0.306239 | 0.302841 | -0.00339812 | 1 |
| 6 | interior | n_Propane | -0.0734991 | -0.115586 | 0.0420871 | 0.364119 | 0.6268 | 0.62864 | 0.631854 | 0.00321373 | 1 |
| 16 | interior | n_Propane | -0.069553 | -0.125524 | 0.0559711 | 0.445899 | 0.327523 | 0.329714 | 0.332437 | 0.00272322 | 1 |
| 17 | interior | n_Propane | -0.0655761 | -0.120452 | 0.054876 | 0.455584 | 0.271605 | 0.27376 | 0.276335 | 0.00257501 | 1 |

## Top Required Target Conflicts
| stage_1based | stage_kind | component | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | equilibrium_transfer_lbmolps | cancellation_coverage | y | y_target | required_y_target_to_cancel_pre_rhs | required_target_delta | required_target_component_feasible |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 20 | bottom | n_Pentane | 0 | 0 | 0 |  | 0.111002 | 0.0840153 | 0.111002 | 0.0269866 | 1 |
| 20 | bottom | n_Butane | 0 | 0 | 0 |  | 0.779919 | 0.805762 | 0.779919 | -0.0258431 | 1 |
| 3 | interior | n_Propane | -0.159965 | -0.242647 | 0.0826817 | 0.340749 | 0.860775 | 0.864262 | 0.871006 | 0.00674483 | 1 |
| 4 | interior | n_Propane | -0.147161 | -0.22307 | 0.0759095 | 0.340294 | 0.772545 | 0.7758 | 0.782112 | 0.00631132 | 1 |
| 3 | interior | n_Butane | 0.120286 | 0.202942 | -0.0826568 | 0.407292 | 0.1392 | 0.135715 | 0.130643 | -0.00507175 | 1 |
| 5 | interior | n_Propane | -0.108324 | -0.167681 | 0.059357 | 0.353988 | 0.690932 | 0.693508 | 0.69821 | 0.00470158 | 1 |
| 4 | interior | n_Butane | 0.10355 | 0.179402 | -0.0758519 | 0.422805 | 0.227365 | 0.224112 | 0.219671 | -0.00444096 | 1 |
| 19 | interior | n_Propane | -0.0865203 | -0.135882 | 0.049362 | 0.36327 | 0.170058 | 0.172008 | 0.175425 | 0.00341772 | 1 |
| 5 | interior | n_Butane | 0.0782924 | 0.137523 | -0.0592302 | 0.430694 | 0.308809 | 0.306239 | 0.302841 | -0.00339812 | 1 |
| 6 | interior | n_Propane | -0.0734991 | -0.115586 | 0.0420871 | 0.364119 | 0.6268 | 0.62864 | 0.631854 | 0.00321373 | 1 |
| 15 | interior | n_Propane | -0.0648159 | -0.121413 | 0.0565975 | 0.466155 | 0.380586 | 0.383122 | 0.386026 | 0.00290437 | 1 |
| 16 | interior | n_Propane | -0.069553 | -0.125524 | 0.0559711 | 0.445899 | 0.327523 | 0.329714 | 0.332437 | 0.00272322 | 1 |

## Top Interior Final RHS Conflicts
| stage_1based | stage_kind | component | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | equilibrium_transfer_lbmolps | cancellation_coverage | y | y_target | required_y_target_to_cancel_pre_rhs | required_target_delta | required_target_component_feasible |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2 | interior | n_Propane | 0.161902 | 0.0767185 | 0.0851839 | -1.11034 | 0.847736 | 0.848765 | 0.846809 | -0.00195668 | 1 |
| 3 | interior | n_Propane | -0.159965 | -0.242647 | 0.0826817 | 0.340749 | 0.860775 | 0.864262 | 0.871006 | 0.00674483 | 1 |
| 4 | interior | n_Propane | -0.147161 | -0.22307 | 0.0759095 | 0.340294 | 0.772545 | 0.7758 | 0.782112 | 0.00631132 | 1 |
| 3 | interior | n_Butane | 0.120286 | 0.202942 | -0.0826568 | 0.407292 | 0.1392 | 0.135715 | 0.130643 | -0.00507175 | 1 |
| 2 | interior | n_Butane | -0.108519 | -0.0232203 | -0.0852984 | -3.67344 | 0.152251 | 0.15122 | 0.152532 | 0.00131151 | 1 |
| 5 | interior | n_Propane | -0.108324 | -0.167681 | 0.059357 | 0.353988 | 0.690932 | 0.693508 | 0.69821 | 0.00470158 | 1 |
| 4 | interior | n_Butane | 0.10355 | 0.179402 | -0.0758519 | 0.422805 | 0.227365 | 0.224112 | 0.219671 | -0.00444096 | 1 |
| 19 | interior | n_Propane | -0.0865203 | -0.135882 | 0.049362 | 0.36327 | 0.170058 | 0.172008 | 0.175425 | 0.00341772 | 1 |
| 5 | interior | n_Butane | 0.0782924 | 0.137523 | -0.0592302 | 0.430694 | 0.308809 | 0.306239 | 0.302841 | -0.00339812 | 1 |
| 6 | interior | n_Propane | -0.0734991 | -0.115586 | 0.0420871 | 0.364119 | 0.6268 | 0.62864 | 0.631854 | 0.00321373 | 1 |
| 16 | interior | n_Propane | -0.069553 | -0.125524 | 0.0559711 | 0.445899 | 0.327523 | 0.329714 | 0.332437 | 0.00272322 | 1 |
| 17 | interior | n_Propane | -0.0655761 | -0.120452 | 0.054876 | 0.455584 | 0.271605 | 0.27376 | 0.276335 | 0.00257501 | 1 |

## Top Stage Conflicts
| stage_1based | stage_kind | max_abs_required_target_delta | max_abs_final_rhs_lbmolps |
|---|---|---|---|
| 2 | interior | 0.00195668 | 0.161902 |
| 3 | interior | 0.00674483 | 0.159965 |
| 4 | interior | 0.00631132 | 0.147161 |
| 5 | interior | 0.00470158 | 0.108324 |
| 19 | interior | 0.00341772 | 0.0865203 |
| 6 | interior | 0.00321373 | 0.0734991 |
| 16 | interior | 0.00272322 | 0.069553 |
| 17 | interior | 0.00257501 | 0.0655761 |
| 15 | interior | 0.00290437 | 0.0648159 |
| 18 | interior | 0.00248508 | 0.0631176 |
| 14 | interior | 0.00263392 | 0.0589481 |
| 13 | interior | 0.00227225 | 0.0509793 |
