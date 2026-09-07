# Vapor RHS Material Terms Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_liq_eq_vap_linearsteady_1300s_eqcompguard_m1_fine_20260709\column_profile_20260709_083905.csv`
Time: `1205` s

## Summary
| n_stages | max_relative_rhs_per_s | max_relative_rhs_per_s_interior | max_abs_final_rhs_lbmolps |
|---|---|---|---|
| 20 | 0.00617214 | 0.00617214 | 0.110249 |

## Interpretation
- `final_rhs` is the live RHS contribution to explicit tray vapor component inventory.
- `pre_equilibrium_rhs` is transport/feed/terminal/holdup behavior before equilibrium transfer.
- Dominant terms identify whether the motion is transport, feed, terminal handling, holdup relaxation, or equilibrium transfer.

## Top Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 12 | n_Butane | 0.00617214 | -0.0964238 | -0.0964238 | transport_out | -0.821332 | 0.633687 | -0.821332 | 0 | 0 |
| 12 | n_Propane | 0.00607199 | -0.110249 | -0.110249 | transport_out | -0.963693 | 0.746413 | -0.963693 | 0 | 0 |
| 12 | n_Pentane | 0.00416256 | -0.0112825 | -0.0112825 | transport_out | -0.0960758 | 0.0741227 | -0.0960758 | 0 | 0 |
| 13 | n_Propane | 0.00268008 | 0.0504644 | 0.0504644 | transport_in | 0.76052 | 0.76052 | -0.746413 | -0 | 0 |
| 13 | n_Butane | 0.00249012 | 0.0401826 | 0.0401826 | transport_in | 0.643004 | 0.643004 | -0.633687 | 0 | 0 |
| 14 | n_Propane | 0.00175229 | 0.03314 | 0.03314 | transport_out | -0.76052 | 0.76041 | -0.76052 | -0 | 0 |
| 13 | n_Pentane | 0.00169169 | 0.00468691 | 0.00468691 | transport_in | 0.0751991 | 0.0751991 | -0.0741227 | 0 | 0 |
| 14 | n_Butane | 0.00157329 | 0.0254001 | 0.0254001 | transport_out | -0.643004 | 0.640291 | -0.643004 | 0 | 0 |
| 11 | n_Propane | 0.00141149 | 0.0268339 | 0.0268339 | transport_in | 0.963693 | 0.963693 | -0.952958 | 0 | 0 |
| 10 | n_Propane | 0.00126873 | 0.0241387 | 0.0241387 | transport_in | 0.952958 | 0.952958 | -0.943297 | 0 | 0 |
| 15 | n_Propane | 0.0012683 | 0.0239133 | 0.0239133 | transport_out | -0.76041 | 0.749559 | -0.76041 | -0 | 0 |
| 7 | n_Propane | 0.00126055 | 0.0237323 | 0.0237323 | transport_out | -0.848668 | 0.844653 | -0.848668 | 0 | 0 |
| 6 | n_Propane | 0.00125611 | 0.0236128 | 0.0236128 | transport_out | -0.855625 | 0.848668 | -0.855625 | 0 | 0 |
| 8 | n_Propane | 0.00125323 | 0.0236362 | 0.0236362 | transport_out | -0.844653 | 0.842409 | -0.844653 | 0 | 0 |
| 11 | n_Butane | 0.00121434 | 0.0199236 | 0.0199236 | transport_in | 0.821332 | 0.821332 | -0.815179 | -0 | 0 |
| 17 | n_Propane | 0.00118669 | 0.023815 | 0.023815 | transport_in | 1.05771 | 1.05771 | -1.01924 | -0 | 0 |
| 18 | n_Propane | 0.00117789 | 0.0236271 | 0.0236271 | transport_in | 1.10239 | 1.10239 | -1.05771 | -0 | 0 |
| 19 | n_Propane | 0.00116726 | 0.023446 | 0.023446 | transport_in | 1.1565 | 1.1565 | -1.10239 | -0 | 0 |
| 9 | n_Propane | 0.00116634 | 0.0232338 | 0.0232338 | transport_in | 0.943297 | 0.943297 | -0.842409 | 0 | 0 |
| 4 | n_Propane | 0.00116062 | 0.0227903 | 0.0227903 | transport_in | 0.877959 | 0.877959 | -0.858189 | 0 | 0 |

