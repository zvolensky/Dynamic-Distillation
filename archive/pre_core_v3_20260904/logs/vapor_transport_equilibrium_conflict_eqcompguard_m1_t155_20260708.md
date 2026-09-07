# Vapor Transport / Equilibrium Conflict Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_liq_eq_vap_linearsteady_300s_eqcompguard_m1_20260708\column_profile_20260708_082230.csv`
Time: `155` s

## Summary
| n_stages | n_components | max_abs_final_rhs_lbmolps | max_abs_required_target_delta | fraction_required_components_feasible | median_cancellation_coverage |
|---|---|---|---|---|---|
| 20 | 3 | 0.278185 | 0.271407 | 0.947368 | 0.767687 |

## Interpretation
- `cancellation_coverage = -equilibrium_transfer / pre_equilibrium_rhs`; `1` would cancel the pre-equilibrium vapor RHS.
- `required_y_target_to_cancel_pre_rhs` is the component target implied by zeroing the pre-equilibrium RHS at the inferred/default relaxation time.
- Large `required_target_delta` means the material transport cancellation demand is far from the logged equilibrium target.

## Top Final RHS Conflicts
| stage_1based | stage_kind | component | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | equilibrium_transfer_lbmolps | cancellation_coverage | y | y_target | required_y_target_to_cancel_pre_rhs | required_target_delta | required_target_component_feasible |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 4 | interior | n_Butane | 0.278185 | 0.278185 | 0 | -0 | 0.324105 | 0.391206 | 0.310031 | -0.0811749 | 1 |
| 4 | interior | n_Propane | -0.256099 | -0.256099 | -0 | -0 | 0.666846 | 0.60061 | 0.679803 | 0.0791935 | 1 |
| 5 | interior | n_Butane | 0.112582 | 0.112582 | 0 | -0 | 0.43812 | 0.487513 | 0.432545 | -0.0549678 | 1 |
| 5 | interior | n_Propane | -0.0886817 | -0.0886817 | -0 | -0 | 0.544208 | 0.498258 | 0.5486 | 0.0503416 | 1 |
| 6 | interior | n_Propane | -0.0399001 | -0.0608212 | 0.0209211 | 0.343977 | 0.497099 | 0.639408 | 0.910815 | 0.271407 | 1 |
| 2 | interior | n_Propane | -0.0290069 | -0.0906018 | 0.0615949 | 0.679842 | 0.820272 | 0.82103 | 0.821388 | 0.000357073 | 1 |
| 7 | interior | n_Propane | -0.0262852 | -0.0519399 | 0.0256547 | 0.49393 | 0.478565 | 0.595659 | 0.715631 | 0.119972 | 1 |
| 8 | interior | n_Propane | -0.0206927 | -0.054207 | 0.0335143 | 0.618265 | 0.460778 | 0.56557 | 0.630273 | 0.0647023 | 1 |
| 17 | interior | n_Butane | -0.0205514 | -0.0205514 | -0 | -0 | 0.728438 | 0.666632 | 0.729332 | 0.0626992 | 1 |
| 4 | interior | n_Pentane | 0.0203829 | 0.0203829 | -0 | 0 | 0.00904842 | 0.00818446 | 0.00801718 | -0.000167278 | 1 |
| 19 | interior | n_Butane | -0.0178828 | -0.0243037 | 0.00642093 | 0.264195 | 0.723372 | 0.72483 | 0.728892 | 0.00406196 | 1 |
| 15 | interior | n_Propane | -0.01719 | -0.113797 | 0.0966073 | 0.848942 | 0.27356 | 0.381832 | 0.401097 | 0.0192654 | 1 |
| 9 | interior | n_Propane | -0.0170598 | -0.0417209 | 0.0246611 | 0.591096 | 0.44063 | 0.543284 | 0.614297 | 0.071013 | 1 |
| 13 | interior | n_Propane | -0.0170258 | -0.0959801 | 0.0789543 | 0.822611 | 0.368685 | 0.466216 | 0.487248 | 0.0210318 | 1 |
| 18 | interior | n_Butane | -0.0165334 | -0.0165334 | -0 | -0 | 0.72588 | 0.701418 | 0.726613 | 0.0251943 | 1 |
| 3 | interior | n_Propane | -0.0156014 | -0.292995 | 0.277394 | 0.946752 | 0.786689 | 0.86579 | 0.870239 | 0.00444888 | 1 |
| 14 | interior | n_Propane | -0.0155532 | -0.130292 | 0.114739 | 0.880628 | 0.328998 | 0.427275 | 0.440597 | 0.0133218 | 1 |
| 12 | interior | n_Propane | -0.0153758 | -0.0881777 | 0.0728019 | 0.825627 | 0.404821 | 0.49773 | 0.517352 | 0.0196224 | 1 |
| 10 | interior | n_Propane | -0.0152222 | -0.0281175 | 0.0128953 | 0.458623 | 0.425172 | 0.523582 | 0.63975 | 0.116167 | 1 |
| 2 | interior | n_Butane | 0.014971 | 0.0731379 | -0.0581669 | 0.795304 | 0.178474 | 0.177758 | 0.177574 | -0.000184292 | 1 |

