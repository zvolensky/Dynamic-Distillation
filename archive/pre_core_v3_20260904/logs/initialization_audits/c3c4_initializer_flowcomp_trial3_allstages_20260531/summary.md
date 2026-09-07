# Column Initialization Residual Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_initializer_flowcomp_trial3_allstages_20260531.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `parity`
- Pressure model: `spec`
- Vapor flow model: `profile`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.027225686 1/s`
- Worst absolute state rate: `0.59108308 per s`
- Max tray total material residual: `71.958017 lbmol/h`
- Total state inventory residual: `4.0500936e-13 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_V` | 0.027225686 | 0.42760043 | 12 | n-Pentane |
| `tray_L` | 0.016872129 | 0.59108308 | 2 | n-Butane |
| `bottom_L` | 0.003212945 | 0.12353748 | 21 | n-Propane |
| `top_L` | 0.00225617 | 0.29783716 | 0 | n-Butane |
| `bottom_T_f` | 0 | 0 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |
| `tray_T_f` | 0 | 0 | 1 |  |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_V` | 12 | n-Pentane | 0.065869696 | 0.027225686 | 1.4193952 |
| 2 | `tray_V` | 11 | n-Pentane | 0.035034649 | 0.022351948 | 0.5674092 |
| 3 | `tray_V` | 12 | n-Butane | 0.42760043 | 0.021641412 | 18.758435 |
| 4 | `tray_V` | 10 | n-Pentane | 0.024660706 | 0.019005914 | 0.29752803 |
| 5 | `tray_L` | 2 | n-Butane | -0.14207973 | 0.016872129 | 7.4209722 |
| 6 | `tray_L` | 12 | n-Butane | -0.59108308 | 0.016765501 | 34.255914 |
| 7 | `tray_V` | 9 | n-Pentane | 0.014985869 | 0.013292475 | 0.12739498 |
| 8 | `tray_L` | 3 | n-Butane | -0.14052923 | 0.012451621 | 10.286018 |
| 9 | `tray_V` | 12 | n-Propane | 0.20592524 | 0.011432213 | 17.01272 |
| 10 | `tray_L` | 12 | n-Pentane | -0.044526416 | 0.010190568 | 3.3693754 |
| 11 | `tray_L` | 11 | n-Pentane | -0.020352016 | 0.0096374498 | 1.1117636 |
| 12 | `tray_L` | 4 | n-Butane | -0.13563524 | 0.0094533114 | 13.347908 |
| 13 | `tray_L` | 10 | n-Pentane | -0.016419657 | 0.0094080546 | 0.74527655 |
| 14 | `tray_V` | 18 | n-Propane | -0.086510255 | 0.0091617459 | 8.4425512 |
| 15 | `tray_V` | 13 | n-Pentane | 0.016438 | 0.0091172499 | 0.80295591 |
| 16 | `tray_V` | 17 | n-Propane | -0.098521042 | 0.0087506331 | 10.258733 |
| 17 | `tray_V` | 19 | n-Pentane | 0.03222514 | 0.0087150725 | 2.697633 |
| 18 | `tray_V` | 18 | n-Pentane | 0.026990232 | 0.0083873791 | 2.2179578 |
| 19 | `tray_L` | 2 | n-Propane | 0.26166692 | 0.0082361488 | 30.770543 |
| 20 | `tray_V` | 4 | n-Butane | 0.06980338 | 0.0081428639 | 7.5723377 |
