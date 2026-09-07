# Column Initialization Residual Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_initializer_specdof_feedT_trial3_20260531.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `parity`
- Pressure model: `spec`
- Vapor flow model: `profile`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.030422562 1/s`
- Worst absolute state rate: `3954.4846 per s`
- Max tray total material residual: `31.668146 lbmol/h`
- Total state inventory residual: `-23.597643 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_V` | 0.030422562 | 0.60527126 | 12 | n-Butane |
| `tray_L` | 0.02510461 | 0.9119983 | 12 | n-Butane |
| `tray_EL_BTU` | 0.011846141 | 3954.4846 | 2 |  |
| `bottom_L` | 0.0033237739 | 0.12779884 | 21 | n-Propane |
| `top_L` | 0.0022144923 | 0.29308167 | 0 | n-Butane |
| `bottom_T_f` | 0 | 0 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |
| `tray_EV_BTU` | 0 | 0 | 1 |  |
| `tray_T_f` | 0 | 0 | 1 |  |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_V` | 12 | n-Butane | 0.60527126 | 0.030422562 | 18.895473 |
| 2 | `tray_V` | 12 | n-Pentane | 0.071155192 | 0.028573485 | 1.4902525 |
| 3 | `tray_L` | 12 | n-Butane | -0.9119983 | 0.02510461 | 35.327922 |
| 4 | `tray_V` | 11 | n-Pentane | 0.034076216 | 0.021732367 | 0.56799373 |
| 5 | `tray_V` | 12 | n-Propane | 0.35803165 | 0.020108687 | 16.804824 |
| 6 | `tray_V` | 10 | n-Pentane | 0.023823426 | 0.018423224 | 0.29311931 |
| 7 | `tray_L` | 2 | n-Butane | -0.15528641 | 0.018254981 | 7.506523 |
| 8 | `tray_V` | 9 | n-Pentane | 0.014399436 | 0.012791842 | 0.1256734 |
| 9 | `tray_L` | 3 | n-Butane | -0.14106066 | 0.012519642 | 10.267148 |
| 10 | `tray_EL_BTU` | 2 |  | 3954.4846 | 0.011846141 | -333819.49 |
| 11 | `tray_L` | 12 | n-Pentane | -0.047537177 | 0.011447031 | 3.1527953 |
| 12 | `tray_L` | 4 | n-Butane | -0.13472459 | 0.0094410346 | 13.270108 |
| 13 | `tray_V` | 18 | n-Propane | -0.089103102 | 0.0094142456 | 8.4647097 |
| 14 | `tray_L` | 11 | n-Pentane | -0.019928231 | 0.0091786279 | 1.1711558 |
| 15 | `tray_L` | 10 | n-Pentane | -0.015756984 | 0.0090554646 | 0.74005249 |
| 16 | `tray_V` | 17 | n-Propane | -0.10082041 | 0.0089421957 | 10.274681 |
| 17 | `tray_V` | 13 | n-Pentane | 0.015764414 | 0.0088130753 | 0.78875291 |
| 18 | `tray_V` | 19 | n-Pentane | 0.031738268 | 0.0085908926 | 2.6944087 |
| 19 | `tray_V` | 18 | n-Pentane | 0.02676924 | 0.0083292743 | 2.2138742 |
| 20 | `tray_L` | 4 | n-Propane | 0.17502542 | 0.0082608082 | 20.187446 |
