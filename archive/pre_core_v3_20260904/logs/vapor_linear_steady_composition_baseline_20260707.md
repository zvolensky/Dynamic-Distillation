# Vapor Linear Steady Composition Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_interior_liq_vapor_eq_align_rhs_terms_20260707\column_profile_20260707_153257.csv`
Time: `0.2` s

## Summary
| n_stages | n_components | max_abs_y_linear_steady_minus_y | max_abs_y_linear_steady_minus_y_interior | max_abs_y_linear_steady_minus_y_target |
|---|---|---|---|---|
| 20 | 3 | 0.0269866 | 0.00482808 | 0.00831429 |

## Interpretation
- `y_linear_steady` is the vapor composition that would zero the linearized component balance using logged transport and equilibrium target terms.
- If `y_linear_steady` differs from `y_target`, forcing vapor directly to equilibrium cannot also zero transport.
- This is a diagnostic using fixed logged traffic and target values; it is not a full nonlinear solve.

## Top Component Deltas
| stage_1based | stage_kind | component | y | y_target | y_linear_steady | y_linear_steady_minus_y | y_linear_steady_minus_y_target | transport_in_lbmolps | V_out_lbmolps |
|---|---|---|---|---|---|---|---|---|---|
| 20 | bottom | n_Pentane | 0.111002 | 0.0840153 | 0.0840153 | -0.0269866 | 0 | 0.187401 | 2.23056 |
| 20 | bottom | n_Butane | 0.779919 | 0.805762 | 0.805762 | 0.0258431 | 1.11022e-16 | 1.7973 | 2.23056 |
| 3 | interior | n_Propane | 0.860775 | 0.864262 | 0.855947 | -0.00482808 | -0.00831429 | 1.82653 | 2.40366 |
| 3 | interior | n_Butane | 0.1392 | 0.135715 | 0.144023 | 0.00482308 | 0.00830824 | 0.537559 | 2.40366 |
| 4 | interior | n_Propane | 0.772545 | 0.7758 | 0.76811 | -0.00443535 | -0.0076909 | 1.60543 | 2.3643 |
| 4 | interior | n_Butane | 0.227365 | 0.224112 | 0.231787 | 0.0044223 | 0.00767537 | 0.717542 | 2.3643 |
| 5 | interior | n_Propane | 0.690932 | 0.693508 | 0.687456 | -0.00347566 | -0.00605193 | 1.44088 | 2.32358 |
| 5 | interior | n_Butane | 0.308809 | 0.306239 | 0.312257 | 0.00344711 | 0.00601788 | 0.856465 | 2.32358 |
| 19 | interior | n_Propane | 0.170058 | 0.172008 | 0.166912 | -0.00314581 | -0.0050957 | 0.243309 | 2.23631 |
| 15 | interior | n_Propane | 0.380586 | 0.383122 | 0.378036 | -0.00254957 | -0.00508568 | 0.735888 | 2.25106 |
| 16 | interior | n_Propane | 0.327523 | 0.329714 | 0.325021 | -0.00250202 | -0.00469347 | 0.609533 | 2.24683 |
| 6 | interior | n_Propane | 0.6268 | 0.62864 | 0.624372 | -0.00242829 | -0.00426854 | 1.32888 | 2.29879 |

## Top Interior Component Deltas
| stage_1based | stage_kind | component | y | y_target | y_linear_steady | y_linear_steady_minus_y | y_linear_steady_minus_y_target | transport_in_lbmolps | V_out_lbmolps |
|---|---|---|---|---|---|---|---|---|---|
| 3 | interior | n_Propane | 0.860775 | 0.864262 | 0.855947 | -0.00482808 | -0.00831429 | 1.82653 | 2.40366 |
| 3 | interior | n_Butane | 0.1392 | 0.135715 | 0.144023 | 0.00482308 | 0.00830824 | 0.537559 | 2.40366 |
| 4 | interior | n_Propane | 0.772545 | 0.7758 | 0.76811 | -0.00443535 | -0.0076909 | 1.60543 | 2.3643 |
| 4 | interior | n_Butane | 0.227365 | 0.224112 | 0.231787 | 0.0044223 | 0.00767537 | 0.717542 | 2.3643 |
| 5 | interior | n_Propane | 0.690932 | 0.693508 | 0.687456 | -0.00347566 | -0.00605193 | 1.44088 | 2.32358 |
| 5 | interior | n_Butane | 0.308809 | 0.306239 | 0.312257 | 0.00344711 | 0.00601788 | 0.856465 | 2.32358 |
| 19 | interior | n_Propane | 0.170058 | 0.172008 | 0.166912 | -0.00314581 | -0.0050957 | 0.243309 | 2.23631 |
| 15 | interior | n_Propane | 0.380586 | 0.383122 | 0.378036 | -0.00254957 | -0.00508568 | 0.735888 | 2.25106 |
| 16 | interior | n_Propane | 0.327523 | 0.329714 | 0.325021 | -0.00250202 | -0.00469347 | 0.609533 | 2.24683 |
| 6 | interior | n_Propane | 0.6268 | 0.62864 | 0.624372 | -0.00242829 | -0.00426854 | 1.32888 | 2.29879 |
| 17 | interior | n_Propane | 0.271605 | 0.27376 | 0.269219 | -0.00238574 | -0.00454058 | 0.487855 | 2.24419 |
| 6 | interior | n_Butane | 0.372571 | 0.370744 | 0.374944 | 0.0023722 | 0.00419915 | 0.952672 | 2.29879 |

## Top Stage Deltas
| stage_1based | stage_kind | max_abs_y_ss_minus_y | max_abs_y_ss_minus_y_target |
|---|---|---|---|
| 20 | bottom | 0.0269866 | 1.11022e-16 |
| 3 | interior | 0.00482808 | 0.00831429 |
| 4 | interior | 0.00443535 | 0.0076909 |
| 5 | interior | 0.00347566 | 0.00605193 |
| 19 | interior | 0.00314581 | 0.0050957 |
| 15 | interior | 0.00254957 | 0.00508568 |
| 16 | interior | 0.00250202 | 0.00469347 |
| 6 | interior | 0.00242829 | 0.00426854 |
| 17 | interior | 0.00238574 | 0.00454058 |
| 18 | interior | 0.00228847 | 0.00398762 |
| 14 | interior | 0.0022567 | 0.00454737 |
| 13 | interior | 0.00188949 | 0.003878 |
