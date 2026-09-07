# Column Initialization Residual Audit

- Excel: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\model_consistent_initialization\c3c4_candidate_stage10_lower_interface\bottom-boundary-balanced.xlsx`
- Thermo: `table`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.041108567 1/s`
- Worst absolute state rate: `465.06945 per s`
- Max tray total material residual: `637.41151 lbmol/h`
- Total state inventory residual: `530.71523 lbmol/h`

## Top Boundary Diagnostics

- Total condenser boundary energy residual: `9.094947e-13 Btu/s`
- Total condenser boundary energy residual relative scale: `8.5291137e-17`
- Total condenser boundary energy owner: `1`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_V` | 0.041108567 | 0.29554438 | 14 | n-Butane |
| `tray_EV_BTU` | 0.016029644 | 394.82103 | 14 |  |
| `tray_L` | 0.0048750642 | 0.11941703 | 17 | n-Pentane |
| `tray_T_f` | 0.0026981305 | 0.33963026 | 3 |  |
| `tray_EL_BTU` | 0.0018481835 | 465.06945 | 2 |  |
| `bottom_L` | 0.0011219198 | 0.27330556 | 21 | n-Propane |
| `top_L` | 0.00062242763 | 0.38725604 | 0 | n-Butane |
| `bottom_T_f` | 0.00018611089 | 0.041262699 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_V` | 14 | n-Butane | 0.29554438 | 0.041108567 | 6.1893623 |
| 2 | `tray_V` | 14 | n-Propane | -0.11399419 | 0.019535822 | 4.8351368 |
| 3 | `tray_EV_BTU` | 14 |  | 394.82103 | 0.016029644 | 24629.68 |
| 4 | `tray_V` | 14 | n-Pentane | 0.01294297 | 0.011216863 | 0.15388503 |
| 5 | `tray_L` | 17 | n-Pentane | 0.019868344 | 0.0048750642 | 3.075504 |
| 6 | `tray_L` | 16 | n-Pentane | 0.021204918 | 0.0048052195 | 3.4128927 |
| 7 | `tray_L` | 18 | n-Pentane | 0.017210527 | 0.0047778069 | 2.6021814 |
| 8 | `tray_L` | 19 | n-Pentane | 0.014904535 | 0.0046863881 | 2.1803886 |
| 9 | `tray_L` | 15 | n-Pentane | 0.017496341 | 0.0042235496 | 3.1425678 |
| 10 | `tray_L` | 16 | n-Propane | 0.085664167 | 0.0038697268 | 21.137007 |
| 11 | `tray_L` | 17 | n-Propane | 0.080412672 | 0.0038276049 | 20.008613 |
| 12 | `tray_L` | 18 | n-Propane | 0.068667831 | 0.0036381539 | 17.874361 |
| 13 | `tray_L` | 19 | n-Propane | 0.058979445 | 0.0034931763 | 15.884188 |
| 14 | `tray_L` | 15 | n-Propane | 0.066160595 | 0.0033662021 | 18.654374 |
| 15 | `tray_V` | 13 | n-Pentane | 0.0032301547 | 0.0028516914 | 0.13271537 |
| 16 | `tray_L` | 19 | n-Butane | -0.11941703 | 0.0027604623 | 42.259796 |
| 17 | `tray_V` | 12 | n-Pentane | 0.0030569637 | 0.0027468672 | 0.11289097 |
| 18 | `tray_T_f` | 3 |  | 0.33963026 | 0.0026981305 | 124.87614 |
| 19 | `tray_V` | 11 | n-Pentane | 0.0029472796 | 0.0026925213 | 0.094617002 |
| 20 | `tray_V` | 10 | n-Pentane | 0.0028669393 | 0.0026623136 | 0.076860123 |
