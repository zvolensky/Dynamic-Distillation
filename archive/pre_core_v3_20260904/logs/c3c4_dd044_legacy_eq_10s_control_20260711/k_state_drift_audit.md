# K-State Drift Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_dd044_legacy_eq_10s_control_20260711\column_profile_20260711_094259.csv`

## Gate
No gate limits were supplied.

## Summary
| first_time_s | final_time_s | first_max_abs_K_state_minus_K_thermo | min_max_abs_K_state_minus_K_thermo | final_max_abs_K_state_minus_K_thermo | peak_max_abs_K_state_minus_K_thermo | final_max_abs_ln_K_state_over_K_thermo | positive_abs_delta_trend_from_min | final_worst_delta_stage_1based | final_worst_delta_component |
|---|---|---|---|---|---|---|---|---|---|
| 2 | 10 | 0.869343 | 0.869343 | 0.873517 | 0.873517 | 1.35524 | 0.00417418 | 3 | n_Pentane |

## Summary By Time
| time_s | max_abs_K_state_minus_K_thermo | max_abs_ln_K_state_over_K_thermo | worst_delta_stage_1based | worst_delta_component | worst_ln_stage_1based | worst_ln_component |
|---|---|---|---|---|---|---|
| 2 | 0.869343 | 1.3509 | 3 | n_Pentane | 3 | n_Pentane |
| 4 | 0.870404 | 1.35201 | 3 | n_Pentane | 3 | n_Pentane |
| 6 | 0.871465 | 1.35311 | 3 | n_Pentane | 3 | n_Pentane |
| 8 | 0.872507 | 1.35419 | 3 | n_Pentane | 3 | n_Pentane |
| 10 | 0.873517 | 1.35524 | 3 | n_Pentane | 3 | n_Pentane |

## Top Absolute K Delta Records
| time_s | stage_1based | component | K_state | K_thermo | K_state_minus_K_thermo | abs_K_state_minus_K_thermo | K_state_over_K_thermo | x | y | y_target |
|---|---|---|---|---|---|---|---|---|---|---|
| 10 | 3 | n_Pentane | 1.17706 | 0.303547 | 0.873517 | 0.873517 | 3.8777 | 0.052889 | 0.0622537 | 0.0168589 |
| 8 | 3 | n_Pentane | 1.17613 | 0.303625 | 0.872507 | 0.872507 | 3.87363 | 0.0529489 | 0.0622749 | 0.0168773 |
| 6 | 3 | n_Pentane | 1.17517 | 0.303706 | 0.871465 | 0.871465 | 3.86944 | 0.0530105 | 0.0622964 | 0.0168963 |
| 4 | 3 | n_Pentane | 1.17419 | 0.303787 | 0.870404 | 0.870404 | 3.86517 | 0.0530732 | 0.0623181 | 0.0169156 |
| 2 | 3 | n_Pentane | 1.17321 | 0.303869 | 0.869343 | 0.869343 | 3.86091 | 0.0531363 | 0.0623402 | 0.0169349 |
| 10 | 4 | n_Pentane | 1.15421 | 0.316342 | 0.837868 | 0.837868 | 3.64862 | 0.0538367 | 0.0621389 | 0.0177599 |
| 8 | 4 | n_Pentane | 1.15326 | 0.316424 | 0.836836 | 0.836836 | 3.64466 | 0.0538983 | 0.0621587 | 0.0177796 |
| 6 | 4 | n_Pentane | 1.15232 | 0.316507 | 0.835809 | 0.835809 | 3.64073 | 0.0539599 | 0.0621788 | 0.0177993 |
| 4 | 4 | n_Pentane | 1.15138 | 0.31659 | 0.834791 | 0.834791 | 3.63682 | 0.0540214 | 0.0621992 | 0.0178191 |
| 2 | 4 | n_Pentane | 1.15045 | 0.316672 | 0.833782 | 0.833782 | 3.63295 | 0.0540829 | 0.0622199 | 0.0178387 |
| 10 | 5 | n_Pentane | 1.13341 | 0.328775 | 0.804636 | 0.804636 | 3.44738 | 0.0547329 | 0.0620348 | 0.0186534 |
| 8 | 5 | n_Pentane | 1.13255 | 0.328865 | 0.803684 | 0.803684 | 3.44381 | 0.054791 | 0.0620534 | 0.0186734 |

## Top Absolute ln Ratio Records
| time_s | stage_1based | component | K_state | K_thermo | K_state_over_K_thermo | abs_ln_K_state_over_K_thermo | x | y | y_target |
|---|---|---|---|---|---|---|---|---|---|
| 10 | 3 | n_Pentane | 1.17706 | 0.303547 | 3.8777 | 1.35524 | 0.052889 | 0.0622537 | 0.0168589 |
| 8 | 3 | n_Pentane | 1.17613 | 0.303625 | 3.87363 | 1.35419 | 0.0529489 | 0.0622749 | 0.0168773 |
| 6 | 3 | n_Pentane | 1.17517 | 0.303706 | 3.86944 | 1.35311 | 0.0530105 | 0.0622964 | 0.0168963 |
| 4 | 3 | n_Pentane | 1.17419 | 0.303787 | 3.86517 | 1.35201 | 0.0530732 | 0.0623181 | 0.0169156 |
| 2 | 3 | n_Pentane | 1.17321 | 0.303869 | 3.86091 | 1.3509 | 0.0531363 | 0.0623402 | 0.0169349 |
| 10 | 4 | n_Pentane | 1.15421 | 0.316342 | 3.64862 | 1.29435 | 0.0538367 | 0.0621389 | 0.0177599 |
| 8 | 4 | n_Pentane | 1.15326 | 0.316424 | 3.64466 | 1.29326 | 0.0538983 | 0.0621587 | 0.0177796 |
| 6 | 4 | n_Pentane | 1.15232 | 0.316507 | 3.64073 | 1.29218 | 0.0539599 | 0.0621788 | 0.0177993 |
| 4 | 4 | n_Pentane | 1.15138 | 0.31659 | 3.63682 | 1.29111 | 0.0540214 | 0.0621992 | 0.0178191 |
| 2 | 4 | n_Pentane | 1.15045 | 0.316672 | 3.63295 | 1.29005 | 0.0540829 | 0.0622199 | 0.0178387 |
| 10 | 5 | n_Pentane | 1.13341 | 0.328775 | 3.44738 | 1.23761 | 0.0547329 | 0.0620348 | 0.0186534 |
| 8 | 5 | n_Pentane | 1.13255 | 0.328865 | 3.44381 | 1.23658 | 0.054791 | 0.0620534 | 0.0186734 |
