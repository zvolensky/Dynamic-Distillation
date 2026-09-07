# Column Initialization Residual Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_initializer_flowcomp_trial1_20260531.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `parity`
- Pressure model: `spec`
- Vapor flow model: `profile`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.028014486 1/s`
- Worst absolute state rate: `0.44058503 per s`
- Max tray total material residual: `389.22117 lbmol/h`
- Total state inventory residual: `-1.5347723e-12 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_V` | 0.028014486 | 0.33357373 | 12 | n-Pentane |
| `tray_L` | 0.015120968 | 0.44058503 | 2 | n-Butane |
| `bottom_L` | 0.0031072444 | 0.1194733 | 21 | n-Propane |
| `top_L` | 0.0019565306 | 0.25828174 | 0 | n-Butane |
| `bottom_T_f` | 0 | 0 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |
| `tray_T_f` | 0 | 0 | 1 |  |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_V` | 12 | n-Pentane | 0.066203909 | 0.028014486 | 1.3632027 |
| 2 | `tray_V` | 11 | n-Pentane | 0.036234033 | 0.023571128 | 0.53722098 |
| 3 | `tray_V` | 10 | n-Pentane | 0.024994381 | 0.019588013 | 0.27600389 |
| 4 | `tray_V` | 12 | n-Butane | 0.33357373 | 0.017084298 | 18.525164 |
| 5 | `tray_L` | 2 | n-Butane | -0.12753608 | 0.015120968 | 7.434386 |
| 6 | `tray_L` | 12 | n-Butane | -0.44058503 | 0.012795259 | 33.433459 |
| 7 | `tray_V` | 9 | n-Pentane | 0.014226464 | 0.01271912 | 0.11851012 |
| 8 | `tray_L` | 3 | n-Butane | -0.14633709 | 0.012606251 | 10.608296 |
| 9 | `tray_L` | 11 | n-Pentane | -0.022483955 | 0.010439365 | 1.1537665 |
| 10 | `tray_L` | 2 | n-Propane | 0.32460367 | 0.010221443 | 30.757128 |
| 11 | `tray_V` | 19 | n-Pentane | 0.037415259 | 0.010009132 | 2.7381123 |
| 12 | `tray_L` | 12 | n-Pentane | -0.045804488 | 0.0099744429 | 3.5921851 |
| 13 | `tray_L` | 4 | n-Butane | -0.14709268 | 0.0099005662 | 13.856997 |
| 14 | `tray_L` | 10 | n-Pentane | -0.017163895 | 0.0098186928 | 0.74808349 |
| 15 | `tray_V` | 18 | n-Propane | -0.089003027 | 0.0095447008 | 8.324863 |
| 16 | `tray_V` | 18 | n-Pentane | 0.029500752 | 0.009149388 | 2.2243416 |
| 17 | `tray_V` | 4 | n-Butane | 0.073966899 | 0.008954235 | 7.2605493 |
| 18 | `tray_V` | 17 | n-Propane | -0.10070486 | 0.0089229188 | 10.28609 |
| 19 | `tray_V` | 13 | n-Pentane | 0.015924116 | 0.0086459181 | 0.84180745 |
| 20 | `tray_V` | 5 | n-Butane | 0.079093813 | 0.0086189463 | 8.1767382 |
