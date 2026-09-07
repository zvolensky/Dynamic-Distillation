# Vapor RHS Material Terms Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_liq_eq_vap_linearsteady_300s_eqcompguard_signaware_20260708\column_profile_20260708_081858.csv`
Time: `270` s

## Summary
| n_stages | max_relative_rhs_per_s | max_relative_rhs_per_s_interior | max_abs_final_rhs_lbmolps |
|---|---|---|---|
| 20 | 0.139135 | 0.139135 | 0.633469 |

## Interpretation
- `final_rhs` is the live RHS contribution to explicit tray vapor component inventory.
- `pre_equilibrium_rhs` is transport/feed/terminal/holdup behavior before equilibrium transfer.
- Dominant terms identify whether the motion is transport, feed, terminal handling, holdup relaxation, or equilibrium transfer.

## Top Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 5 | n_Butane | 0.139135 | 0.633469 | 0.444087 | transport_in | 1.37409 | 1.37409 | -0.953866 | 0.189382 | 0 |
| 5 | n_Propane | 0.0928343 | -0.569398 | -0.379599 | transport_out | -1.37822 | 0.964135 | -1.37822 | -0.189799 | 0 |
| 4 | n_Butane | 0.0229464 | 0.0707431 | 0.383277 | transport_in | 0.953866 | 0.953866 | -0.574501 | -0.312534 | 0 |
| 9 | n_Pentane | 0.0139452 | 0.0195628 | 0.0294817 | transport_in | 0.129122 | 0.129122 | -0.0994474 | -0.00991896 | 0 |
| 5 | n_Pentane | 0.0130065 | 0.0133797 | 0.012962 | transport_in | 0.0204712 | 0.0204712 | -0.00770187 | 0.000417678 | 0 |
| 4 | n_Propane | 0.0124489 | -0.0937581 | -0.410952 | transport_out | -1.80143 | 1.37822 | -1.80143 | 0.317194 | 0 |
| 10 | n_Pentane | 0.0116995 | -0.0178659 | 0.0357318 | transport_in | 0.164937 | 0.164937 | -0.129122 | -0.0535977 | 0 |
| 15 | n_Butane | 0.00945905 | -0.0670099 | -0.0611595 | transport_out | -1.74029 | 1.6763 | -1.74029 | -0.00585032 | 0 |
| 9 | n_Propane | 0.00877211 | -0.0317858 | -0.046789 | transport_out | -0.647668 | 0.602137 | -0.647668 | 0.0150032 | 0 |
| 11 | n_Pentane | 0.00857802 | -0.0144225 | 0.028845 | transport_in | 0.194249 | 0.194249 | -0.164937 | -0.0432675 | 0 |
| 16 | n_Propane | 0.00599633 | 0.0169101 | 0.0112734 | transport_in | 0.438399 | 0.438399 | -0.433415 | 0.00563669 | 0 |
| 14 | n_Butane | 0.00599145 | -0.0455789 | -0.0431036 | transport_in | 1.74029 | 1.74029 | -1.73884 | -0.00247533 | 0 |
| 8 | n_Pentane | 0.00508378 | 0.00633378 | 0.0371275 | transport_in | 0.0994474 | 0.0994474 | -0.062659 | -0.0307937 | 0 |
| 10 | n_Propane | 0.0047836 | 0.0165411 | -0.0343412 | transport_out | -0.602137 | 0.568181 | -0.602137 | 0.0508823 | 0 |
| 19 | n_Butane | 0.00391029 | -0.0312441 | -0.051581 | transport_out | -1.62575 | 1.56746 | -1.62575 | 0.0203369 | 0 |
| 18 | n_Butane | 0.00330132 | -0.027027 | -0.0257386 | transport_out | -1.64674 | 1.62575 | -1.64674 | -0.00128845 | 0 |
| 6 | n_Butane | 0.00326592 | 0.020458 | 0.120626 | transport_in | 1.48168 | 1.48168 | -1.37409 | -0.100168 | 0 |
| 17 | n_Butane | 0.00310062 | -0.0257387 | -0.0242496 | transport_out | -1.66237 | 1.64674 | -1.66237 | -0.00148906 | 0 |
| 7 | n_Pentane | 0.00302892 | 0.00347682 | 0.0248151 | transport_in | 0.062659 | 0.062659 | -0.0379872 | -0.0213383 | 0 |
| 13 | n_Propane | 0.00299036 | 0.00821582 | 0.00547721 | transport_in | 0.432964 | 0.432964 | -0.420122 | 0.00273861 | 0 |

