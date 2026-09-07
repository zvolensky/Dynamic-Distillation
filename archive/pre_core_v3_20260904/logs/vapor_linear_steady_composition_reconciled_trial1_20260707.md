# Vapor Linear Steady Composition Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_vapor_material_reconciled_trial1_smoke_20260707\column_profile_20260707_154658.csv`
Time: `0.2` s

## Summary
| n_stages | n_components | max_abs_y_linear_steady_minus_y | max_abs_y_linear_steady_minus_y_interior | max_abs_y_linear_steady_minus_y_target |
|---|---|---|---|---|
| 20 | 3 | 0.012844 | 0.012844 | 0.00972507 |

## Interpretation
- `y_linear_steady` is the vapor composition that would zero the linearized component balance using logged transport and equilibrium target terms.
- If `y_linear_steady` differs from `y_target`, forcing vapor directly to equilibrium cannot also zero transport.
- This is a diagnostic using fixed logged traffic and target values; it is not a full nonlinear solve.

## Top Component Deltas
| stage_1based | stage_kind | component | y | y_target | y_linear_steady | y_linear_steady_minus_y | y_linear_steady_minus_y_target | transport_in_lbmolps | V_out_lbmolps |
|---|---|---|---|---|---|---|---|---|---|
| 7 | interior | n_Propane | 0.589371 | 0.606414 | 0.602215 | 0.012844 | -0.00419878 | 1.27414 | 2.28413 |
| 7 | interior | n_Butane | 0.409237 | 0.39239 | 0.396432 | -0.0128056 | 0.00404144 | 0.993749 | 2.28413 |
| 8 | interior | n_Propane | 0.560173 | 0.576089 | 0.572927 | 0.0127535 | -0.00316198 | 1.22729 | 2.27455 |
| 6 | interior | n_Butane | 0.365939 | 0.347675 | 0.353265 | -0.0126736 | 0.00558992 | 0.934752 | 2.29988 |
| 6 | interior | n_Propane | 0.633448 | 0.651789 | 0.646121 | 0.0126729 | -0.00566766 | 1.3462 | 2.29988 |
| 8 | interior | n_Butane | 0.436898 | 0.421406 | 0.42428 | -0.0126182 | 0.00287461 | 1.02738 | 2.27455 |
| 9 | interior | n_Propane | 0.541244 | 0.556295 | 0.553674 | 0.0124296 | -0.00262099 | 1.19231 | 2.26754 |
| 5 | interior | n_Butane | 0.303675 | 0.284053 | 0.291485 | -0.0121904 | 0.0074318 | 0.841615 | 2.32706 |
| 5 | interior | n_Propane | 0.696079 | 0.715732 | 0.708264 | 0.0121851 | -0.00746786 | 1.45685 | 2.32706 |
| 9 | interior | n_Butane | 0.453083 | 0.438771 | 0.440954 | -0.0121289 | 0.00218303 | 1.04643 | 2.26754 |
| 10 | interior | n_Propane | 0.527379 | 0.541985 | 0.53931 | 0.0119313 | -0.0026743 | 1.15472 | 2.26082 |
| 11 | interior | n_Propane | 0.512437 | 0.525677 | 0.524044 | 0.0116064 | -0.00163276 | 1.13832 | 2.25339 |

## Top Interior Component Deltas
| stage_1based | stage_kind | component | y | y_target | y_linear_steady | y_linear_steady_minus_y | y_linear_steady_minus_y_target | transport_in_lbmolps | V_out_lbmolps |
|---|---|---|---|---|---|---|---|---|---|
| 7 | interior | n_Propane | 0.589371 | 0.606414 | 0.602215 | 0.012844 | -0.00419878 | 1.27414 | 2.28413 |
| 7 | interior | n_Butane | 0.409237 | 0.39239 | 0.396432 | -0.0128056 | 0.00404144 | 0.993749 | 2.28413 |
| 8 | interior | n_Propane | 0.560173 | 0.576089 | 0.572927 | 0.0127535 | -0.00316198 | 1.22729 | 2.27455 |
| 6 | interior | n_Butane | 0.365939 | 0.347675 | 0.353265 | -0.0126736 | 0.00558992 | 0.934752 | 2.29988 |
| 6 | interior | n_Propane | 0.633448 | 0.651789 | 0.646121 | 0.0126729 | -0.00566766 | 1.3462 | 2.29988 |
| 8 | interior | n_Butane | 0.436898 | 0.421406 | 0.42428 | -0.0126182 | 0.00287461 | 1.02738 | 2.27455 |
| 9 | interior | n_Propane | 0.541244 | 0.556295 | 0.553674 | 0.0124296 | -0.00262099 | 1.19231 | 2.26754 |
| 5 | interior | n_Butane | 0.303675 | 0.284053 | 0.291485 | -0.0121904 | 0.0074318 | 0.841615 | 2.32706 |
| 5 | interior | n_Propane | 0.696079 | 0.715732 | 0.708264 | 0.0121851 | -0.00746786 | 1.45685 | 2.32706 |
| 9 | interior | n_Butane | 0.453083 | 0.438771 | 0.440954 | -0.0121289 | 0.00218303 | 1.04643 | 2.26754 |
| 10 | interior | n_Propane | 0.527379 | 0.541985 | 0.53931 | 0.0119313 | -0.0026743 | 1.15472 | 2.26082 |
| 11 | interior | n_Propane | 0.512437 | 0.525677 | 0.524044 | 0.0116064 | -0.00163276 | 1.13832 | 2.25339 |

## Top Stage Deltas
| stage_1based | stage_kind | max_abs_y_ss_minus_y | max_abs_y_ss_minus_y_target |
|---|---|---|---|
| 7 | interior | 0.012844 | 0.00419878 |
| 8 | interior | 0.0127535 | 0.00316198 |
| 6 | interior | 0.0126736 | 0.00566766 |
| 9 | interior | 0.0124296 | 0.00262099 |
| 5 | interior | 0.0121904 | 0.00746786 |
| 10 | interior | 0.0119313 | 0.0026743 |
| 11 | interior | 0.0116064 | 0.00163276 |
| 4 | interior | 0.0113718 | 0.00911817 |
| 20 | bottom | 0.0110905 | 0.00154718 |
| 3 | interior | 0.0104199 | 0.00972507 |
| 12 | interior | 0.0102013 | 0.00444119 |
| 13 | interior | 0.0101642 | 0.00516274 |