## Top Required Target Conflicts
| stage_1based | stage_kind | component | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | equilibrium_transfer_lbmolps | cancellation_coverage | y | y_target | required_y_target_to_cancel_pre_rhs | required_target_delta | required_target_component_feasible |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 6 | interior | n_Propane | -0.0399001 | -0.0608212 | 0.0209211 | 0.343977 | 0.497099 | 0.639408 | 0.910815 | 0.271407 | 1 |
| 7 | interior | n_Propane | -0.0262852 | -0.0519399 | 0.0256547 | 0.49393 | 0.478565 | 0.595659 | 0.715631 | 0.119972 | 1 |
| 10 | interior | n_Propane | -0.0152222 | -0.0281175 | 0.0128953 | 0.458623 | 0.425172 | 0.523582 | 0.63975 | 0.116167 | 1 |
| 20 | bottom | n_Propane | 0 | 0 | 0 |  | 0.20727 | 0.110223 | 0.20727 | 0.0970472 | 1 |
| 17 | interior | n_Propane | 0.000923233 | 0.000923233 | 0 | -0 | 0.191831 | 0.281458 | 0.191791 | -0.0896673 | 1 |
| 20 | bottom | n_Butane | 0 | 0 | 0 |  | 0.71805 | 0.805762 | 0.71805 | -0.0877118 | 1 |
| 4 | interior | n_Butane | 0.278185 | 0.278185 | 0 | -0 | 0.324105 | 0.391206 | 0.310031 | -0.0811749 | 1 |
| 11 | interior | n_Propane | -0.0141447 | -0.0291649 | 0.0150202 | 0.515009 | 0.41534 | 0.501283 | 0.582216 | 0.0809335 | 1 |
| 4 | interior | n_Propane | -0.256099 | -0.256099 | -0 | -0 | 0.666846 | 0.60061 | 0.679803 | 0.0791935 | 1 |
| 9 | interior | n_Propane | -0.0170598 | -0.0417209 | 0.0246611 | 0.591096 | 0.44063 | 0.543284 | 0.614297 | 0.071013 | 1 |
| 8 | interior | n_Propane | -0.0206927 | -0.054207 | 0.0335143 | 0.618265 | 0.460778 | 0.56557 | 0.630273 | 0.0647023 | 1 |
| 17 | interior | n_Butane | -0.0205514 | -0.0205514 | -0 | -0 | 0.728438 | 0.666632 | 0.729332 | 0.0626992 | 1 |
| 5 | interior | n_Butane | 0.112582 | 0.112582 | 0 | -0 | 0.43812 | 0.487513 | 0.432545 | -0.0549678 | 1 |
| 5 | interior | n_Propane | -0.0886817 | -0.0886817 | -0 | -0 | 0.544208 | 0.498258 | 0.5486 | 0.0503416 | 1 |
| 18 | interior | n_Propane | 0.00152927 | 0.00152927 | 0 | -0 | 0.193946 | 0.234048 | 0.193878 | -0.0401697 | 1 |
| 17 | interior | n_Pentane | -0.0006069 | -0.0006069 | -0 | -0 | 0.0797307 | 0.0519091 | 0.0797571 | 0.027848 | 1 |
| 18 | interior | n_Butane | -0.0165334 | -0.0165334 | -0 | -0 | 0.72588 | 0.701418 | 0.726613 | 0.0251943 | 1 |
| 13 | interior | n_Propane | -0.0170258 | -0.0959801 | 0.0789543 | 0.822611 | 0.368685 | 0.466216 | 0.487248 | 0.0210318 | 1 |
| 16 | interior | n_Propane | -0.012297 | -0.077568 | 0.065271 | 0.841469 | 0.225097 | 0.331721 | 0.351809 | 0.0200877 | 1 |
| 12 | interior | n_Propane | -0.0153758 | -0.0881777 | 0.0728019 | 0.825627 | 0.404821 | 0.49773 | 0.517352 | 0.0196224 | 1 |

