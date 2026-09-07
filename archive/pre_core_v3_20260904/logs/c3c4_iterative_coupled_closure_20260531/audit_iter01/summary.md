# Column Initialization Residual Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_iterative_coupled_closure_20260531\c3c4_coupled_iter01_blend0.0500.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `parity`
- Pressure model: `spec`
- Vapor flow model: `profile`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.030022615 1/s`
- Worst absolute state rate: `0.22876972 per s`
- Max tray total material residual: `0.09 lbmol/h`
- Total state inventory residual: `0.004 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_V` | 0.030022615 | 0.22659022 | 2 | n-Butane |
| `tray_L` | 0.015681089 | 0.22876972 | 19 | n-Propane |
| `bottom_L` | 0.00023951455 | 0.014487897 | 21 | n-Propane |
| `top_L` | 2.6116199e-10 | 1.7010492e-08 | 0 | n-Pentane |
| `bottom_T_f` | 0 | 0 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |
| `tray_T_f` | 0 | 0 | 1 |  |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_V` | 2 | n-Butane | 0.1502205 | 0.030022615 | 4.003578 |
| 2 | `tray_V` | 3 | n-Butane | 0.1636964 | 0.024820414 | 5.5952325 |
| 3 | `tray_V` | 11 | n-Pentane | 0.02848882 | 0.019134422 | 0.48887805 |
| 4 | `tray_V` | 4 | n-Butane | 0.14738502 | 0.01714514 | 7.5963146 |
| 5 | `tray_L` | 19 | n-Propane | 0.11347187 | 0.015681089 | 6.2362237 |
| 6 | `tray_V` | 19 | n-Pentane | 0.052947022 | 0.015092048 | 2.5082729 |
| 7 | `tray_L` | 3 | n-Butane | -0.16594794 | 0.013996952 | 10.856005 |
| 8 | `tray_V` | 18 | n-Propane | -0.12098594 | 0.0133765 | 8.0446633 |
| 9 | `tray_L` | 18 | n-Propane | 0.12039331 | 0.012784992 | 8.4167682 |
| 10 | `tray_L` | 11 | n-Pentane | -0.028578827 | 0.01232726 | 1.3183438 |
| 11 | `tray_V` | 10 | n-Pentane | 0.015660358 | 0.011969418 | 0.30836416 |
| 12 | `tray_V` | 5 | n-Butane | 0.11357992 | 0.011014229 | 9.3121082 |
| 13 | `tray_L` | 2 | n-Butane | -0.093615084 | 0.010993623 | 7.5153984 |
| 14 | `tray_V` | 17 | n-Propane | -0.12260811 | 0.010896948 | 10.251601 |
| 15 | `tray_L` | 17 | n-Propane | 0.12198447 | 0.010237278 | 10.915714 |
| 16 | `tray_V` | 3 | n-Propane | -0.22623107 | 0.0098836164 | 21.889503 |
| 17 | `tray_L` | 4 | n-Butane | -0.14880686 | 0.0097986571 | 14.186454 |
| 18 | `tray_V` | 4 | n-Propane | -0.18703359 | 0.0093272451 | 19.052393 |
| 19 | `tray_L` | 4 | n-Propane | 0.18863667 | 0.0093055983 | 19.27131 |
| 20 | `tray_L` | 3 | n-Propane | 0.22876972 | 0.0092786801 | 23.655416 |
