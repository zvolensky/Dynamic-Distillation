# Vapor Transport / Equilibrium Conflict Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\checkpoint_no_energy_reload_300s_20260708\column_profile_20260708_181150.csv`
Time: `300` s

## Summary
| n_stages | n_components | max_abs_final_rhs_lbmolps | max_abs_required_target_delta | fraction_required_components_feasible | median_cancellation_coverage |
|---|---|---|---|---|---|
| 20 | 3 | 0.027359 |  | 1 |  |

## Interpretation
- `cancellation_coverage = -equilibrium_transfer / pre_equilibrium_rhs`; `1` would cancel the pre-equilibrium vapor RHS.
- `required_y_target_to_cancel_pre_rhs` is the component target implied by zeroing the pre-equilibrium RHS at the inferred/default relaxation time.
- Large `required_target_delta` means the material transport cancellation demand is far from the logged equilibrium target.

## Top Final RHS Conflicts
| stage_1based | stage_kind | component | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | equilibrium_transfer_lbmolps | cancellation_coverage | y | y_target | required_y_target_to_cancel_pre_rhs | required_target_delta | required_target_component_feasible |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2 | interior | n_Propane | 0.027359 | 0.027359 |  |  | 0.50018 |  | 0.499984 |  | 1 |
| 3 | interior | n_Propane | 0.026001 | 0.026001 |  |  | 0.502931 |  | 0.502591 |  | 1 |
| 4 | interior | n_Propane | 0.0250874 | 0.0250874 |  |  | 0.50415 |  | 0.503816 |  | 1 |
| 12 | interior | n_Propane | 0.0249872 | 0.0249872 |  |  | 0.512256 |  | 0.511919 |  | 1 |
| 5 | interior | n_Propane | 0.0249223 | 0.0249223 |  |  | 0.505257 |  | 0.504922 |  | 1 |
| 11 | interior | n_Propane | 0.0249049 | 0.0249049 |  |  | 0.511244 |  | 0.510901 |  | 1 |
| 14 | interior | n_Propane | 0.0248604 | 0.0248604 |  |  | 0.51423 |  | 0.51389 |  | 1 |
| 13 | interior | n_Propane | 0.024849 | 0.024849 |  |  | 0.513258 |  | 0.512918 |  | 1 |
| 15 | interior | n_Propane | 0.0248481 | 0.0248481 |  |  | 0.515166 |  | 0.514827 |  | 1 |
| 16 | interior | n_Propane | 0.0248466 | 0.0248466 |  |  | 0.516035 |  | 0.515711 |  | 1 |
| 10 | interior | n_Propane | 0.0247656 | 0.0247656 |  |  | 0.510245 |  | 0.509905 |  | 1 |
| 17 | interior | n_Propane | 0.0247076 | 0.0247076 |  |  | 0.516841 |  | 0.516518 |  | 1 |
| 6 | interior | n_Propane | 0.0246422 | 0.0246422 |  |  | 0.506293 |  | 0.505958 |  | 1 |
| 9 | interior | n_Propane | 0.0246412 | 0.0246412 |  |  | 0.509256 |  | 0.508919 |  | 1 |
| 7 | interior | n_Propane | 0.0245758 | 0.0245758 |  |  | 0.50729 |  | 0.506956 |  | 1 |
| 18 | interior | n_Propane | 0.024511 | 0.024511 |  |  | 0.51752 |  | 0.517198 |  | 1 |
| 8 | interior | n_Propane | 0.0244676 | 0.0244676 |  |  | 0.508273 |  | 0.507939 |  | 1 |
| 19 | interior | n_Propane | 0.0242831 | 0.0242831 |  |  | 0.518057 |  | 0.517741 |  | 1 |
| 3 | interior | n_Butane | 0.0197025 | 0.0197025 |  |  | 0.445251 |  | 0.444993 |  | 1 |
| 4 | interior | n_Butane | 0.0190333 | 0.0190333 |  |  | 0.444111 |  | 0.443857 |  | 1 |

## Top Required Target Conflicts
| stage_1based | stage_kind | component | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | equilibrium_transfer_lbmolps | cancellation_coverage | y | y_target | required_y_target_to_cancel_pre_rhs | required_target_delta | required_target_component_feasible |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2 | interior | n_Propane | 0.027359 | 0.027359 |  |  | 0.50018 |  | 0.499984 |  | 1 |
| 3 | interior | n_Propane | 0.026001 | 0.026001 |  |  | 0.502931 |  | 0.502591 |  | 1 |
| 4 | interior | n_Propane | 0.0250874 | 0.0250874 |  |  | 0.50415 |  | 0.503816 |  | 1 |
| 12 | interior | n_Propane | 0.0249872 | 0.0249872 |  |  | 0.512256 |  | 0.511919 |  | 1 |
| 5 | interior | n_Propane | 0.0249223 | 0.0249223 |  |  | 0.505257 |  | 0.504922 |  | 1 |
| 11 | interior | n_Propane | 0.0249049 | 0.0249049 |  |  | 0.511244 |  | 0.510901 |  | 1 |
| 14 | interior | n_Propane | 0.0248604 | 0.0248604 |  |  | 0.51423 |  | 0.51389 |  | 1 |
| 13 | interior | n_Propane | 0.024849 | 0.024849 |  |  | 0.513258 |  | 0.512918 |  | 1 |
| 15 | interior | n_Propane | 0.0248481 | 0.0248481 |  |  | 0.515166 |  | 0.514827 |  | 1 |
| 16 | interior | n_Propane | 0.0248466 | 0.0248466 |  |  | 0.516035 |  | 0.515711 |  | 1 |
| 10 | interior | n_Propane | 0.0247656 | 0.0247656 |  |  | 0.510245 |  | 0.509905 |  | 1 |
| 17 | interior | n_Propane | 0.0247076 | 0.0247076 |  |  | 0.516841 |  | 0.516518 |  | 1 |
| 6 | interior | n_Propane | 0.0246422 | 0.0246422 |  |  | 0.506293 |  | 0.505958 |  | 1 |
| 9 | interior | n_Propane | 0.0246412 | 0.0246412 |  |  | 0.509256 |  | 0.508919 |  | 1 |
| 7 | interior | n_Propane | 0.0245758 | 0.0245758 |  |  | 0.50729 |  | 0.506956 |  | 1 |
| 18 | interior | n_Propane | 0.024511 | 0.024511 |  |  | 0.51752 |  | 0.517198 |  | 1 |
| 8 | interior | n_Propane | 0.0244676 | 0.0244676 |  |  | 0.508273 |  | 0.507939 |  | 1 |
| 19 | interior | n_Propane | 0.0242831 | 0.0242831 |  |  | 0.518057 |  | 0.517741 |  | 1 |
| 3 | interior | n_Butane | 0.0197025 | 0.0197025 |  |  | 0.445251 |  | 0.444993 |  | 1 |
| 4 | interior | n_Butane | 0.0190333 | 0.0190333 |  |  | 0.444111 |  | 0.443857 |  | 1 |