## Top Interior Final RHS Conflicts
| stage_1based | stage_kind | component | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | equilibrium_transfer_lbmolps | cancellation_coverage | y | y_target | required_y_target_to_cancel_pre_rhs | required_target_delta | required_target_component_feasible |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 4 | interior | n_Butane | 0.278185 | 0.278185 | 0 | -0 | 0.324105 | 0.391206 | 0.310031 | -0.0811749 | 1 |
| 4 | interior | n_Propane | -0.256099 | -0.256099 | -0 | -0 | 0.666846 | 0.60061 | 0.679803 | 0.0791935 | 1 |
| 5 | interior | n_Butane | 0.112582 | 0.112582 | 0 | -0 | 0.43812 | 0.487513 | 0.432545 | -0.0549678 | 1 |
| 5 | interior | n_Propane | -0.0886817 | -0.0886817 | -0 | -0 | 0.544208 | 0.498258 | 0.5486 | 0.0503416 | 1 |
| 6 | interior | n_Propane | -0.0399001 | -0.0608212 | 0.0209211 | 0.343977 | 0.497099 | 0.639408 | 0.910815 | 0.271407 | 1 |
| 2 | interior | n_Propane | -0.0290069 | -0.0906018 | 0.0615949 | 0.679842 | 0.820272 | 0.82103 | 0.821388 | 0.000357073 | 1 |
| 7 | interior | n_Propane | -0.0262852 | -0.0519399 | 0.0256547 | 0.49393 | 0.478565 | 0.595659 | 0.715631 | 0.119972 | 1 |
| 8 | interior | n_Propane | -0.0206927 | -0.054207 | 0.0335143 | 0.618265 | 0.460778 | 0.56557 | 0.630273 | 0.0647023 | 1 |
| 17 | interior | n_Butane | -0.0205514 | -0.0205514 | -0 | -0 | 0.728438 | 0.666632 | 0.729332 | 0.0626992 | 1 |
| 4 | interior | n_Pentane | 0.0203829 | 0.0203829 | -0 | 0 | 0.00904842 | 0.00818446 | 0.00801718 | -0.000167278 | 1 |
| 19 | interior | n_Butane | -0.0178828 | -0.0243037 | 0.00642093 | 0.264195 | 0.723372 | 0.72483 | 0.728892 | 0.00406196 | 1 |
| 15 | interior | n_Propane | -0.01719 | -0.113797 | 0.0966073 | 0.848942 | 0.27356 | 0.381832 | 0.401097 | 0.0192654 | 1 |
| 9 | interior | n_Propane | -0.0170598 | -0.0417209 | 0.0246611 | 0.591096 | 0.44063 | 0.543284 | 0.614297 | 0.071013 | 1 |
| 13 | interior | n_Propane | -0.0170258 | -0.0959801 | 0.0789543 | 0.822611 | 0.368685 | 0.466216 | 0.487248 | 0.0210318 | 1 |
| 18 | interior | n_Butane | -0.0165334 | -0.0165334 | -0 | -0 | 0.72588 | 0.701418 | 0.726613 | 0.0251943 | 1 |
| 3 | interior | n_Propane | -0.0156014 | -0.292995 | 0.277394 | 0.946752 | 0.786689 | 0.86579 | 0.870239 | 0.00444888 | 1 |
| 14 | interior | n_Propane | -0.0155532 | -0.130292 | 0.114739 | 0.880628 | 0.328998 | 0.427275 | 0.440597 | 0.0133218 | 1 |
| 12 | interior | n_Propane | -0.0153758 | -0.0881777 | 0.0728019 | 0.825627 | 0.404821 | 0.49773 | 0.517352 | 0.0196224 | 1 |
| 10 | interior | n_Propane | -0.0152222 | -0.0281175 | 0.0128953 | 0.458623 | 0.425172 | 0.523582 | 0.63975 | 0.116167 | 1 |
| 2 | interior | n_Butane | 0.014971 | 0.0731379 | -0.0581669 | 0.795304 | 0.178474 | 0.177758 | 0.177574 | -0.000184292 | 1 |

## Top Stage Conflicts
| stage_1based | stage_kind | max_abs_required_target_delta | max_abs_final_rhs_lbmolps |
|---|---|---|---|
| 4 | interior | 0.0811749 | 0.278185 |
| 5 | interior | 0.0549678 | 0.112582 |
| 6 | interior | 0.271407 | 0.0399001 |
| 2 | interior | 0.000357073 | 0.0290069 |
| 7 | interior | 0.119972 | 0.0262852 |
| 8 | interior | 0.0647023 | 0.0206927 |
| 17 | interior | 0.0896673 | 0.0205514 |
| 19 | interior | 0.00406196 | 0.0178828 |
| 15 | interior | 0.0192654 | 0.01719 |
| 9 | interior | 0.071013 | 0.0170598 |
| 13 | interior | 0.0210318 | 0.0170258 |
| 18 | interior | 0.0401697 | 0.0165334 |
| 3 | interior | 0.00444888 | 0.0156014 |
| 14 | interior | 0.0133218 | 0.0155532 |
| 12 | interior | 0.0196224 | 0.0153758 |
| 10 | interior | 0.116167 | 0.0152222 |
| 11 | interior | 0.0809335 | 0.0141447 |
| 16 | interior | 0.0200877 | 0.012297 |
| 1 | top | 0 | 0 |
| 20 | bottom | 0.0970472 | 0 |