## Top Interior Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 5 | n_Butane | 0.139135 | 0.633469 | 0.444087 | transport_in | 1.37409 | 1.37409 | -0.953866 | 0.189382 | 0 |
| 5 | n_Propane | 0.0928343 | -0.569398 | -0.379599 | transport_out | -1.37822 | 0.964135 | -1.37822 | -0.189799 | 0 |
| 4 | n_Butane | 0.0229464 | 0.0707431 | 0.383277 | transport_in | 0.953866 | 0.953866 | -0.574501 | -0.312534 | 0 |
| 9 | n_Pentane | 0.0139452 | 0.0195628 | 0.0294817 | transport_in | 0.129122 | 0.129122 | -0.0994474 | -0.00991896 | 0 |
| 5 | n_Pentane | 0.0130065 | 0.0133797 | 0.012962 | transport_in | 0.0204712 | 0.0204712 | -0.00770187 | 0.000417678 | 0 |
| 4 | n_Propane | 0.0124489 | -0.0937581 | -0.410952 | transport_out | -1.80143 | 1.37822 | -1.80143 | 0.317194 | 0 |
| 10 | n_Pentane | 0.0116995 | -0.0178659 | 0.0357318 | transport_in | 0.164937 | 0.164937 | -0.129122 | -0.0535977 | 0 |
| 15 | n_Butane | 0.00945905 | -0.0670099 | -0.0611595 | transport_out | -1.74029 | 1.6763 | -1.74029 | -0.00585032 | 0 |
| 9 | n_Propane | 0.00877211 | -0.0317858 | -0.046789 | transport_out | -0.647668 | 0.602137 | -0.647668 | 0.0150032 | 0 |
| 11 | n_Pentane | 0.00857802 | -0.0144225 | 0.028845 | transport_in | 0.194249 | 0.194249 | -0.164937 | -0.0432675 | 0 |
| 16 | n_Propane | 0.00599633 | 0.0169101 | 0.0112734 | transport_in | 0.438399 | 0.438399 | -0.433415 | 0.00563669 | 0 |
| 14 | n_Butane | 0.00599145 | -0.0455789 | -0.0431036 | transport_in | 1.74029 | 1.74029 | -1.73884 | -0.00247533 | 0 |
| 8 | n_Pentane | 0.00508378 | 0.00633378 | 0.0371275 | transport_in | 0.0994474 | 0.0994474 | -0.062659 | -0.0307937 | 0 |
| 10 | n_Propane | 0.0047836 | 0.0165411 | -0.0343412 | transport_out | -0.602137 | 0.568181 | -0.602137 | 0.0508823 | 0 |
| 19 | n_Butane | 0.00391029 | -0.0312441 | -0.051581 | transport_out | -1.62575 | 1.56746 | -1.62575 | 0.0203369 | 0 |
| 18 | n_Butane | 0.00330132 | -0.027027 | -0.0257386 | transport_out | -1.64674 | 1.62575 | -1.64674 | -0.00128845 | 0 |
| 6 | n_Butane | 0.00326592 | 0.020458 | 0.120626 | transport_in | 1.48168 | 1.48168 | -1.37409 | -0.100168 | 0 |
| 17 | n_Butane | 0.00310062 | -0.0257387 | -0.0242496 | transport_out | -1.66237 | 1.64674 | -1.66237 | -0.00148906 | 0 |
| 7 | n_Pentane | 0.00302892 | 0.00347682 | 0.0248151 | transport_in | 0.062659 | 0.062659 | -0.0379872 | -0.0213383 | 0 |
| 13 | n_Propane | 0.00299036 | 0.00821582 | 0.00547721 | transport_in | 0.432964 | 0.432964 | -0.420122 | 0.00273861 | 0 |

## Top Stage Terms
| stage_1based | max_abs_final_rhs_lbmolps | dominant_stage_term | dominant_stage_term_abs_lbmolps |
|---|---|---|---|
| 5 | 0.633469 | transport_out | 1.37822 |
| 4 | 0.0937581 | transport_out | 1.80143 |
| 15 | 0.0670099 | transport_out | 1.74029 |
| 14 | 0.0455789 | transport_in | 1.74029 |
| 9 | 0.0317858 | transport_in | 1.59205 |
| 19 | 0.0312441 | transport_out | 1.62575 |
| 18 | 0.027027 | transport_out | 1.64674 |
| 17 | 0.0257387 | transport_out | 1.66237 |
| 3 | 0.0226881 | transport_out | 2.06699 |
| 6 | 0.020458 | transport_in | 1.48168 |
| 2 | 0.0184259 | transport_in | 2.06699 |
| 10 | 0.0178659 | transport_out | 1.59205 |
| 16 | 0.0169101 | transport_out | 1.6763 |
| 11 | 0.0144225 | transport_out | 1.5791 |
| 13 | 0.0128197 | transport_in | 1.73884 |
| 12 | 0.00921713 | transport_in | 1.71843 |
| 8 | 0.00633378 | transport_in | 1.58558 |
| 7 | 0.00582349 | transport_in | 1.55819 |
| 1 | 0 | transport_in | 2.05609 |
| 20 | 0 | transport_in | 1.7973 |
