# Vapor RHS Material Terms Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_liq_eq_vap_linearsteady_300s_eqcompguard_20260708\column_profile_20260708_081534.csv`
Time: `210` s

## Summary
| n_stages | max_relative_rhs_per_s | max_relative_rhs_per_s_interior | max_abs_final_rhs_lbmolps |
|---|---|---|---|
| 20 | 0.171033 | 0.171033 | 0.651469 |

## Interpretation
- `final_rhs` is the live RHS contribution to explicit tray vapor component inventory.
- `pre_equilibrium_rhs` is transport/feed/terminal/holdup behavior before equilibrium transfer.
- Dominant terms identify whether the motion is transport, feed, terminal handling, holdup relaxation, or equilibrium transfer.

## Top Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 15 | n_Propane | 0.171033 | -0.651469 | -0.32884 | transport_out | -0.660861 | 0.314769 | -0.660861 | -0.322629 | 0 |
| 15 | n_Pentane | 0.132135 | 0.197802 | 0.0791209 | transport_in | 0.192989 | 0.192989 | -0.11692 | 0.118681 | 0 |
| 15 | n_Butane | 0.0735656 | 0.516532 | 0.312584 | transport_in | 1.69222 | 1.69222 | -1.41661 | 0.203947 | 0 |
| 14 | n_Propane | 0.0135938 | -0.065801 | -0.259433 | transport_out | -0.917764 | 0.660861 | -0.917764 | 0.193632 | 0 |
| 16 | n_Propane | 0.0126017 | -0.0335031 | -0.0425558 | transport_out | -0.314769 | 0.272401 | -0.314769 | 0.00905273 | 0 |
| 14 | n_Pentane | 0.0120534 | 0.0159328 | 0.0397951 | transport_in | 0.11692 | 0.11692 | -0.0769133 | -0.0238623 | 0 |
| 18 | n_Propane | 0.00821759 | 0.0189158 | 0.00871082 | transport_in | 0.275219 | 0.275219 | -0.26443 | 0.010205 | 0 |
| 16 | n_Butane | 0.00793611 | 0.0787007 | 0.0901794 | transport_in | 1.78341 | 1.78341 | -1.69222 | -0.0114786 | 0 |
| 19 | n_Propane | 0.00609851 | 0.0142722 | 0.00769389 | transport_in | 0.284815 | 0.284815 | -0.275219 | 0.00657827 | 0 |
| 14 | n_Butane | 0.00562194 | 0.0340749 | 0.203844 | transport_in | 1.41661 | 1.41661 | -1.20944 | -0.169769 | 0 |
| 17 | n_Butane | 0.00350044 | -0.0353571 | -0.0169627 | transport_out | -1.78341 | 1.77285 | -1.78341 | -0.0183944 | 0 |
| 17 | n_Pentane | 0.00322461 | -0.0064288 | -0.0114004 | transport_out | -0.194722 | 0.18402 | -0.194722 | 0.00497159 | 0 |
| 19 | n_Pentane | 0.00309592 | -0.00585662 | -0.00234265 | transport_out | -0.183111 | 0.182034 | -0.183111 | -0.00351397 | 0 |
| 18 | n_Pentane | 0.00308972 | -0.00588897 | -0.00235559 | transport_out | -0.18402 | 0.183111 | -0.18402 | -0.00353338 | 0 |
| 19 | n_Butane | 0.00303078 | -0.0292675 | -0.0262032 | transport_out | -1.77764 | 1.76371 | -1.77764 | -0.0030643 | 0 |
| 10 | n_Pentane | 0.00242224 | -0.00276784 | 0.00553568 | transport_in | 0.0393181 | 0.0393181 | -0.0335633 | -0.00830352 | 0 |
| 16 | n_Pentane | 0.00200464 | 0.00404319 | 0.00161727 | transport_in | 0.194722 | 0.194722 | -0.192989 | 0.00242591 | 0 |
| 17 | n_Propane | 0.00187203 | 0.00447427 | -0.00894853 | transport_out | -0.272401 | 0.26443 | -0.272401 | 0.0134228 | 0 |
| 13 | n_Propane | 0.00168613 | -0.00890235 | -0.109114 | transport_out | -1.02374 | 0.917764 | -1.02374 | 0.100212 | 0 |
| 18 | n_Butane | 0.00162583 | -0.0158165 | -0.00914489 | transport_in | 1.77764 | 1.77764 | -1.77285 | -0.00667164 | 0 |

