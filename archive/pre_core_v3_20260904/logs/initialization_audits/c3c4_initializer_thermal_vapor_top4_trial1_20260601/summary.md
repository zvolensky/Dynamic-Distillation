# Column Initialization Residual Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_initializer_thermal_vapor_top4_trial1_20260601.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.034550633 1/s`
- Worst absolute state rate: `4141.7465 per s`
- Max tray total material residual: `3584.7636 lbmol/h`
- Total state inventory residual: `110.47525 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_V` | 0.034550633 | 0.7402826 | 2 | n-Butane |
| `tray_T_f` | 0.017443835 | 2.2278568 | 2 |  |
| `tray_EL_BTU` | 0.016252282 | 4141.7465 | 5 |  |
| `tray_L` | 0.01255204 | 0.20464479 | 3 | n-Butane |
| `bottom_L` | 0.0033155561 | 0.12748287 | 21 | n-Propane |
| `top_L` | 0.001705251 | 0.40623169 | 0 | n-Butane |
| `bottom_T_f` | 1.6735789e-08 | 3.7104965e-06 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |
| `tray_EV_BTU` | 0 | 0 | 1 |  |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_V` | 2 | n-Butane | 0.26235064 | 0.034550633 | 6.5932224 |
| 2 | `tray_V` | 2 | n-Propane | 0.7402826 | 0.029658032 | 23.960611 |
| 3 | `tray_V` | 18 | n-Propane | -0.27563143 | 0.028887598 | 8.5415143 |
| 4 | `tray_V` | 19 | n-Propane | -0.22266991 | 0.028109993 | 6.9213788 |
| 5 | `tray_V` | 17 | n-Propane | -0.31534566 | 0.02773524 | 10.369855 |
| 6 | `tray_V` | 15 | n-Propane | -0.41286209 | 0.027353296 | 14.093687 |
| 7 | `tray_V` | 4 | n-Butane | 0.22303611 | 0.026660548 | 7.3657736 |
| 8 | `tray_V` | 16 | n-Propane | -0.34489407 | 0.026022555 | 12.253659 |
| 9 | `tray_V` | 14 | n-Propane | -0.43622209 | 0.025917122 | 15.831425 |
| 10 | `tray_V` | 3 | n-Butane | 0.19518219 | 0.025405849 | 6.6825692 |
| 11 | `tray_V` | 13 | n-Propane | -0.45657775 | 0.024745773 | 17.450737 |
| 12 | `tray_V` | 7 | n-Butane | 0.24878478 | 0.023600677 | 9.5414259 |
| 13 | `tray_V` | 11 | n-Butane | 0.28871629 | 0.023549959 | 11.259736 |
| 14 | `tray_V` | 8 | n-Butane | 0.26086558 | 0.023405444 | 10.145508 |
| 15 | `tray_V` | 6 | n-Butane | 0.23003299 | 0.023345197 | 8.8535469 |
| 16 | `tray_V` | 9 | n-Butane | 0.26881996 | 0.023091437 | 10.641543 |
| 17 | `tray_V` | 10 | n-Butane | 0.27631191 | 0.023001869 | 11.012585 |
| 18 | `tray_V` | 5 | n-Butane | 0.20423068 | 0.022435297 | 8.1030968 |
| 19 | `tray_V` | 12 | n-Propane | -0.42199796 | 0.021538821 | 18.592436 |
| 20 | `tray_V` | 19 | n-Butane | -0.64534912 | 0.020713009 | 30.156706 |
