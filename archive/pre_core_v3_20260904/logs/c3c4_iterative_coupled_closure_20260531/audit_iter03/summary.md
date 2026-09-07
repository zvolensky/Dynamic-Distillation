# Column Initialization Residual Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_iterative_coupled_closure_20260531\c3c4_coupled_iter03_blend0.0781.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `parity`
- Pressure model: `spec`
- Vapor flow model: `profile`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.024411194 1/s`
- Worst absolute state rate: `0.20484021 per s`
- Max tray total material residual: `0.09 lbmol/h`
- Total state inventory residual: `0.004 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_L` | 0.024411194 | 0.20484021 | 2 | n-Pentane |
| `tray_V` | 0.019521622 | 0.1968246 | 19 | n-Pentane |
| `bottom_L` | 0.00046520952 | 0.051170466 | 21 | n-Pentane |
| `top_L` | 6.996447e-11 | 1.4701451e-08 | 0 | n-Pentane |
| `bottom_T_f` | 0 | 0 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |
| `tray_T_f` | 0 | 0 | 1 |  |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_L` | 2 | n-Pentane | 0.025409873 | 0.024411194 | 0.040910684 |
| 2 | `tray_V` | 19 | n-Pentane | 0.07151646 | 0.019521622 | 2.6634486 |
| 3 | `tray_V` | 2 | n-Butane | 0.12136498 | 0.015494968 | 6.8325416 |
| 4 | `tray_V` | 3 | n-Butane | 0.1345526 | 0.015146558 | 7.8833781 |
| 5 | `tray_V` | 11 | n-Pentane | 0.024377753 | 0.014138634 | 0.72419439 |
| 6 | `tray_L` | 3 | n-Butane | -0.14209722 | 0.012788603 | 10.111239 |
| 7 | `tray_V` | 18 | n-Propane | -0.10425891 | 0.012319055 | 7.4632226 |
| 8 | `tray_V` | 4 | n-Butane | 0.1230084 | 0.011692525 | 9.5202596 |
| 9 | `tray_L` | 11 | n-Pentane | -0.024678927 | 0.011366741 | 1.1711525 |
| 10 | `tray_V` | 17 | n-Propane | -0.10563921 | 0.010192191 | 9.3647207 |
| 11 | `tray_V` | 3 | n-Propane | -0.19633356 | 0.0096833197 | 19.275439 |
| 12 | `tray_L` | 4 | n-Butane | -0.12777137 | 0.0091477832 | 12.967468 |
| 13 | `tray_V` | 4 | n-Propane | -0.16215755 | 0.0091035339 | 16.812593 |
| 14 | `tray_V` | 19 | n-Propane | 0.059704446 | 0.0090645916 | 5.5865567 |
| 15 | `tray_L` | 19 | n-Propane | 0.097257407 | 0.0088194368 | 10.027621 |
| 16 | `tray_V` | 10 | n-Pentane | 0.013402713 | 0.0085289325 | 0.57144087 |
| 17 | `tray_V` | 16 | n-Propane | -0.10152705 | 0.0083272028 | 11.192215 |
| 18 | `tray_L` | 10 | n-Pentane | -0.013565386 | 0.0082913552 | 0.63608786 |
| 19 | `tray_L` | 2 | n-Butane | 0.068297309 | 0.0082268453 | 7.3017616 |
| 20 | `tray_V` | 2 | n-Propane | -0.1968246 | 0.00812627 | 23.22078 |
