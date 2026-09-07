# Vapor RHS Material Terms Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_liq_eq_vap_linearsteady_60s_dt005_20260707\column_profile_20260707_172123.csv`
Time: `45` s

## Summary
| n_stages | max_relative_rhs_per_s | max_relative_rhs_per_s_interior | max_abs_final_rhs_lbmolps |
|---|---|---|---|
| 20 | 0.140396 | 0.140396 | 0.391925 |

## Interpretation
- `final_rhs` is the live RHS contribution to explicit tray vapor component inventory.
- `pre_equilibrium_rhs` is transport/feed/terminal/holdup behavior before equilibrium transfer.
- Dominant terms identify whether the motion is transport, feed, terminal handling, holdup relaxation, or equilibrium transfer.

## Top Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 3 | n_Butane | 0.140396 | -0.391925 | 0.23255 | transport_in | 0.77447 | 0.77447 | -0.550391 | -0.624475 | 0 |
| 3 | n_Propane | 0.0374415 | 0.378566 | -0.246563 | transport_out | -2.79898 | 2.50934 | -2.79898 | 0.625129 | 0 |
| 12 | n_Butane | 0.00202825 | -0.0125365 | 0.129978 | transport_out | -1.49173 | 1.07778 | -1.49173 | -0.142515 | 0 |
| 12 | n_Propane | 0.00195455 | -0.0124643 | -0.226571 | transport_out | -1.54818 | 0.998426 | -1.54818 | 0.214106 | 0 |
| 4 | n_Propane | 0.00136469 | -0.0126875 | -0.269603 | transport_out | -2.50934 | 2.21366 | -2.50934 | 0.256915 | 0 |
| 11 | n_Butane | 0.00123558 | -0.00746988 | 0.00784369 | transport_in | 1.49173 | 1.49173 | -1.4883 | -0.0153136 | 0 |
| 4 | n_Butane | 0.00106901 | -0.00380645 | 0.252316 | transport_in | 1.01874 | 1.01874 | -0.77447 | -0.256122 | 0 |
| 19 | n_Propane | 0.00102723 | -0.00301495 | -0.131121 | transport_out | -0.349528 | 0.219412 | -0.349528 | 0.128106 | 0 |

## Top Interior Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 3 | n_Butane | 0.140396 | -0.391925 | 0.23255 | transport_in | 0.77447 | 0.77447 | -0.550391 | -0.624475 | 0 |
| 3 | n_Propane | 0.0374415 | 0.378566 | -0.246563 | transport_out | -2.79898 | 2.50934 | -2.79898 | 0.625129 | 0 |
| 12 | n_Butane | 0.00202825 | -0.0125365 | 0.129978 | transport_out | -1.49173 | 1.07778 | -1.49173 | -0.142515 | 0 |
| 12 | n_Propane | 0.00195455 | -0.0124643 | -0.226571 | transport_out | -1.54818 | 0.998426 | -1.54818 | 0.214106 | 0 |
| 4 | n_Propane | 0.00136469 | -0.0126875 | -0.269603 | transport_out | -2.50934 | 2.21366 | -2.50934 | 0.256915 | 0 |
| 11 | n_Butane | 0.00123558 | -0.00746988 | 0.00784369 | transport_in | 1.49173 | 1.49173 | -1.4883 | -0.0153136 | 0 |
| 4 | n_Butane | 0.00106901 | -0.00380645 | 0.252316 | transport_in | 1.01874 | 1.01874 | -0.77447 | -0.256122 | 0 |
| 19 | n_Propane | 0.00102723 | -0.00301495 | -0.131121 | transport_out | -0.349528 | 0.219412 | -0.349528 | 0.128106 | 0 |

## Top Stage Terms
| stage_1based | max_abs_final_rhs_lbmolps | dominant_stage_term | dominant_stage_term_abs_lbmolps |
|---|---|---|---|
| 3 | 0.391925 | transport_out | 2.79898 |
| 4 | 0.0126875 | transport_out | 2.50934 |
| 12 | 0.0125365 | transport_out | 1.54818 |
| 11 | 0.00746988 | transport_out | 1.61751 |
| 5 | 0.006598 | transport_out | 2.21366 |
| 2 | 0.00629942 | transport_out | 2.8505 |
| 10 | 0.0060947 | transport_out | 1.65684 |
| 9 | 0.00506818 | transport_out | 1.69821 |
