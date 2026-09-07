# Column Initialization Residual Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_initializer_pf_closure_trial2_syncV_20260601.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.024466898 1/s`
- Worst absolute state rate: `3795.9356 per s`
- Max tray total material residual: `2572.085 lbmol/h`
- Total state inventory residual: `-5.9366531 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_V` | 0.024466898 | 0.67693472 | 18 | n-Propane |
| `tray_L` | 0.018186912 | 0.22852868 | 2 | n-Butane |
| `tray_EL_BTU` | 0.014933789 | 3795.9356 | 2 |  |
| `tray_EV_BTU` | 0.003949955 | 112.26373 | 19 |  |
| `bottom_L` | 0.0033155561 | 0.12748287 | 21 | n-Propane |
| `tray_T_f` | 0.003032769 | 0.38733312 | 2 |  |
| `top_L` | 0.0021698369 | 0.28644032 | 0 | n-Butane |
| `top_V` | 0.0003298931 | 0.02051802 | 0 | n-Propane |
| `bottom_T_f` | 1.6737042e-08 | 3.7107743e-06 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_V` | 18 | n-Propane | -0.091717883 | 0.024466898 | 2.7486518 |
| 2 | `tray_V` | 17 | n-Propane | -0.10217976 | 0.023304572 | 3.3845369 |
| 3 | `tray_V` | 19 | n-Propane | -0.066549067 | 0.020819322 | 2.1965051 |
| 4 | `tray_V` | 16 | n-Propane | -0.10452011 | 0.020695422 | 4.0503977 |
| 5 | `tray_V` | 2 | n-Propane | -0.67693472 | 0.02017052 | 32.560599 |
| 6 | `tray_V` | 4 | n-Butane | 0.082561608 | 0.019625737 | 3.2068029 |
| 7 | `tray_V` | 3 | n-Butane | 0.074294643 | 0.019199912 | 2.8695305 |
| 8 | `tray_V` | 5 | n-Butane | 0.086194353 | 0.018791916 | 3.5867783 |
| 9 | `tray_V` | 15 | n-Butane | 0.13886341 | 0.018199749 | 6.629963 |
| 10 | `tray_L` | 2 | n-Butane | -0.15455499 | 0.018186912 | 7.4981435 |
| 11 | `tray_V` | 14 | n-Butane | 0.13007023 | 0.018147488 | 6.167396 |
| 12 | `tray_V` | 19 | n-Pentane | 0.034146332 | 0.018067455 | 0.88993589 |
| 13 | `tray_V` | 13 | n-Butane | 0.11729309 | 0.017403472 | 5.7396373 |
| 14 | `tray_V` | 6 | n-Butane | 0.085277077 | 0.017174423 | 3.9653532 |
| 15 | `tray_V` | 12 | n-Butane | 0.10902346 | 0.017131644 | 5.3638647 |
| 16 | `tray_V` | 15 | n-Propane | -0.083433157 | 0.016359905 | 4.0998559 |
| 17 | `tray_V` | 18 | n-Pentane | 0.02777253 | 0.015964704 | 0.73962075 |
| 18 | `tray_EL_BTU` | 2 |  | 3795.9356 | 0.014933789 | -254183.36 |
| 19 | `tray_V` | 7 | n-Butane | 0.079043644 | 0.014868372 | 4.3162273 |
| 20 | `tray_V` | 14 | n-Propane | -0.073204561 | 0.01296933 | 4.6444364 |
