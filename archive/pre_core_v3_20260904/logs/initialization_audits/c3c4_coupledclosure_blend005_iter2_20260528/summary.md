# Column Initialization Residual Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_splitter_openloop_seed_coupledclosure_blend005_iter2_20260528.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `parity`
- Pressure model: `spec`
- Vapor flow model: `profile`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.02308975 1/s`
- Worst absolute state rate: `0.22167945 per s`
- Max tray total material residual: `0.09 lbmol/h`
- Total state inventory residual: `-0.0060691 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_V` | 0.02308975 | 0.21562619 | 2 | n-Butane |
| `top_L` | 0.020494315 | 0.18271331 | 0 | n-Pentane |
| `tray_L` | 0.017420415 | 0.22167945 | 2 | n-Butane |
| `bottom_L` | 0.0011083101 | 0.04296934 | 21 | n-Propane |
| `bottom_T_f` | 0 | 0 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |
| `tray_T_f` | 0 | 0 | 1 |  |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_V` | 2 | n-Butane | 0.1395917 | 0.02308975 | 5.0456135 |
| 2 | `tray_V` | 3 | n-Butane | 0.15296142 | 0.020564692 | 6.4380602 |
| 3 | `top_L` | 0 | n-Pentane | 0.020662509 | 0.020494315 | 0.0082068935 |
| 4 | `tray_L` | 2 | n-Butane | -0.14496045 | 0.017420415 | 7.3212972 |
| 5 | `tray_V` | 11 | n-Pentane | 0.026974528 | 0.017120644 | 0.57555572 |
| 6 | `tray_V` | 4 | n-Butane | 0.13840601 | 0.014874384 | 8.3049907 |
| 7 | `tray_L` | 3 | n-Butane | -0.15735218 | 0.013709766 | 10.477379 |
| 8 | `tray_V` | 18 | n-Propane | -0.11482461 | 0.013003195 | 7.8304923 |
| 9 | `tray_L` | 19 | n-Propane | 0.10748444 | 0.012329079 | 7.717962 |
| 10 | `tray_L` | 11 | n-Pentane | -0.02714988 | 0.012053565 | 1.2524356 |
| 11 | `tray_V` | 19 | n-Pentane | 0.038855685 | 0.010897892 | 2.5654311 |
| 12 | `tray_V` | 17 | n-Propane | -0.1163577 | 0.010650665 | 9.9249228 |
| 13 | `tray_V` | 10 | n-Pentane | 0.014828765 | 0.010552274 | 0.40526724 |
| 14 | `tray_L` | 18 | n-Propane | 0.11367412 | 0.010487225 | 9.8392948 |
| 15 | `tray_V` | 5 | n-Butane | 0.10710925 | 0.0098228905 | 9.9040464 |
| 16 | `tray_V` | 3 | n-Propane | -0.21521846 | 0.0098153939 | 20.926625 |
| 17 | `tray_L` | 4 | n-Butane | -0.14117818 | 0.0096457435 | 13.636319 |
| 18 | `tray_V` | 4 | n-Propane | -0.17787061 | 0.0092509055 | 18.227373 |
| 19 | `tray_L` | 10 | n-Pentane | -0.014923401 | 0.0089688707 | 0.66391085 |
| 20 | `tray_L` | 3 | n-Propane | 0.2201691 | 0.0087947354 | 24.034193 |
