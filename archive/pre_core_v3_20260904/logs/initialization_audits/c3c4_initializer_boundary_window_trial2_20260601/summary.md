# Column Initialization Residual Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_initializer_boundary_window_trial2_20260601.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `parity`
- Pressure model: `spec`
- Vapor flow model: `profile`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.018797057 1/s`
- Worst absolute state rate: `1254.8858 per s`
- Max tray total material residual: `2.8239056 lbmol/h`
- Total state inventory residual: `-1.1305146 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_L` | 0.018797057 | 0.29171354 | 6 | n-Propane |
| `tray_V` | 0.010775886 | 0.11133125 | 10 | n-Pentane |
| `tray_EL_BTU` | 0.0049399755 | 1254.8858 | 6 |  |
| `bottom_L` | 0.0033155561 | 0.12748287 | 21 | n-Propane |
| `top_L` | 0.0011413964 | 0.30098414 | 0 | n-Butane |
| `bottom_T_f` | 0 | 0 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |
| `tray_EV_BTU` | 0 | 0 | 1 |  |
| `tray_T_f` | 0 | 0 | 1 |  |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_L` | 6 | n-Propane | 0.29171354 | 0.018797057 | 14.519107 |
| 2 | `tray_L` | 6 | n-Butane | -0.28229549 | 0.015403918 | 17.326214 |
| 3 | `tray_V` | 10 | n-Pentane | 0.013209288 | 0.010775886 | 0.22581921 |
| 4 | `tray_V` | 11 | n-Pentane | 0.013797203 | 0.01001343 | 0.37786987 |
| 5 | `tray_V` | 18 | n-Propane | -0.090264578 | 0.0094601942 | 8.5415143 |
| 6 | `tray_V` | 19 | n-Pentane | 0.0347102 | 0.0091240213 | 2.8042655 |
| 7 | `tray_V` | 17 | n-Propane | -0.10184364 | 0.0089573384 | 10.369855 |
| 8 | `tray_V` | 9 | n-Pentane | 0.0096971039 | 0.0087109997 | 0.11320218 |
| 9 | `tray_V` | 18 | n-Pentane | 0.028180791 | 0.0085437951 | 2.2983927 |
| 10 | `tray_L` | 10 | n-Pentane | -0.014442323 | 0.0084606302 | 0.70700327 |
| 11 | `tray_V` | 19 | n-Propane | -0.065157352 | 0.0082255064 | 6.9213788 |
| 12 | `tray_V` | 16 | n-Propane | -0.10491068 | 0.0079156009 | 12.253659 |
| 13 | `tray_L` | 16 | n-Propane | 0.09599994 | 0.0073022034 | 12.146709 |
| 14 | `tray_L` | 11 | n-Pentane | -0.014584676 | 0.0072093348 | 1.0230266 |
| 15 | `tray_V` | 17 | n-Pentane | 0.020947664 | 0.0071678697 | 1.9224394 |
| 16 | `tray_L` | 17 | n-Propane | 0.082931434 | 0.0070210429 | 10.81184 |
| 17 | `tray_V` | 12 | n-Pentane | 0.012840806 | 0.0070086706 | 0.83213141 |
| 18 | `tray_V` | 15 | n-Propane | -0.1024589 | 0.0067881957 | 14.093687 |
| 19 | `tray_V` | 6 | n-Butane | 0.065493707 | 0.0066467139 | 8.8535469 |
| 20 | `tray_L` | 9 | n-Pentane | -0.0091755208 | 0.0065664192 | 0.39734009 |
