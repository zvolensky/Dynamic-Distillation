# Column Initialization Residual Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_initializer_boundary_window_trial1_20260601.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `parity`
- Pressure model: `spec`
- Vapor flow model: `profile`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.017905042 1/s`
- Worst absolute state rate: `1306.9795 per s`
- Max tray total material residual: `1.7510733 lbmol/h`
- Total state inventory residual: `-0.70138171 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_L` | 0.017905042 | 0.31762137 | 5 | n-Butane |
| `tray_V` | 0.010775886 | 0.11133125 | 10 | n-Pentane |
| `tray_EL_BTU` | 0.0051286094 | 1306.9795 | 5 |  |
| `bottom_L` | 0.0033155561 | 0.12748287 | 21 | n-Propane |
| `top_L` | 0.0011665402 | 0.28878922 | 0 | n-Butane |
| `bottom_T_f` | 0 | 0 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |
| `tray_EV_BTU` | 0 | 0 | 1 |  |
| `tray_T_f` | 0 | 0 | 1 |  |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_L` | 5 | n-Butane | -0.29724203 | 0.017905042 | 15.601024 |
| 2 | `tray_L` | 5 | n-Propane | 0.31762137 | 0.017751314 | 16.892837 |
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
| 13 | `tray_V` | 5 | n-Butane | 0.069170269 | 0.0075985426 | 8.1030968 |
| 14 | `tray_L` | 16 | n-Propane | 0.09599994 | 0.0073022034 | 12.146709 |
| 15 | `tray_L` | 11 | n-Pentane | -0.014584676 | 0.0072093348 | 1.0230266 |
| 16 | `tray_V` | 17 | n-Pentane | 0.020947664 | 0.0071678697 | 1.9224394 |
| 17 | `tray_L` | 17 | n-Propane | 0.082931434 | 0.0070210429 | 10.81184 |
| 18 | `tray_V` | 12 | n-Pentane | 0.012840806 | 0.0070086706 | 0.83213141 |
| 19 | `tray_V` | 15 | n-Propane | -0.1024589 | 0.0067881957 | 14.093687 |
| 20 | `tray_V` | 6 | n-Butane | 0.065493707 | 0.0066467139 | 8.8535469 |