## Top Interior Final RHS Conflicts
| stage_1based | stage_kind | component | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | equilibrium_transfer_lbmolps | cancellation_coverage | y | y_target | required_y_target_to_cancel_pre_rhs | required_target_delta | required_target_component_feasible |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2 | interior | n_Propane | 0.027359 | 0.027359 |  |  | 0.50018 |  | 0.499984 |  | 1 |
| 3 | interior | n_Propane | 0.026001 | 0.026001 |  |  | 0.502931 |  | 0.502591 |  | 1 |
| 4 | interior | n_Propane | 0.0250874 | 0.0250874 |  |  | 0.50415 |  | 0.503816 |  | 1 |
| 12 | interior | n_Propane | 0.0249872 | 0.0249872 |  |  | 0.512256 |  | 0.511919 |  | 1 |
| 5 | interior | n_Propane | 0.0249223 | 0.0249223 |  |  | 0.505257 |  | 0.504922 |  | 1 |
| 11 | interior | n_Propane | 0.0249049 | 0.0249049 |  |  | 0.511244 |  | 0.510901 |  | 1 |
| 14 | interior | n_Propane | 0.0248604 | 0.0248604 |  |  | 0.51423 |  | 0.51389 |  | 1 |
| 13 | interior | n_Propane | 0.024849 | 0.024849 |  |  | 0.513258 |  | 0.512918 |  | 1 |
| 15 | interior | n_Propane | 0.0248481 | 0.0248481 |  |  | 0.515166 |  | 0.514827 |  | 1 |
| 16 | interior | n_Propane | 0.0248466 | 0.0248466 |  |  | 0.516035 |  | 0.515711 |  | 1 |
| 10 | interior | n_Propane | 0.0247656 | 0.0247656 |  |  | 0.510245 |  | 0.509905 |  | 1 |
| 17 | interior | n_Propane | 0.0247076 | 0.0247076 |  |  | 0.516841 |  | 0.516518 |  | 1 |
| 6 | interior | n_Propane | 0.0246422 | 0.0246422 |  |  | 0.506293 |  | 0.505958 |  | 1 |
| 9 | interior | n_Propane | 0.0246412 | 0.0246412 |  |  | 0.509256 |  | 0.508919 |  | 1 |
| 7 | interior | n_Propane | 0.0245758 | 0.0245758 |  |  | 0.50729 |  | 0.506956 |  | 1 |
| 18 | interior | n_Propane | 0.024511 | 0.024511 |  |  | 0.51752 |  | 0.517198 |  | 1 |
| 8 | interior | n_Propane | 0.0244676 | 0.0244676 |  |  | 0.508273 |  | 0.507939 |  | 1 |
| 19 | interior | n_Propane | 0.0242831 | 0.0242831 |  |  | 0.518057 |  | 0.517741 |  | 1 |
| 3 | interior | n_Butane | 0.0197025 | 0.0197025 |  |  | 0.445251 |  | 0.444993 |  | 1 |
| 4 | interior | n_Butane | 0.0190333 | 0.0190333 |  |  | 0.444111 |  | 0.443857 |  | 1 |

## Top Stage Conflicts
| stage_1based | stage_kind | max_abs_required_target_delta | max_abs_final_rhs_lbmolps |
|---|---|---|---|
| 2 | interior | 0 | 0.027359 |
| 3 | interior | 0 | 0.026001 |
| 4 | interior | 0 | 0.0250874 |
| 12 | interior | 0 | 0.0249872 |
| 5 | interior | 0 | 0.0249223 |
| 11 | interior | 0 | 0.0249049 |
| 14 | interior | 0 | 0.0248604 |
| 13 | interior | 0 | 0.024849 |
| 15 | interior | 0 | 0.0248481 |
| 16 | interior | 0 | 0.0248466 |
| 10 | interior | 0 | 0.0247656 |
| 17 | interior | 0 | 0.0247076 |
| 6 | interior | 0 | 0.0246422 |
| 9 | interior | 0 | 0.0246412 |
| 7 | interior | 0 | 0.0245758 |
| 18 | interior | 0 | 0.024511 |
| 8 | interior | 0 | 0.0244676 |
| 19 | interior | 0 | 0.0242831 |
| 1 | top | 0 | 0 |
| 20 | bottom | 0 | 0 |
