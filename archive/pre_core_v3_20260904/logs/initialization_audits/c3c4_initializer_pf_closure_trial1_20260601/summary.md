# Column Initialization Residual Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_initializer_pf_closure_trial1_20260601.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.068320684 1/s`
- Worst absolute state rate: `3795.9356 per s`
- Max tray total material residual: `7942.8246 lbmol/h`
- Total state inventory residual: `-5.9366531 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_V` | 0.068320684 | 1.6135726 | 2 | n-Butane |
| `tray_L` | 0.018186912 | 0.22852868 | 2 | n-Butane |
| `tray_EL_BTU` | 0.014933789 | 3795.9356 | 2 |  |
| `tray_T_f` | 0.003347977 | 0.42759023 | 2 |  |
| `bottom_L` | 0.0033155561 | 0.12748287 | 21 | n-Propane |
| `top_L` | 0.0021698369 | 0.28644032 | 0 | n-Butane |
| `top_V` | 0.00032998528 | 0.020523753 | 0 | n-Propane |
| `bottom_T_f` | 1.6737042e-08 | 3.7107743e-06 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `tray_EV_BTU` | 0 | 0 | 1 |  |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_V` | 2 | n-Butane | 0.51877415 | 0.068320684 | 6.5932224 |
| 2 | `tray_V` | 2 | n-Propane | 1.6135726 | 0.064644756 | 23.960611 |
| 3 | `tray_V` | 18 | n-Propane | -0.2761422 | 0.028941129 | 8.5415143 |
| 4 | `tray_V` | 19 | n-Propane | -0.22246425 | 0.028084031 | 6.9213788 |
| 5 | `tray_V` | 17 | n-Propane | -0.31575698 | 0.027771416 | 10.369855 |
| 6 | `tray_V` | 15 | n-Propane | -0.41187708 | 0.027288036 | 14.093687 |
| 7 | `tray_V` | 16 | n-Propane | -0.34600765 | 0.026106575 | 12.253659 |
| 8 | `tray_V` | 14 | n-Propane | -0.43398881 | 0.025784437 | 15.831425 |
| 9 | `tray_V` | 13 | n-Propane | -0.45488672 | 0.024654122 | 17.450737 |
| 10 | `tray_V` | 11 | n-Butane | 0.29434168 | 0.02400881 | 11.259736 |
| 11 | `tray_V` | 7 | n-Butane | 0.24850777 | 0.023574398 | 9.5414259 |
| 12 | `tray_V` | 8 | n-Butane | 0.26036502 | 0.023360533 | 10.145508 |
| 13 | `tray_V` | 6 | n-Butane | 0.22946797 | 0.023287854 | 8.8535469 |
| 14 | `tray_V` | 9 | n-Butane | 0.27056882 | 0.023241663 | 10.641543 |
| 15 | `tray_V` | 10 | n-Butane | 0.27697742 | 0.02305727 | 11.012585 |
| 16 | `tray_V` | 5 | n-Butane | 0.20281363 | 0.02227963 | 8.1030968 |
| 17 | `tray_V` | 12 | n-Propane | -0.43247868 | 0.022073758 | 18.592436 |
| 18 | `tray_V` | 19 | n-Butane | -0.64445307 | 0.020684249 | 30.156706 |
| 19 | `tray_V` | 4 | n-Butane | 0.16852225 | 0.020144251 | 7.3657736 |
| 20 | `tray_V` | 11 | n-Propane | 0.25481237 | 0.018685901 | 12.636612 |
