# Column Initialization Residual Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_initializer_specdof_feedvf_trial5_noflash_20260531.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `parity`
- Pressure model: `spec`
- Vapor flow model: `profile`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.026240129 1/s`
- Worst absolute state rate: `6330.3346 per s`
- Max tray total material residual: `34.383219 lbmol/h`
- Total state inventory residual: `-24.814149 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_EL_BTU` | 0.026240129 | 6330.3346 | 12 |  |
| `tray_L` | 0.018261437 | 0.22528001 | 2 | n-Butane |
| `tray_V` | 0.010771293 | 0.11849442 | 10 | n-Pentane |
| `bottom_L` | 0.0034541227 | 0.13281074 | 21 | n-Propane |
| `top_L` | 0.0022144973 | 0.29307524 | 0 | n-Butane |
| `bottom_T_f` | 0 | 0 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |
| `tray_EV_BTU` | 0 | 0 | 1 |  |
| `tray_T_f` | 0 | 0 | 1 |  |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_EL_BTU` | 12 |  | -6330.3346 | 0.026240129 | -241245.33 |
| 2 | `tray_L` | 2 | n-Butane | -0.15538403 | 0.018261437 | 7.5088611 |
| 3 | `tray_L` | 3 | n-Butane | -0.14120372 | 0.012526282 | 10.272596 |
| 4 | `tray_EL_BTU` | 2 |  | 3954.527 | 0.011846268 | -333819.49 |
| 5 | `tray_V` | 10 | n-Pentane | 0.013203686 | 0.010771293 | 0.22582185 |
| 6 | `tray_V` | 11 | n-Pentane | 0.013787464 | 0.010006815 | 0.37780745 |
| 7 | `tray_L` | 4 | n-Butane | -0.13496916 | 0.0094509192 | 13.281062 |
| 8 | `tray_V` | 18 | n-Propane | -0.08840759 | 0.0092364166 | 8.5716331 |
| 9 | `tray_V` | 17 | n-Propane | -0.10084004 | 0.0088596376 | 10.38196 |
| 10 | `tray_V` | 9 | n-Pentane | 0.00969472 | 0.0087086187 | 0.1132328 |
| 11 | `tray_V` | 19 | n-Pentane | 0.032723745 | 0.0087030375 | 2.7600373 |
| 12 | `tray_L` | 10 | n-Pentane | -0.014443001 | 0.0084608437 | 0.70704025 |
| 13 | `tray_V` | 18 | n-Pentane | 0.027129844 | 0.0082889099 | 2.2730292 |
| 14 | `tray_L` | 4 | n-Propane | 0.17527004 | 0.0082766328 | 20.17649 |
| 15 | `tray_L` | 3 | n-Propane | 0.2044158 | 0.0080992703 | 24.238792 |
| 16 | `tray_V` | 19 | n-Propane | -0.062973442 | 0.0078866345 | 6.9848308 |
| 17 | `tray_V` | 16 | n-Propane | -0.10439133 | 0.0078747623 | 12.256442 |
| 18 | `tray_V` | 4 | n-Butane | 0.065644595 | 0.0077662422 | 7.4525558 |
| 19 | `tray_L` | 5 | n-Propane | 0.13371582 | 0.0074735239 | 16.891938 |
| 20 | `tray_V` | 5 | n-Butane | 0.068092055 | 0.0074228594 | 8.1732918 |
