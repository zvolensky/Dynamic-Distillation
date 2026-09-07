# Vapor RHS Material Terms Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_dd044_exponential_eq_continue290s_topKc5_20260711\column_profile_20260711_095431.csv`
Time: `290` s

## Summary
| n_stages | max_relative_rhs_per_s | max_relative_rhs_per_s_interior | max_abs_final_rhs_lbmolps |
|---|---|---|---|
| 20 | 0.00237115 | 0.00237115 | 0.0226858 |

## Interpretation
- `final_rhs` is the live RHS contribution to explicit tray vapor component inventory.
- `pre_equilibrium_rhs` is transport/feed/terminal/holdup behavior before equilibrium transfer.
- Dominant terms identify whether the motion is transport, feed, terminal handling, holdup relaxation, or equilibrium transfer.

## Top Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 19 | n_Propane | 0.00237115 | -0.0226858 | 0.131291 | transport_in | 0.858729 | 0.858729 | -0.692073 | -0.153976 | 0 |
| 19 | n_Pentane | 0.00169833 | 0.00659168 | -0.0679849 | transport_out | -0.232748 | 0.176657 | -0.232748 | 0.0745766 | 0 |
| 18 | n_Butane | 0.000854804 | 0.0139582 | -0.0631172 | transport_out | -1.2536 | 1.20005 | -1.2536 | 0.0770754 | 0 |
| 19 | n_Butane | 0.000832892 | 0.0132062 | -0.0661937 | transport_out | -1.20005 | 1.19518 | -1.20005 | 0.0793998 | 0 |
| 17 | n_Butane | 0.000671986 | 0.0110512 | -0.00409249 | transport_in | 1.2536 | 1.2536 | -1.24898 | 0.0151437 | 0 |
| 17 | n_Pentane | 0.000668721 | -0.0021971 | 0.0574676 | transport_in | 0.243571 | 0.243571 | -0.184814 | -0.0596647 | 0 |
| 18 | n_Pentane | 0.000654521 | -0.00260395 | -0.0126807 | transport_out | -0.243571 | 0.232748 | -0.243571 | 0.0100768 | 0 |
| 16 | n_Butane | 0.000653167 | 0.0104699 | 0.0395416 | transport_in | 1.24898 | 1.24898 | -1.20145 | -0.0290717 | 0 |
| 18 | n_Propane | 0.000570413 | -0.00479098 | 0.0823612 | transport_in | 0.692073 | 0.692073 | -0.605096 | -0.0871522 | 0 |
| 7 | n_Butane | 0.000488865 | 0.00502478 | 0.0513311 | transport_in | 0.820456 | 0.820456 | -0.772765 | -0.0463063 | 0 |
| 8 | n_Butane | 0.000483826 | 0.00524051 | 0.03561 | transport_in | 0.850502 | 0.850502 | -0.820456 | -0.0303695 | 0 |
| 15 | n_Butane | 0.000472893 | 0.00682815 | 0.0623878 | transport_in | 1.20145 | 1.20145 | -1.12669 | -0.0555596 | 0 |
| 6 | n_Butane | 0.000470765 | 0.00442622 | 0.07793 | transport_in | 0.772765 | 0.772765 | -0.697252 | -0.0735038 | 0 |
| 7 | n_Pentane | 0.000464805 | -0.000639434 | 0.00706661 | transport_in | 0.0382101 | 0.0382101 | -0.0312909 | -0.00770605 | 0 |
| 9 | n_Butane | 0.000460772 | 0.00515951 | 0.0283083 | transport_in | 0.871119 | 0.871119 | -0.850502 | -0.0231488 | 0 |
| 8 | n_Pentane | 0.000450689 | -0.000657043 | 0.00674235 | transport_in | 0.0446933 | 0.0446933 | -0.0382101 | -0.0073994 | 0 |
| 6 | n_Pentane | 0.000431888 | -0.000556339 | 0.00746131 | transport_in | 0.0312909 | 0.0312909 | -0.0239125 | -0.00801765 | 0 |
| 5 | n_Butane | 0.000427241 | 0.00344281 | 0.114911 | transport_in | 0.697252 | 0.697252 | -0.585727 | -0.111468 | 0 |
| 14 | n_Butane | 0.000426816 | 0.0058106 | 0.0720113 | transport_in | 1.12669 | 1.12669 | -1.04508 | -0.0662007 | 0 |
| 10 | n_Butane | 0.000422645 | 0.00484963 | 0.0264945 | transport_in | 0.887314 | 0.887314 | -0.871119 | -0.0216449 | 0 |

