# Column Initialization Residual Audit

- Excel: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_model_consistent_seed_candidate_stage7_bottom_state_balanced.xlsx`
- Thermo: `table`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.0049868945 1/s`
- Worst absolute state rate: `467.58396 per s`
- Max tray total material residual: `187.50343 lbmol/h`
- Total state inventory residual: `-229.07824 lbmol/h`

## Top Boundary Diagnostics

- Total condenser boundary energy residual: `9.094947e-13 Btu/s`
- Total condenser boundary energy residual relative scale: `7.5784937e-17`
- Total condenser boundary energy owner: `1`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `bottom_L` | 0.0049868945 | 0.34087466 | 21 | n-Propane |
| `tray_L` | 0.0033286902 | 0.057538055 | 16 | n-Pentane |
| `tray_V` | 0.0032580877 | 0.0046592413 | 17 | n-Pentane |
| `tray_T_f` | 0.0029293911 | 0.36874046 | 3 |  |
| `tray_EL_BTU` | 0.0018532149 | 467.58396 | 2 |  |
| `top_L` | 0.00086611702 | 0.51379169 | 0 | n-Butane |
| `tray_EV_BTU` | 0.00058126811 | 37.477261 | 17 |  |
| `bottom_T_f` | 0.00016601899 | 0.036808117 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `bottom_L` | 21 | n-Propane | 0.29474947 | 0.0049868945 | 58.104814 |
| 2 | `tray_L` | 16 | n-Pentane | 0.014623835 | 0.0033286902 | 3.3932701 |
| 3 | `tray_L` | 17 | n-Pentane | 0.013658285 | 0.0033053869 | 3.132129 |
| 4 | `tray_V` | 17 | n-Pentane | 0.0040974637 | 0.0032580877 | 0.25762843 |
| 5 | `tray_V` | 16 | n-Pentane | 0.004004362 | 0.0032580208 | 0.22907808 |
| 6 | `tray_V` | 18 | n-Pentane | 0.0041899706 | 0.0032562884 | 0.28673206 |
| 7 | `tray_V` | 19 | n-Pentane | 0.0042319556 | 0.0032155468 | 0.31609206 |
| 8 | `tray_V` | 15 | n-Pentane | 0.0037527063 | 0.0031904262 | 0.17623981 |
| 9 | `tray_L` | 18 | n-Pentane | 0.011877056 | 0.0031611438 | 2.7572021 |
| 10 | `tray_V` | 14 | n-Pentane | 0.0036067976 | 0.0031243841 | 0.15440275 |
| 11 | `tray_V` | 13 | n-Pentane | 0.0034768663 | 0.0030666364 | 0.13377194 |
| 12 | `tray_V` | 12 | n-Pentane | 0.0033633367 | 0.0030185532 | 0.11422147 |
| 13 | `tray_L` | 19 | n-Pentane | 0.010381136 | 0.0030166866 | 2.441238 |
| 14 | `tray_L` | 12 | n-Pentane | 0.014308716 | 0.0030137084 | 3.7478766 |
| 15 | `tray_V` | 7 | n-Pentane | 0.0030879607 | 0.0030056335 | 0.027390944 |
| 16 | `tray_V` | 8 | n-Pentane | 0.0031247851 | 0.0029936545 | 0.043802853 |
| 17 | `tray_L` | 13 | n-Pentane | 0.013378096 | 0.0029840029 | 3.4832718 |
| 18 | `tray_V` | 11 | n-Pentane | 0.0032687245 | 0.0029824249 | 0.095995556 |
| 19 | `tray_L` | 15 | n-Pentane | 0.012195962 | 0.0029767743 | 3.0970395 |
| 20 | `tray_V` | 9 | n-Pentane | 0.0031571018 | 0.0029763832 | 0.060717535 |
