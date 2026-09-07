# Column Initialization Residual Audit

- Excel: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_model_consistent_seed_candidate_stage4_bottomL_boundary.xlsx`
- Thermo: `table`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.0091490957 1/s`
- Worst absolute state rate: `428.83719 per s`
- Max tray total material residual: `333.69985 lbmol/h`
- Total state inventory residual: `305.61272 lbmol/h`

## Top Boundary Diagnostics

- Total condenser boundary energy residual: `1.8189894e-12 Btu/s`
- Total condenser boundary energy residual relative scale: `1.2399208e-16`
- Total condenser boundary energy owner: `1`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_L` | 0.0091490957 | 0.10616391 | 19 | n-Pentane |
| `tray_T_f` | 0.0053762129 | 0.66647412 | 2 |  |
| `bottom_L` | 0.0051170409 | 0.39157627 | 21 | n-Propane |
| `tray_V` | 0.0048085771 | 0.0063905447 | 8 | n-Pentane |
| `top_L` | 0.0023329585 | 0.78115878 | 0 | n-Butane |
| `tray_EL_BTU` | 0.0017024574 | 428.83719 | 2 |  |
| `tray_EV_BTU` | 0.00076777799 | 32.657577 | 19 |  |
| `bottom_T_f` | 0.00023763218 | 0.052685499 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_L` | 19 | n-Pentane | 0.02790137 | 0.0091490957 | 2.0496315 |
| 2 | `tray_L` | 18 | n-Pentane | 0.026618156 | 0.0071683638 | 2.713282 |
| 3 | `tray_L` | 17 | n-Pentane | 0.024605294 | 0.0056301715 | 3.3702565 |
| 4 | `tray_T_f` | 2 |  | -0.66647412 | 0.0053762129 | 122.96721 |
| 5 | `bottom_L` | 21 | n-Propane | 0.19674982 | 0.0051170409 | 37.449921 |
| 6 | `tray_V` | 8 | n-Pentane | 0.0050415719 | 0.0048085771 | 0.048454008 |
| 7 | `tray_V` | 7 | n-Pentane | 0.0049280483 | 0.0048006903 | 0.026529109 |
| 8 | `tray_V` | 9 | n-Pentane | 0.0049923051 | 0.0046606979 | 0.07114968 |
| 9 | `tray_L` | 9 | n-Pentane | -0.0070763742 | 0.004517809 | 0.56632879 |
| 10 | `tray_V` | 10 | n-Pentane | 0.0048923149 | 0.0044725818 | 0.093845835 |
| 11 | `tray_V` | 11 | n-Pentane | 0.0047729093 | 0.0042758123 | 0.11625791 |
| 12 | `tray_L` | 16 | n-Pentane | 0.020447291 | 0.0042605252 | 3.799242 |
| 13 | `tray_V` | 6 | n-Pentane | 0.0041681591 | 0.0041341793 | 0.008219225 |
| 14 | `tray_V` | 12 | n-Pentane | 0.004648052 | 0.004084877 | 0.13786831 |
| 15 | `tray_L` | 8 | n-Pentane | -0.0052045466 | 0.0039068061 | 0.33217428 |
| 16 | `tray_V` | 13 | n-Pentane | 0.0045077034 | 0.0038873559 | 0.15958083 |
| 17 | `tray_V` | 14 | n-Pentane | 0.0043458482 | 0.0036803955 | 0.18081011 |
| 18 | `tray_L` | 10 | n-Pentane | -0.0063992009 | 0.0036044616 | 0.77535558 |
| 19 | `tray_L` | 4 | n-Propane | 0.10330623 | 0.0035723951 | 27.917919 |
| 20 | `tray_L` | 5 | n-Propane | 0.090046688 | 0.0035296227 | 24.511704 |
