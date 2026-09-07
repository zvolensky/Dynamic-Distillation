# Column Initialization Residual Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_splitter_openloop_seed_vaporclosure_blend025_20260528.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `parity`
- Pressure model: `spec`
- Vapor flow model: `profile`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.03693263 1/s`
- Worst absolute state rate: `0.24228864 per s`
- Max tray total material residual: `0.09 lbmol/h`
- Total state inventory residual: `-0.0060691 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_V` | 0.03693263 | 0.24228864 | 2 | n-Butane |
| `tray_L` | 0.021100071 | 0.23813174 | 19 | n-Propane |
| `top_L` | 0.00032765667 | 0.043631927 | 0 | n-Butane |
| `bottom_L` | 5.0226481e-06 | 0.00049468407 | 21 | n-Propane |
| `bottom_T_f` | 0 | 0 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |
| `tray_T_f` | 0 | 0 | 1 |  |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_V` | 2 | n-Butane | 0.16554902 | 0.03693263 | 3.4824596 |
| 2 | `tray_V` | 3 | n-Butane | 0.16975067 | 0.026956247 | 5.2972664 |
| 3 | `tray_L` | 19 | n-Propane | 0.11977447 | 0.021100071 | 4.6764961 |
| 4 | `tray_L` | 2 | n-Butane | -0.16140914 | 0.018510821 | 7.7197181 |
| 5 | `tray_V` | 4 | n-Butane | 0.14633672 | 0.017476008 | 7.3735781 |
| 6 | `tray_L` | 18 | n-Propane | 0.1274661 | 0.016095481 | 6.9193718 |
| 7 | `tray_V` | 10 | n-Pentane | 0.020031626 | 0.015958231 | 0.25525355 |
| 8 | `tray_V` | 11 | n-Pentane | 0.023128637 | 0.015554516 | 0.4869403 |
| 9 | `tray_V` | 18 | n-Propane | -0.1248414 | 0.014381597 | 7.6806355 |
| 10 | `tray_L` | 3 | n-Butane | -0.17499609 | 0.01428007 | 11.254568 |
| 11 | `tray_V` | 19 | n-Propane | -0.089344633 | 0.013887441 | 5.4334845 |
| 12 | `tray_V` | 19 | n-Pentane | 0.051206626 | 0.013656812 | 2.7495301 |
| 13 | `tray_V` | 18 | n-Pentane | 0.038707966 | 0.012679546 | 2.052788 |
| 14 | `tray_L` | 11 | n-Pentane | -0.030082983 | 0.012599038 | 1.3877206 |
| 15 | `tray_L` | 17 | n-Propane | 0.12919237 | 0.012314093 | 9.4914231 |
| 16 | `tray_V` | 17 | n-Propane | -0.1283196 | 0.011675629 | 9.9903805 |
| 17 | `tray_V` | 5 | n-Butane | 0.10974115 | 0.010888179 | 9.0789259 |
| 18 | `tray_L` | 4 | n-Propane | 0.19667928 | 0.0099878919 | 18.691771 |
| 19 | `tray_V` | 3 | n-Propane | -0.23261479 | 0.009977682 | 22.31351 |
| 20 | `tray_L` | 4 | n-Butane | -0.15683707 | 0.0099480958 | 14.765537 |
