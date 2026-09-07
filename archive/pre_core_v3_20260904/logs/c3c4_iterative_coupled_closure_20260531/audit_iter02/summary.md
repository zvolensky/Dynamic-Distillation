# Column Initialization Residual Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_iterative_coupled_closure_20260531\c3c4_coupled_iter02_blend0.0625.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `parity`
- Pressure model: `spec`
- Vapor flow model: `profile`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.026254829 1/s`
- Worst absolute state rate: `0.21786027 per s`
- Max tray total material residual: `0.09 lbmol/h`
- Total state inventory residual: `0.004 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_V` | 0.026254829 | 0.21288519 | 19 | n-Pentane |
| `tray_L` | 0.015883159 | 0.21786027 | 2 | n-Pentane |
| `bottom_L` | 0.00046663383 | 0.055506942 | 21 | n-Pentane |
| `top_L` | 1.2091073e-10 | 1.5947336e-08 | 0 | n-Pentane |
| `bottom_T_f` | 0 | 0 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |
| `tray_T_f` | 0 | 0 | 1 |  |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_V` | 19 | n-Pentane | 0.093984955 | 0.026254829 | 2.5797207 |
| 2 | `tray_V` | 2 | n-Butane | 0.1369345 | 0.021714533 | 5.3061224 |
| 3 | `tray_V` | 3 | n-Butane | 0.15027767 | 0.019647307 | 6.6487671 |
| 4 | `tray_V` | 11 | n-Pentane | 0.026595955 | 0.01665135 | 0.59722514 |
| 5 | `tray_L` | 2 | n-Pentane | 0.016072951 | 0.015883159 | 0.011949208 |
| 6 | `tray_V` | 4 | n-Butane | 0.13616125 | 0.01435973 | 8.4821598 |
| 7 | `tray_L` | 3 | n-Butane | -0.1550625 | 0.013530566 | 10.460163 |
| 8 | `tray_V` | 18 | n-Propane | -0.11328428 | 0.012907022 | 7.7769496 |
| 9 | `tray_L` | 11 | n-Pentane | -0.026787027 | 0.011933778 | 1.2446393 |
| 10 | `tray_L` | 19 | n-Propane | 0.10599865 | 0.011744824 | 8.0251376 |
| 11 | `tray_V` | 17 | n-Propane | -0.11479509 | 0.010586776 | 9.8432532 |
| 12 | `tray_V` | 10 | n-Pentane | 0.014620867 | 0.010228009 | 0.42949301 |
| 13 | `tray_L` | 18 | n-Propane | 0.112019 | 0.010064681 | 10.129911 |
| 14 | `tray_V` | 3 | n-Propane | -0.21246531 | 0.0097973917 | 20.685905 |
| 15 | `tray_L` | 4 | n-Butane | -0.13918217 | 0.0095501145 | 13.573874 |
| 16 | `tray_V` | 5 | n-Butane | 0.10549159 | 0.0095449957 | 10.052031 |
| 17 | `tray_V` | 4 | n-Propane | -0.17557987 | 0.0092307859 | 18.021118 |
| 18 | `tray_L` | 10 | n-Pentane | -0.014724004 | 0.0088488149 | 0.6639521 |
| 19 | `tray_L` | 3 | n-Propane | 0.21786027 | 0.0086999439 | 24.041572 |
| 20 | `tray_V` | 16 | n-Propane | -0.11030601 | 0.0085983314 | 11.82877 |
