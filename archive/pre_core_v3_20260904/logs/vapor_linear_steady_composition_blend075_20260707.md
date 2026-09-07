# Vapor Linear Steady Composition Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_liq_eq_vap_eq_blend075_rhs_terms_20260707\column_profile_20260707_160811.csv`
Time: `0.2` s

## Summary
| n_stages | n_components | max_abs_y_linear_steady_minus_y | max_abs_y_linear_steady_minus_y_interior | max_abs_y_linear_steady_minus_y_target |
|---|---|---|---|---|
| 20 | 3 | 0.0269786 | 0.00483049 | 0.00831347 |

## Interpretation
- `y_linear_steady` is the vapor composition that would zero the linearized component balance using logged transport and equilibrium target terms.
- If `y_linear_steady` differs from `y_target`, forcing vapor directly to equilibrium cannot also zero transport.
- This is a diagnostic using fixed logged traffic and target values; it is not a full nonlinear solve.

## Top Component Deltas
| stage_1based | stage_kind | component | y | y_target | y_linear_steady | y_linear_steady_minus_y | y_linear_steady_minus_y_target | transport_in_lbmolps | V_out_lbmolps |
|---|---|---|---|---|---|---|---|---|---|
| 20 | bottom | n_Pentane | 0.110994 | 0.0840153 | 0.0840153 | -0.0269786 | 0 | 0.187401 | 2.23056 |
| 20 | bottom | n_Butane | 0.779951 | 0.805762 | 0.805762 | 0.0258106 | 1.11022e-16 | 1.7973 | 2.23056 |
| 3 | interior | n_Propane | 0.860779 | 0.864262 | 0.855949 | -0.00483049 | -0.00831347 | 1.82652 | 2.40512 |
| 3 | interior | n_Butane | 0.139195 | 0.135715 | 0.144022 | 0.00482659 | 0.00830702 | 0.537515 | 2.40512 |
| 4 | interior | n_Propane | 0.772555 | 0.775802 | 0.768113 | -0.00444233 | -0.00768889 | 1.60546 | 2.36426 |
| 4 | interior | n_Butane | 0.22735 | 0.22411 | 0.231783 | 0.00443246 | 0.00767249 | 0.717455 | 2.36426 |
| 5 | interior | n_Propane | 0.690954 | 0.693511 | 0.687463 | -0.00349136 | -0.00604857 | 1.44095 | 2.32354 |
| 5 | interior | n_Butane | 0.308777 | 0.306234 | 0.312247 | 0.00347008 | 0.00601298 | 0.856318 | 2.32354 |
| 19 | interior | n_Propane | 0.169879 | 0.171962 | 0.166868 | -0.00301032 | -0.00509402 | 0.243254 | 2.23627 |
| 15 | interior | n_Propane | 0.381142 | 0.38322 | 0.378166 | -0.00297576 | -0.00505373 | 0.736845 | 2.25093 |
| 16 | interior | n_Propane | 0.327967 | 0.329795 | 0.32512 | -0.00284769 | -0.00467558 | 0.610178 | 2.2467 |
| 15 | interior | n_Butane | 0.580107 | 0.578184 | 0.582867 | 0.00275998 | 0.00468303 | 1.41404 | 2.25093 |

## Top Interior Component Deltas
| stage_1based | stage_kind | component | y | y_target | y_linear_steady | y_linear_steady_minus_y | y_linear_steady_minus_y_target | transport_in_lbmolps | V_out_lbmolps |
|---|---|---|---|---|---|---|---|---|---|
| 3 | interior | n_Propane | 0.860779 | 0.864262 | 0.855949 | -0.00483049 | -0.00831347 | 1.82652 | 2.40512 |
| 3 | interior | n_Butane | 0.139195 | 0.135715 | 0.144022 | 0.00482659 | 0.00830702 | 0.537515 | 2.40512 |
| 4 | interior | n_Propane | 0.772555 | 0.775802 | 0.768113 | -0.00444233 | -0.00768889 | 1.60546 | 2.36426 |
| 4 | interior | n_Butane | 0.22735 | 0.22411 | 0.231783 | 0.00443246 | 0.00767249 | 0.717455 | 2.36426 |
| 5 | interior | n_Propane | 0.690954 | 0.693511 | 0.687463 | -0.00349136 | -0.00604857 | 1.44095 | 2.32354 |
| 5 | interior | n_Butane | 0.308777 | 0.306234 | 0.312247 | 0.00347008 | 0.00601298 | 0.856318 | 2.32354 |
| 19 | interior | n_Propane | 0.169879 | 0.171962 | 0.166868 | -0.00301032 | -0.00509402 | 0.243254 | 2.23627 |
| 15 | interior | n_Propane | 0.381142 | 0.38322 | 0.378166 | -0.00297576 | -0.00505373 | 0.736845 | 2.25093 |
| 16 | interior | n_Propane | 0.327967 | 0.329795 | 0.32512 | -0.00284769 | -0.00467558 | 0.610178 | 2.2467 |
| 15 | interior | n_Butane | 0.580107 | 0.578184 | 0.582867 | 0.00275998 | 0.00468303 | 1.41404 | 2.25093 |
| 14 | interior | n_Propane | 0.428605 | 0.430438 | 0.425933 | -0.0026718 | -0.0045049 | 0.857924 | 2.25558 |
| 17 | interior | n_Propane | 0.271905 | 0.273818 | 0.269277 | -0.00262876 | -0.00454127 | 0.487944 | 2.24408 |

## Top Stage Deltas
| stage_1based | stage_kind | max_abs_y_ss_minus_y | max_abs_y_ss_minus_y_target |
|---|---|---|---|
| 20 | bottom | 0.0269786 | 1.11022e-16 |
| 3 | interior | 0.00483049 | 0.00831347 |
| 4 | interior | 0.00444233 | 0.00768889 |
| 5 | interior | 0.00349136 | 0.00604857 |
| 19 | interior | 0.00301032 | 0.00509402 |
| 15 | interior | 0.00297576 | 0.00505373 |
| 16 | interior | 0.00284769 | 0.00467558 |
| 14 | interior | 0.0026718 | 0.0045049 |
| 17 | interior | 0.00262876 | 0.00454127 |
| 6 | interior | 0.00245683 | 0.00426397 |
| 18 | interior | 0.00234021 | 0.00400293 |
| 13 | interior | 0.00228102 | 0.00383513 |
