# Column Initialization Residual Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_depropanizer_chemsep_warmer_feed_pr76_source_20260531.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.095423297 1/s`
- Worst absolute state rate: `1.7718444 per s`
- Max tray total material residual: `7963.7312 lbmol/h`
- Total state inventory residual: `4.793721e-12 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_V` | 0.095423297 | 1.7718444 | 2 | n-Butane |
| `tray_L` | 0.021166411 | 0.23859027 | 19 | n-Propane |
| `tray_T_f` | 0.0010119281 | 0.12923941 | 2 |  |
| `bottom_L` | 5.0172774e-06 | 0.00050480376 | 21 | n-Propane |
| `top_L` | 3.4225642e-07 | 0.00043086041 | 0 | n-Propane |
| `bottom_T_f` | 1.6735789e-08 | 3.7104965e-06 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_V` | 2 | n-Butane | 0.37043891 | 0.095423297 | 2.8820595 |
| 2 | `tray_V` | 2 | n-Propane | 1.7718444 | 0.061797362 | 27.671846 |
| 3 | `tray_V` | 3 | n-Butane | 0.22665871 | 0.039936636 | 4.6754582 |
| 4 | `tray_V` | 19 | n-Propane | -0.25399494 | 0.036647296 | 5.9307961 |
| 5 | `tray_V` | 18 | n-Propane | -0.30564181 | 0.033164673 | 8.2158848 |
| 6 | `tray_V` | 4 | n-Butane | 0.25214267 | 0.032257735 | 6.8165027 |
| 7 | `tray_V` | 17 | n-Propane | -0.34627627 | 0.030013339 | 10.537413 |
| 8 | `tray_V` | 11 | n-Pentane | 0.039664584 | 0.028392154 | 0.39702621 |
| 9 | `tray_V` | 15 | n-Propane | -0.439695 | 0.027811485 | 14.809835 |
| 10 | `tray_V` | 5 | n-Butane | 0.26590742 | 0.02751977 | 8.6624143 |
| 11 | `tray_V` | 16 | n-Propane | -0.37468149 | 0.027203436 | 12.773315 |
| 12 | `tray_V` | 14 | n-Propane | -0.45293714 | 0.025785126 | 16.56583 |
| 13 | `tray_V` | 6 | n-Butane | 0.26945971 | 0.024416062 | 10.036166 |
| 14 | `tray_V` | 13 | n-Propane | -0.45809283 | 0.024104202 | 18.004688 |
| 15 | `tray_V` | 7 | n-Butane | 0.26985694 | 0.022640414 | 10.919258 |
| 16 | `tray_V` | 8 | n-Butane | 0.26755408 | 0.021516066 | 11.435084 |
| 17 | `tray_L` | 19 | n-Propane | 0.11936992 | 0.021166411 | 4.6395918 |
| 18 | `tray_V` | 11 | n-Propane | 0.2783752 | 0.020850207 | 12.351196 |
| 19 | `tray_V` | 9 | n-Butane | 0.26291592 | 0.020729863 | 11.682955 |
| 20 | `tray_V` | 12 | n-Propane | -0.40675609 | 0.020540882 | 18.80227 |