## Top Interior Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 15 | n_Propane | 0.171033 | -0.651469 | -0.32884 | transport_out | -0.660861 | 0.314769 | -0.660861 | -0.322629 | 0 |
| 15 | n_Pentane | 0.132135 | 0.197802 | 0.0791209 | transport_in | 0.192989 | 0.192989 | -0.11692 | 0.118681 | 0 |
| 15 | n_Butane | 0.0735656 | 0.516532 | 0.312584 | transport_in | 1.69222 | 1.69222 | -1.41661 | 0.203947 | 0 |
| 14 | n_Propane | 0.0135938 | -0.065801 | -0.259433 | transport_out | -0.917764 | 0.660861 | -0.917764 | 0.193632 | 0 |
| 16 | n_Propane | 0.0126017 | -0.0335031 | -0.0425558 | transport_out | -0.314769 | 0.272401 | -0.314769 | 0.00905273 | 0 |
| 14 | n_Pentane | 0.0120534 | 0.0159328 | 0.0397951 | transport_in | 0.11692 | 0.11692 | -0.0769133 | -0.0238623 | 0 |
| 18 | n_Propane | 0.00821759 | 0.0189158 | 0.00871082 | transport_in | 0.275219 | 0.275219 | -0.26443 | 0.010205 | 0 |
| 16 | n_Butane | 0.00793611 | 0.0787007 | 0.0901794 | transport_in | 1.78341 | 1.78341 | -1.69222 | -0.0114786 | 0 |
| 19 | n_Propane | 0.00609851 | 0.0142722 | 0.00769389 | transport_in | 0.284815 | 0.284815 | -0.275219 | 0.00657827 | 0 |
| 14 | n_Butane | 0.00562194 | 0.0340749 | 0.203844 | transport_in | 1.41661 | 1.41661 | -1.20944 | -0.169769 | 0 |
| 17 | n_Butane | 0.00350044 | -0.0353571 | -0.0169627 | transport_out | -1.78341 | 1.77285 | -1.78341 | -0.0183944 | 0 |
| 17 | n_Pentane | 0.00322461 | -0.0064288 | -0.0114004 | transport_out | -0.194722 | 0.18402 | -0.194722 | 0.00497159 | 0 |
| 19 | n_Pentane | 0.00309592 | -0.00585662 | -0.00234265 | transport_out | -0.183111 | 0.182034 | -0.183111 | -0.00351397 | 0 |
| 18 | n_Pentane | 0.00308972 | -0.00588897 | -0.00235559 | transport_out | -0.18402 | 0.183111 | -0.18402 | -0.00353338 | 0 |
| 19 | n_Butane | 0.00303078 | -0.0292675 | -0.0262032 | transport_out | -1.77764 | 1.76371 | -1.77764 | -0.0030643 | 0 |
| 10 | n_Pentane | 0.00242224 | -0.00276784 | 0.00553568 | transport_in | 0.0393181 | 0.0393181 | -0.0335633 | -0.00830352 | 0 |
| 16 | n_Pentane | 0.00200464 | 0.00404319 | 0.00161727 | transport_in | 0.194722 | 0.194722 | -0.192989 | 0.00242591 | 0 |
| 17 | n_Propane | 0.00187203 | 0.00447427 | -0.00894853 | transport_out | -0.272401 | 0.26443 | -0.272401 | 0.0134228 | 0 |
| 13 | n_Propane | 0.00168613 | -0.00890235 | -0.109114 | transport_out | -1.02374 | 0.917764 | -1.02374 | 0.100212 | 0 |
| 18 | n_Butane | 0.00162583 | -0.0158165 | -0.00914489 | transport_in | 1.77764 | 1.77764 | -1.77285 | -0.00667164 | 0 |

## Top Stage Terms
| stage_1based | max_abs_final_rhs_lbmolps | dominant_stage_term | dominant_stage_term_abs_lbmolps |
|---|---|---|---|
| 15 | 0.651469 | transport_in | 1.69222 |
| 16 | 0.0787007 | transport_in | 1.78341 |
| 14 | 0.065801 | transport_in | 1.41661 |
| 17 | 0.0353571 | transport_out | 1.78341 |
| 19 | 0.0292675 | transport_out | 1.77764 |
| 18 | 0.0189158 | transport_in | 1.77764 |
| 2 | 0.0155684 | transport_in | 2.02082 |
| 3 | 0.0112258 | transport_out | 2.02082 |
| 4 | 0.0104912 | transport_out | 1.77749 |
| 5 | 0.00923858 | transport_out | 1.56909 |
| 13 | 0.00890235 | transport_in | 1.20944 |
| 6 | 0.00838296 | transport_out | 1.41166 |
| 7 | 0.00778577 | transport_out | 1.30568 |
| 10 | 0.00772919 | transport_out | 1.13144 |
| 8 | 0.00741185 | transport_out | 1.23774 |
| 9 | 0.00699379 | transport_out | 1.19251 |
| 11 | 0.00682456 | transport_out | 1.12328 |
| 12 | 0.00678427 | transport_in | 1.1161 |
| 1 | 0 | transport_in | 2.00613 |
| 20 | 0 | transport_in | 1.7973 |
