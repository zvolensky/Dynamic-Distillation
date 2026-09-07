# Column Initialization Residual Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_depropanizer_chemsep_warmer_feed_pr76_source_20260531.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `parity`
- Pressure model: `spec`
- Vapor flow model: `profile`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `False`

## Gate

- Pass: `True`
- Worst relative state rate: `5.4583689e-05 1/s`
- Worst absolute state rate: `0.0004394006 per s`
- Max tray total material residual: `0.0055560307 lbmol/h`
- Total state inventory residual: `1.673427e-11 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_L` | 5.4583689e-05 | 0.0004394006 | 19 | n-Propane |
| `tray_T_f` | 0 | 0 | 1 |  |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_L` | 19 | n-Propane | 0.00030782972 | 5.4583689e-05 | 4.6395918 |
| 2 | `tray_L` | 19 | n-Pentane | 0.00013157086 | 1.6024417e-05 | 7.2106488 |
| 3 | `tray_L` | 19 | n-Butane | -0.0004394006 | 8.8814213e-06 | 48.474132 |
| 4 | `tray_L` | 13 | n-Propane | 4.6341223e-07 | 2.9895063e-08 | 14.501296 |
| 5 | `tray_L` | 13 | n-Butane | 9.5309746e-07 | 2.8972152e-08 | 31.89702 |
| 6 | `tray_L` | 14 | n-Propane | -3.9844218e-07 | 2.8597173e-08 | 12.932922 |
| 7 | `tray_L` | 14 | n-Butane | -8.2117688e-07 | 2.4076503e-08 | 33.106983 |
| 8 | `tray_L` | 13 | n-Pentane | 1.2683218e-07 | 2.3860036e-08 | 4.3156742 |
| 9 | `tray_L` | 3 | n-Propane | 5.508153e-07 | 2.2650916e-08 | 23.317573 |
| 10 | `tray_L` | 14 | n-Pentane | -1.0319672e-07 | 1.9296669e-08 | 4.3479032 |
| 11 | `tray_L` | 2 | n-Propane | -5.5163502e-07 | 1.7496633e-08 | 30.528067 |
| 12 | `tray_L` | 2 | n-Butane | -1.0990853e-07 | 1.2686485e-08 | 7.6634345 |
| 13 | `tray_L` | 16 | n-Propane | 1.355672e-07 | 1.0744433e-08 | 11.617436 |
| 14 | `tray_L` | 16 | n-Butane | 4.6156244e-07 | 9.9676981e-09 | 45.305821 |
| 15 | `tray_L` | 16 | n-Pentane | 6.4106568e-08 | 9.695409e-09 | 5.612054 |
| 16 | `tray_L` | 3 | n-Butane | 1.1083262e-07 | 9.0893066e-09 | 11.193738 |
| 17 | `tray_L` | 15 | n-Butane | -3.2034286e-07 | 8.7207898e-09 | 35.73324 |
| 18 | `tray_L` | 12 | n-Propane | -1.4260166e-07 | 8.4744598e-09 | 15.827227 |
| 19 | `tray_L` | 12 | n-Butane | -2.6099868e-07 | 8.1717169e-09 | 30.93927 |
| 20 | `tray_L` | 15 | n-Pentane | -4.524409e-08 | 8.1550319e-09 | 4.5479968 |
