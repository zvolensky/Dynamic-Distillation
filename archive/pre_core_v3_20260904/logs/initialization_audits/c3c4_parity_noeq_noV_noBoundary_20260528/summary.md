# Column Initialization Residual Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_splitter_openloop_seed_20260526.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `parity`
- Pressure model: `spec`
- Vapor flow model: `profile`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `False`

## Gate

- Pass: `True`
- Worst relative state rate: `5.4886142e-05 1/s`
- Worst absolute state rate: `0.00042212503 per s`
- Max tray total material residual: `0.088404706 lbmol/h`
- Total state inventory residual: `0.0389309 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_L` | 5.4886142e-05 | 0.00042212503 | 19 | n-Propane |
| `tray_T_f` | 0 | 0 | 1 |  |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_L` | 19 | n-Propane | 0.00031156098 | 5.4886142e-05 | 4.6764961 |
| 2 | `tray_L` | 19 | n-Pentane | 0.00013512092 | 1.6454646e-05 | 7.2117184 |
| 3 | `tray_L` | 19 | n-Butane | -0.00042212503 | 8.5387964e-06 | 48.436128 |
| 4 | `tray_L` | 1 | n-Propane | -1.6769185e-06 | 1.6769185e-06 | 0 |
| 5 | `tray_L` | 18 | n-Propane | -5.7887677e-06 | 7.3096299e-07 | 6.9193718 |
| 6 | `tray_L` | 17 | n-Propane | 5.3401552e-06 | 5.0900198e-07 | 9.4914231 |
| 7 | `tray_L` | 18 | n-Butane | -1.5716288e-05 | 3.1536879e-07 | 48.834634 |
| 8 | `tray_L` | 18 | n-Pentane | -2.2469917e-06 | 3.1010667e-07 | 6.2458672 |
| 9 | `tray_L` | 8 | n-Propane | 2.7527462e-06 | 2.3232314e-07 | 10.848782 |
| 10 | `tray_L` | 6 | n-Propane | -2.720021e-06 | 1.9363376e-07 | 13.047246 |
| 11 | `tray_L` | 17 | n-Butane | 9.5547256e-06 | 1.9333237e-07 | 48.421241 |
| 12 | `tray_L` | 16 | n-Propane | -2.2885625e-06 | 1.8054698e-07 | 11.675718 |
| 13 | `tray_L` | 1 | n-Butane | -1.7351236e-07 | 1.7351236e-07 | 0 |
| 14 | `tray_L` | 17 | n-Pentane | 1.1836706e-06 | 1.7022456e-07 | 5.9535826 |
| 15 | `tray_L` | 5 | n-Propane | 2.0379036e-06 | 1.2528924e-07 | 15.265591 |
| 16 | `tray_L` | 11 | n-Propane | -1.225798e-06 | 1.1503348e-07 | 9.6560108 |
| 17 | `tray_L` | 14 | n-Pentane | 5.9346241e-07 | 1.1089174e-07 | 4.351728 |
| 18 | `tray_L` | 16 | n-Butane | -4.183466e-06 | 9.046643e-08 | 45.243297 |
| 19 | `tray_L` | 16 | n-Pentane | -5.8743033e-07 | 8.8785541e-08 | 5.6162838 |
| 20 | `tray_L` | 13 | n-Propane | 1.3437458e-06 | 8.6531945e-08 | 14.528899 |