## Top Interior Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 12 | n_Butane | 0.00617214 | -0.0964238 | -0.0964238 | transport_out | -0.821332 | 0.633687 | -0.821332 | 0 | 0 |
| 12 | n_Propane | 0.00607199 | -0.110249 | -0.110249 | transport_out | -0.963693 | 0.746413 | -0.963693 | 0 | 0 |
| 12 | n_Pentane | 0.00416256 | -0.0112825 | -0.0112825 | transport_out | -0.0960758 | 0.0741227 | -0.0960758 | 0 | 0 |
| 13 | n_Propane | 0.00268008 | 0.0504644 | 0.0504644 | transport_in | 0.76052 | 0.76052 | -0.746413 | -0 | 0 |
| 13 | n_Butane | 0.00249012 | 0.0401826 | 0.0401826 | transport_in | 0.643004 | 0.643004 | -0.633687 | 0 | 0 |
| 14 | n_Propane | 0.00175229 | 0.03314 | 0.03314 | transport_out | -0.76052 | 0.76041 | -0.76052 | -0 | 0 |
| 13 | n_Pentane | 0.00169169 | 0.00468691 | 0.00468691 | transport_in | 0.0751991 | 0.0751991 | -0.0741227 | 0 | 0 |
| 14 | n_Butane | 0.00157329 | 0.0254001 | 0.0254001 | transport_out | -0.643004 | 0.640291 | -0.643004 | 0 | 0 |
| 11 | n_Propane | 0.00141149 | 0.0268339 | 0.0268339 | transport_in | 0.963693 | 0.963693 | -0.952958 | 0 | 0 |
| 10 | n_Propane | 0.00126873 | 0.0241387 | 0.0241387 | transport_in | 0.952958 | 0.952958 | -0.943297 | 0 | 0 |
| 15 | n_Propane | 0.0012683 | 0.0239133 | 0.0239133 | transport_out | -0.76041 | 0.749559 | -0.76041 | -0 | 0 |
| 7 | n_Propane | 0.00126055 | 0.0237323 | 0.0237323 | transport_out | -0.848668 | 0.844653 | -0.848668 | 0 | 0 |
| 6 | n_Propane | 0.00125611 | 0.0236128 | 0.0236128 | transport_out | -0.855625 | 0.848668 | -0.855625 | 0 | 0 |
| 8 | n_Propane | 0.00125323 | 0.0236362 | 0.0236362 | transport_out | -0.844653 | 0.842409 | -0.844653 | 0 | 0 |
| 11 | n_Butane | 0.00121434 | 0.0199236 | 0.0199236 | transport_in | 0.821332 | 0.821332 | -0.815179 | -0 | 0 |
| 17 | n_Propane | 0.00118669 | 0.023815 | 0.023815 | transport_in | 1.05771 | 1.05771 | -1.01924 | -0 | 0 |
| 18 | n_Propane | 0.00117789 | 0.0236271 | 0.0236271 | transport_in | 1.10239 | 1.10239 | -1.05771 | -0 | 0 |
| 19 | n_Propane | 0.00116726 | 0.023446 | 0.023446 | transport_in | 1.1565 | 1.1565 | -1.10239 | -0 | 0 |
| 9 | n_Propane | 0.00116634 | 0.0232338 | 0.0232338 | transport_in | 0.943297 | 0.943297 | -0.842409 | 0 | 0 |
| 4 | n_Propane | 0.00116062 | 0.0227903 | 0.0227903 | transport_in | 0.877959 | 0.877959 | -0.858189 | 0 | 0 |

## Top Stage Terms
| stage_1based | max_abs_final_rhs_lbmolps | dominant_stage_term | dominant_stage_term_abs_lbmolps |
|---|---|---|---|
| 12 | 0.110249 | transport_out | 0.963693 |
| 13 | 0.0504644 | transport_in | 0.76052 |
| 14 | 0.03314 | transport_out | 0.76052 |
| 2 | 0.0278535 | transport_in | 0.841116 |
| 11 | 0.0268339 | transport_in | 0.963693 |
| 10 | 0.0241387 | transport_in | 0.952958 |
| 16 | 0.0240024 | transport_in | 1.01924 |
| 15 | 0.0239133 | transport_out | 0.76041 |
| 17 | 0.023815 | transport_in | 1.05771 |
| 7 | 0.0237323 | transport_out | 0.848668 |
| 8 | 0.0236362 | transport_out | 0.844653 |
| 18 | 0.0236271 | transport_in | 1.10239 |
| 6 | 0.0236128 | transport_out | 0.855625 |
| 19 | 0.023446 | transport_in | 1.1565 |
| 9 | 0.0232338 | transport_in | 0.943297 |
| 4 | 0.0227903 | transport_in | 0.877959 |
| 3 | 0.0226816 | transport_in | 0.858189 |
| 5 | 0.0215827 | transport_out | 0.877959 |
| 1 | 0 | transport_in | 0.820684 |
| 20 | 0 | transport_in | 1.7973 |
