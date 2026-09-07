# Column Initialization Residual Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_splitter_openloop_seed_lsq_stage2_18_19_20260531_r3.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `parity`
- Pressure model: `spec`
- Vapor flow model: `profile`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.030657858 1/s`
- Worst absolute state rate: `0.25131724 per s`
- Max tray total material residual: `0.09 lbmol/h`
- Total state inventory residual: `0.004 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_V` | 0.030657858 | 0.23782329 | 3 | n-Butane |
| `tray_L` | 0.019315462 | 0.25131724 | 2 | n-Butane |
| `bottom_L` | 0.0032940425 | 0.12771032 | 21 | n-Propane |
| `top_L` | 0.001209251 | 0.16099133 | 0 | n-Butane |
| `bottom_T_f` | 0 | 0 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |
| `tray_T_f` | 0 | 0 | 1 |  |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_V` | 3 | n-Butane | 0.17499639 | 0.030657858 | 4.7080434 |
| 2 | `tray_V` | 11 | n-Pentane | 0.030082812 | 0.021524032 | 0.39763835 |
| 3 | `tray_V` | 4 | n-Butane | 0.15683661 | 0.01997832 | 6.8503404 |
| 4 | `tray_L` | 2 | n-Butane | -0.17459393 | 0.019315462 | 8.0390763 |
| 5 | `tray_V` | 10 | n-Pentane | 0.016535719 | 0.013707109 | 0.20636084 |
| 6 | `tray_L` | 3 | n-Butane | -0.16181129 | 0.013204171 | 11.254559 |
| 7 | `tray_L` | 11 | n-Pentane | -0.030082983 | 0.012599037 | 1.3877209 |
| 8 | `tray_V` | 5 | n-Butane | 0.12039114 | 0.012425531 | 8.6890136 |
| 9 | `tray_L` | 17 | n-Propane | 0.12919237 | 0.012314088 | 9.4914279 |
| 10 | `tray_L` | 4 | n-Propane | 0.19667928 | 0.0099878873 | 18.69178 |
| 11 | `tray_V` | 3 | n-Propane | -0.23782329 | 0.0099494955 | 22.90305 |
| 12 | `tray_L` | 4 | n-Butane | -0.15683707 | 0.0099480913 | 14.765544 |
| 13 | `tray_V` | 18 | n-Pentane | 0.031057845 | 0.0098721717 | 2.1459993 |
| 14 | `tray_V` | 17 | n-Pentane | 0.026264593 | 0.0098250159 | 1.6732366 |
| 15 | `tray_V` | 19 | n-Pentane | 0.036318262 | 0.0098023925 | 2.7050405 |
| 16 | `tray_L` | 16 | n-Propane | 0.12410413 | 0.0097906963 | 11.67572 |
| 17 | `tray_L` | 10 | n-Pentane | -0.016535631 | 0.0095272419 | 0.73561569 |
| 18 | `tray_V` | 19 | n-Propane | -0.077284023 | 0.0094637435 | 7.1663269 |
| 19 | `tray_V` | 4 | n-Propane | -0.19667882 | 0.0094010971 | 19.920837 |
| 20 | `tray_L` | 3 | n-Propane | 0.22463748 | 0.0092608412 | 23.256704 |
