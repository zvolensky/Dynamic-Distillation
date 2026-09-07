# Column Initialization Residual Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_depropanizer_chemsep_warmer_feed_pr76_source_energy_reconciled_20260531.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.095423294 1/s`
- Worst absolute state rate: `7634.4552 per s`
- Max tray total material residual: `7963.7309 lbmol/h`
- Total state inventory residual: `1.292233e-11 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_V` | 0.095423294 | 1.7718443 | 2 | n-Butane |
| `tray_T_f` | 0.025112764 | 4.5367213 | 12 |  |
| `tray_EL_BTU` | 0.022869942 | 7634.4552 | 2 |  |
| `tray_L` | 0.021624056 | 0.63370983 | 12 | n-Pentane |
| `bottom_L` | 5.0172774e-06 | 0.00050480376 | 21 | n-Propane |
| `top_L` | 3.4225642e-07 | 0.00043086041 | 0 | n-Propane |
| `bottom_T_f` | 1.6735789e-08 | 3.7104965e-06 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |
| `tray_EV_BTU` | 0 | 0 | 1 |  |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_V` | 2 | n-Butane | 0.3704389 | 0.095423294 | 2.8820595 |
| 2 | `tray_V` | 2 | n-Propane | 1.7718443 | 0.061797358 | 27.671846 |
| 3 | `tray_V` | 12 | n-Pentane | 0.091740964 | 0.042556659 | 1.155737 |
| 4 | `tray_V` | 3 | n-Butane | 0.22665871 | 0.039936635 | 4.6754582 |
| 5 | `tray_V` | 19 | n-Propane | -0.25399493 | 0.036647296 | 5.9307961 |
| 6 | `tray_V` | 18 | n-Propane | -0.30564181 | 0.033164673 | 8.2158848 |
| 7 | `tray_V` | 4 | n-Butane | 0.25214267 | 0.032257735 | 6.8165027 |
| 8 | `tray_V` | 17 | n-Propane | -0.34627626 | 0.030013338 | 10.537413 |
| 9 | `tray_V` | 11 | n-Pentane | 0.040163297 | 0.028749137 | 0.39702621 |
| 10 | `tray_V` | 15 | n-Propane | -0.43969499 | 0.027811485 | 14.809835 |
| 11 | `tray_V` | 5 | n-Butane | 0.26590742 | 0.02751977 | 8.6624143 |
| 12 | `tray_V` | 16 | n-Propane | -0.37468148 | 0.027203435 | 12.773315 |
| 13 | `tray_V` | 14 | n-Propane | -0.45293713 | 0.025785126 | 16.56583 |
| 14 | `tray_T_f` | 12 |  | 4.5367213 | 0.025112764 | 179.654 |
| 15 | `tray_V` | 6 | n-Butane | 0.26945971 | 0.024416061 | 10.036166 |
| 16 | `tray_V` | 13 | n-Propane | -0.45809282 | 0.024104202 | 18.004688 |
| 17 | `tray_EL_BTU` | 2 |  | 7634.4552 | 0.022869942 | -333819.49 |
| 18 | `tray_V` | 7 | n-Butane | 0.26985694 | 0.022640414 | 10.919258 |
| 19 | `tray_L` | 12 | n-Pentane | -0.11451329 | 0.021624056 | 4.2956436 |
| 20 | `tray_V` | 8 | n-Butane | 0.26755411 | 0.021516069 | 11.435084 |
