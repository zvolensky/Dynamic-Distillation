# K-State Drift Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_dd044_exponential_eq_10s_smoke_20260711\column_profile_20260711_094127.csv`

## Gate
No gate limits were supplied.

## Summary
| first_time_s | final_time_s | first_max_abs_K_state_minus_K_thermo | min_max_abs_K_state_minus_K_thermo | final_max_abs_K_state_minus_K_thermo | peak_max_abs_K_state_minus_K_thermo | final_max_abs_ln_K_state_over_K_thermo | positive_abs_delta_trend_from_min | final_worst_delta_stage_1based | final_worst_delta_component |
|---|---|---|---|---|---|---|---|---|---|
| 2 | 10 | 0.797162 | 0.797162 | 0.804045 | 0.804045 | 0.762502 | 0.00688314 | 16 | n_Propane |

## Summary By Time
| time_s | max_abs_K_state_minus_K_thermo | max_abs_ln_K_state_over_K_thermo | worst_delta_stage_1based | worst_delta_component | worst_ln_stage_1based | worst_ln_component |
|---|---|---|---|---|---|---|
| 2 | 0.797162 | 0.759999 | 16 | n_Propane | 16 | n_Pentane |
| 4 | 0.80044 | 0.764994 | 16 | n_Propane | 16 | n_Pentane |
| 6 | 0.801385 | 0.764223 | 16 | n_Propane | 16 | n_Pentane |
| 8 | 0.802781 | 0.763595 | 16 | n_Propane | 16 | n_Pentane |
| 10 | 0.804045 | 0.762502 | 16 | n_Propane | 16 | n_Pentane |

## Top Absolute K Delta Records
| time_s | stage_1based | component | K_state | K_thermo | K_state_minus_K_thermo | abs_K_state_minus_K_thermo | K_state_over_K_thermo | x | y | y_target |
|---|---|---|---|---|---|---|---|---|---|---|
| 10 | 16 | n_Propane | 1.00084 | 1.80489 | -0.804045 | 0.804045 | 0.554518 | 0.395753 | 0.396086 | 0.395825 |
| 8 | 16 | n_Propane | 1.00068 | 1.80346 | -0.802781 | 0.802781 | 0.554866 | 0.39651 | 0.396779 | 0.396569 |
| 6 | 16 | n_Propane | 1.00052 | 1.80191 | -0.801385 | 0.801385 | 0.555257 | 0.397166 | 0.397373 | 0.397211 |
| 4 | 16 | n_Propane | 1.00042 | 1.80086 | -0.80044 | 0.80044 | 0.555522 | 0.397709 | 0.397874 | 0.397744 |
| 2 | 16 | n_Propane | 1.00286 | 1.80002 | -0.797162 | 0.797162 | 0.557138 | 0.397914 | 0.399053 | 0.398158 |
| 10 | 17 | n_Propane | 0.999889 | 1.77984 | -0.779952 | 0.779952 | 0.561786 | 0.397024 | 0.39698 | 0.397014 |
| 8 | 17 | n_Propane | 0.999788 | 1.77947 | -0.779686 | 0.779686 | 0.561845 | 0.397217 | 0.397133 | 0.397198 |
| 6 | 17 | n_Propane | 0.999698 | 1.77913 | -0.779436 | 0.779436 | 0.561901 | 0.397397 | 0.397277 | 0.39737 |
| 4 | 17 | n_Propane | 0.999667 | 1.77881 | -0.779141 | 0.779141 | 0.561987 | 0.397566 | 0.397434 | 0.397537 |
| 2 | 17 | n_Propane | 1.00236 | 1.77848 | -0.776128 | 0.776128 | 0.563602 | 0.397496 | 0.398433 | 0.397704 |
| 4 | 18 | n_Propane | 1.00014 | 1.7653 | -0.765166 | 0.765166 | 0.566552 | 0.393417 | 0.39347 | 0.393426 |
| 6 | 18 | n_Propane | 1.00029 | 1.76456 | -0.764268 | 0.764268 | 0.566879 | 0.393807 | 0.393922 | 0.393826 |

## Top Absolute ln Ratio Records
| time_s | stage_1based | component | K_state | K_thermo | K_state_over_K_thermo | abs_ln_K_state_over_K_thermo | x | y | y_target |
|---|---|---|---|---|---|---|---|---|---|
| 4 | 16 | n_Pentane | 0.998751 | 0.464756 | 2.14898 | 0.764994 | 0.0824242 | 0.0823213 | 0.0824021 |
| 6 | 16 | n_Pentane | 0.998545 | 0.465018 | 2.14732 | 0.764223 | 0.0826849 | 0.0825645 | 0.0826589 |
| 8 | 16 | n_Pentane | 0.998233 | 0.465165 | 2.14598 | 0.763595 | 0.0829916 | 0.082845 | 0.0829599 |
| 10 | 16 | n_Pentane | 0.99792 | 0.465527 | 2.14363 | 0.762502 | 0.0833389 | 0.0831655 | 0.0833013 |
| 2 | 16 | n_Pentane | 0.993334 | 0.464549 | 2.13827 | 0.759999 | 0.0823119 | 0.0817632 | 0.0821943 |
| 4 | 17 | n_Pentane | 1.00031 | 0.470132 | 2.12771 | 0.755048 | 0.0820813 | 0.0821065 | 0.0820869 |
| 6 | 17 | n_Pentane | 1.00025 | 0.470211 | 2.12723 | 0.754821 | 0.0821632 | 0.0821834 | 0.0821677 |
| 8 | 17 | n_Pentane | 1.00006 | 0.470292 | 2.12647 | 0.754463 | 0.0822519 | 0.082257 | 0.082253 |
| 10 | 17 | n_Pentane | 0.999859 | 0.470379 | 2.12565 | 0.754076 | 0.082348 | 0.0823364 | 0.0823454 |
| 2 | 17 | n_Pentane | 0.994562 | 0.470055 | 2.11584 | 0.749454 | 0.0821071 | 0.0816606 | 0.082008 |
| 6 | 18 | n_Pentane | 0.999157 | 0.476225 | 2.09808 | 0.741021 | 0.0831756 | 0.0831055 | 0.0831639 |
| 10 | 18 | n_Pentane | 0.998495 | 0.475922 | 2.09802 | 0.740996 | 0.0828678 | 0.0827431 | 0.0828469 |
