# Column Initialization Residual Audit

- Excel: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_initializer_residual_coupled_stage4_20260706.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `True`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.012620463 1/s`
- Worst absolute state rate: `2826.6616 per s`
- Max tray total material residual: `473.05405 lbmol/h`
- Total state inventory residual: `-9.459763 lbmol/h`

## Top Boundary Diagnostics

- Total condenser boundary energy residual: `-9.094947e-13 Btu/s`
- Total condenser boundary energy residual relative scale: `-8.0846888e-17`
- Total condenser boundary energy owner: `1`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_EV_BTU` | 0.012620463 | 1047.9797 | 2 |  |
| `tray_EL_BTU` | 0.012617518 | 2826.6616 | 2 |  |
| `tray_V` | 0.0074649435 | 0.18419087 | 9 | n-Pentane |
| `bottom_L` | 0.0049085543 | 0.18940722 | 21 | n-Propane |
| `tray_T_f` | 0.0047776904 | 0.59230095 | 2 |  |
| `tray_L` | 0.0045310951 | 0.054094266 | 19 | n-Pentane |
| `top_L` | 0.00061166442 | 0.48399251 | 0 | n-Butane |
| `bottom_T_f` | 0.00029473234 | 0.065345192 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_EV_BTU` | 2 |  | 1047.9797 | 0.012620463 | 83037.131 |
| 2 | `tray_EL_BTU` | 2 |  | 2826.6616 | 0.012617518 | -224025.74 |
| 3 | `tray_V` | 9 | n-Pentane | 0.0080168214 | 0.0074649435 | 0.073929281 |
| 4 | `tray_V` | 8 | n-Pentane | 0.0071711836 | 0.0069523817 | 0.031471504 |
| 5 | `tray_V` | 2 | n-Propane | -0.18419087 | 0.0051126485 | 35.026508 |
| 6 | `bottom_L` | 21 | n-Propane | 0.18940722 | 0.0049085543 | 37.58717 |
| 7 | `tray_T_f` | 2 |  | 0.59230095 | 0.0047776904 | 122.97223 |
| 8 | `tray_L` | 19 | n-Pentane | 0.028384155 | 0.0045310951 | 5.2643035 |
| 9 | `tray_L` | 18 | n-Pentane | 0.029142331 | 0.0043531953 | 5.6944688 |
| 10 | `tray_L` | 3 | n-Butane | 0.040211139 | 0.004349202 | 8.2456361 |
| 11 | `tray_L` | 12 | n-Pentane | -0.022522324 | 0.0040981306 | 4.4957554 |
| 12 | `tray_L` | 8 | n-Pentane | -0.005043641 | 0.0040959942 | 0.23135943 |
| 13 | `tray_L` | 9 | n-Pentane | -0.0058929019 | 0.0040749014 | 0.4461459 |
| 14 | `tray_V` | 10 | n-Pentane | 0.0045109095 | 0.0039464076 | 0.14304195 |
| 15 | `tray_V` | 17 | n-Butane | 0.037416286 | 0.0037885319 | 8.8761965 |
| 16 | `tray_V` | 16 | n-Butane | 0.035286758 | 0.0037843153 | 8.3244763 |
| 17 | `tray_V` | 7 | n-Pentane | 0.0036494991 | 0.0036012652 | 0.013393599 |
| 18 | `tray_EV_BTU` | 8 |  | -85.736985 | 0.0034080596 | 25156.126 |
| 19 | `tray_V` | 18 | n-Butane | 0.035048688 | 0.0034012096 | 9.3047714 |
| 20 | `tray_EV_BTU` | 7 |  | -82.311089 | 0.0032963515 | 24969.362 |
