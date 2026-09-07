# Column Initialization Residual Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_iterative_coupled_closure_20260531\c3c4_coupled_iter04_blend0.0977.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `parity`
- Pressure model: `spec`
- Vapor flow model: `profile`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.032046427 1/s`
- Worst absolute state rate: `0.18949159 per s`
- Max tray total material residual: `0.09 lbmol/h`
- Total state inventory residual: `0.004 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_L` | 0.032046427 | 0.18949159 | 2 | n-Pentane |
| `tray_V` | 0.023310463 | 0.18509086 | 19 | n-Propane |
| `bottom_L` | 0.00046230116 | 0.046173357 | 21 | n-Pentane |
| `top_L` | 4.4178014e-11 | 1.3265762e-08 | 0 | n-Pentane |
| `bottom_T_f` | 0 | 0 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |
| `tray_T_f` | 0 | 0 | 1 |  |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_L` | 2 | n-Pentane | 0.035188347 | 0.032046427 | 0.098042774 |
| 2 | `tray_V` | 19 | n-Propane | 0.14947233 | 0.023310463 | 5.4122417 |
| 3 | `tray_L` | 2 | n-Butane | 0.15849031 | 0.018816933 | 7.4227496 |
| 4 | `tray_L` | 12 | n-Pentane | 0.053934869 | 0.012721351 | 3.2397123 |
| 5 | `tray_V` | 19 | n-Pentane | 0.046199089 | 0.012287214 | 2.7599319 |
| 6 | `tray_V` | 11 | n-Pentane | 0.021821623 | 0.011666156 | 0.87050661 |
| 7 | `tray_L` | 3 | n-Butane | -0.12685075 | 0.011661709 | 9.8775443 |
| 8 | `tray_V` | 18 | n-Propane | -0.093858569 | 0.011585044 | 7.1017012 |
| 9 | `tray_V` | 3 | n-Butane | 0.11643191 | 0.011297406 | 9.3060742 |
| 10 | `tray_V` | 2 | n-Butane | 0.10342353 | 0.010782831 | 8.5915012 |
| 11 | `tray_L` | 11 | n-Pentane | -0.022237462 | 0.01056238 | 1.1053458 |
| 12 | `tray_V` | 17 | n-Propane | -0.095088487 | 0.0096897696 | 8.8132867 |
| 13 | `tray_V` | 3 | n-Propane | -0.17774424 | 0.0095304725 | 17.650097 |
| 14 | `tray_V` | 4 | n-Butane | 0.1078518 | 0.0092051148 | 10.716507 |
| 15 | `tray_V` | 4 | n-Propane | -0.14669042 | 0.0089336664 | 15.419957 |
| 16 | `tray_L` | 4 | n-Butane | -0.11442903 | 0.0085191665 | 12.431951 |
| 17 | `tray_V` | 2 | n-Propane | -0.17831729 | 0.0080187504 | 21.23754 |
| 18 | `tray_V` | 16 | n-Propane | -0.091410664 | 0.0079774125 | 10.458686 |
| 19 | `tray_L` | 19 | n-Pentane | -0.050254534 | 0.0078442339 | 5.4065572 |
| 20 | `tray_L` | 10 | n-Pentane | -0.012223658 | 0.0075312522 | 0.62305781 |
