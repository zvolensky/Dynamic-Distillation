# Column Initialization Residual Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_iterative_coupled_closure_continue_20260531\c3c4_coupled_cont_iter01_blend0.0250.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `parity`
- Pressure model: `spec`
- Vapor flow model: `profile`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.026444526 1/s`
- Worst absolute state rate: `0.20091096 per s`
- Max tray total material residual: `0.09 lbmol/h`
- Total state inventory residual: `0.004 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_L` | 0.026444526 | 0.20091096 | 2 | n-Pentane |
| `tray_V` | 0.017633568 | 0.19208673 | 19 | n-Pentane |
| `bottom_L` | 0.00046451716 | 0.049891206 | 21 | n-Pentane |
| `top_L` | 6.1464503e-11 | 1.4333915e-08 | 0 | n-Pentane |
| `bottom_T_f` | 0 | 0 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |
| `tray_T_f` | 0 | 0 | 1 |  |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_L` | 2 | n-Pentane | 0.027913162 | 0.026444526 | 0.055536499 |
| 2 | `tray_V` | 19 | n-Pentane | 0.065035213 | 0.017633568 | 2.6881483 |
| 3 | `tray_V` | 2 | n-Butane | 0.11677197 | 0.014098067 | 7.2828353 |
| 4 | `tray_V` | 3 | n-Butane | 0.1299137 | 0.014048387 | 8.2475883 |
| 5 | `tray_V` | 11 | n-Pentane | 0.023723384 | 0.013466568 | 0.76165032 |
| 6 | `tray_V` | 19 | n-Propane | 0.082685023 | 0.012639236 | 5.541932 |
| 7 | `tray_L` | 3 | n-Butane | -0.13819413 | 0.012504657 | 10.051413 |
| 8 | `tray_V` | 18 | n-Propane | -0.10159642 | 0.012137186 | 7.3706731 |
| 9 | `tray_L` | 11 | n-Pentane | -0.024053912 | 0.011165504 | 1.154306 |
| 10 | `tray_V` | 4 | n-Butane | 0.11912831 | 0.011003401 | 9.826499 |
| 11 | `tray_L` | 2 | n-Butane | 0.091386718 | 0.010967194 | 7.3327346 |
| 12 | `tray_V` | 17 | n-Propane | -0.10293823 | 0.010068732 | 9.2235536 |
| 13 | `tray_V` | 3 | n-Propane | -0.19157469 | 0.0096465734 | 18.859352 |
| 14 | `tray_L` | 12 | n-Pentane | 0.04054933 | 0.0090660827 | 3.4726407 |
| 15 | `tray_V` | 4 | n-Propane | -0.15819796 | 0.009062629 | 16.456078 |
| 16 | `tray_L` | 4 | n-Butane | -0.12435573 | 0.0089914932 | 12.830376 |
| 17 | `tray_V` | 16 | n-Propane | -0.098937254 | 0.0082417274 | 11.004432 |
| 18 | `tray_L` | 19 | n-Propane | 0.094684902 | 0.0081743717 | 10.583141 |
| 19 | `tray_V` | 2 | n-Propane | -0.19208673 | 0.0081004577 | 22.713071 |
| 20 | `tray_L` | 10 | n-Pentane | -0.013221903 | 0.0080979242 | 0.63275217 |