## Top Interior Component Terms
| stage_1based | component | relative_rhs_per_s | final_rhs_lbmolps | pre_equilibrium_rhs_lbmolps | dominant_term | dominant_term_lbmolps | transport_in_lbmolps | transport_out_lbmolps | equilibrium_transfer_lbmolps | terminal_adjust_lbmolps |
|---|---|---|---|---|---|---|---|---|---|---|
| 19 | n_Propane | 0.00237115 | -0.0226858 | 0.131291 | transport_in | 0.858729 | 0.858729 | -0.692073 | -0.153976 | 0 |
| 19 | n_Pentane | 0.00169833 | 0.00659168 | -0.0679849 | transport_out | -0.232748 | 0.176657 | -0.232748 | 0.0745766 | 0 |
| 18 | n_Butane | 0.000854804 | 0.0139582 | -0.0631172 | transport_out | -1.2536 | 1.20005 | -1.2536 | 0.0770754 | 0 |
| 19 | n_Butane | 0.000832892 | 0.0132062 | -0.0661937 | transport_out | -1.20005 | 1.19518 | -1.20005 | 0.0793998 | 0 |
| 17 | n_Butane | 0.000671986 | 0.0110512 | -0.00409249 | transport_in | 1.2536 | 1.2536 | -1.24898 | 0.0151437 | 0 |
| 17 | n_Pentane | 0.000668721 | -0.0021971 | 0.0574676 | transport_in | 0.243571 | 0.243571 | -0.184814 | -0.0596647 | 0 |
| 18 | n_Pentane | 0.000654521 | -0.00260395 | -0.0126807 | transport_out | -0.243571 | 0.232748 | -0.243571 | 0.0100768 | 0 |
| 16 | n_Butane | 0.000653167 | 0.0104699 | 0.0395416 | transport_in | 1.24898 | 1.24898 | -1.20145 | -0.0290717 | 0 |
| 18 | n_Propane | 0.000570413 | -0.00479098 | 0.0823612 | transport_in | 0.692073 | 0.692073 | -0.605096 | -0.0871522 | 0 |
| 7 | n_Butane | 0.000488865 | 0.00502478 | 0.0513311 | transport_in | 0.820456 | 0.820456 | -0.772765 | -0.0463063 | 0 |
| 8 | n_Butane | 0.000483826 | 0.00524051 | 0.03561 | transport_in | 0.850502 | 0.850502 | -0.820456 | -0.0303695 | 0 |
| 15 | n_Butane | 0.000472893 | 0.00682815 | 0.0623878 | transport_in | 1.20145 | 1.20145 | -1.12669 | -0.0555596 | 0 |
| 6 | n_Butane | 0.000470765 | 0.00442622 | 0.07793 | transport_in | 0.772765 | 0.772765 | -0.697252 | -0.0735038 | 0 |
| 7 | n_Pentane | 0.000464805 | -0.000639434 | 0.00706661 | transport_in | 0.0382101 | 0.0382101 | -0.0312909 | -0.00770605 | 0 |
| 9 | n_Butane | 0.000460772 | 0.00515951 | 0.0283083 | transport_in | 0.871119 | 0.871119 | -0.850502 | -0.0231488 | 0 |
| 8 | n_Pentane | 0.000450689 | -0.000657043 | 0.00674235 | transport_in | 0.0446933 | 0.0446933 | -0.0382101 | -0.0073994 | 0 |
| 6 | n_Pentane | 0.000431888 | -0.000556339 | 0.00746131 | transport_in | 0.0312909 | 0.0312909 | -0.0239125 | -0.00801765 | 0 |
| 5 | n_Butane | 0.000427241 | 0.00344281 | 0.114911 | transport_in | 0.697252 | 0.697252 | -0.585727 | -0.111468 | 0 |
| 14 | n_Butane | 0.000426816 | 0.0058106 | 0.0720113 | transport_in | 1.12669 | 1.12669 | -1.04508 | -0.0662007 | 0 |
| 10 | n_Butane | 0.000422645 | 0.00484963 | 0.0264945 | transport_in | 0.887314 | 0.887314 | -0.871119 | -0.0216449 | 0 |

## Top Stage Terms
| stage_1based | max_abs_final_rhs_lbmolps | dominant_stage_term | dominant_stage_term_abs_lbmolps |
|---|---|---|---|
| 19 | 0.0226858 | transport_out | 1.20005 |
| 18 | 0.0139582 | transport_out | 1.2536 |
| 17 | 0.0110512 | transport_in | 1.2536 |
| 2 | 0.0110295 | transport_out | 1.95128 |
| 16 | 0.0104699 | transport_in | 1.24898 |
| 15 | 0.00682815 | transport_in | 1.20145 |
| 3 | 0.00604384 | transport_out | 1.76472 |
| 14 | 0.0058106 | transport_in | 1.12669 |
| 8 | 0.00524051 | transport_out | 1.14105 |
| 9 | 0.00515951 | transport_out | 1.09862 |
| 4 | 0.00503505 | transport_out | 1.57469 |
| 7 | 0.00502478 | transport_out | 1.19725 |
| 10 | 0.00484963 | transport_out | 1.06033 |
| 5 | 0.00447157 | transport_out | 1.40214 |
| 6 | 0.00442622 | transport_out | 1.27927 |
| 11 | 0.00433963 | transport_out | 1.01763 |
| 13 | 0.00431181 | transport_in | 1.04508 |
| 12 | 0.00385558 | transport_in | 0.973314 |
| 1 | 0 | transport_in | 1.95128 |
| 20 | 0 | transport_in | 1.78956 |
