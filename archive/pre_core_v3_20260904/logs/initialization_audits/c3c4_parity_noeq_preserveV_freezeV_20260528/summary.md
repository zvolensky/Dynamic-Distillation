# Column Initialization Residual Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_splitter_openloop_seed_20260526.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `parity`
- Pressure model: `spec`
- Vapor flow model: `profile`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.021100071 1/s`
- Worst absolute state rate: `0.23813174 per s`
- Max tray total material residual: `276.07 lbmol/h`
- Total state inventory residual: `318.90393 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_L` | 0.021100071 | 0.23813174 | 19 | n-Propane |
| `bottom_L` | 5.0226481e-06 | 0.00049468407 | 21 | n-Propane |
| `top_L` | 1.0200089e-09 | 1.2829282e-06 | 0 | n-Propane |
| `bottom_T_f` | 0 | 0 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |
| `tray_T_f` | 0 | 0 | 1 |  |
| `tray_V` | 0 | 0 | 1 | n-Propane |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_L` | 19 | n-Propane | 0.11977447 | 0.021100071 | 4.6764961 |
| 2 | `tray_L` | 2 | n-Butane | -0.16140914 | 0.018510821 | 7.7197181 |
| 3 | `tray_L` | 18 | n-Propane | 0.1274661 | 0.016095481 | 6.9193718 |
| 4 | `tray_L` | 3 | n-Butane | -0.17499609 | 0.01428007 | 11.254568 |
| 5 | `tray_L` | 11 | n-Pentane | -0.030082983 | 0.012599038 | 1.3877206 |
| 6 | `tray_L` | 17 | n-Propane | 0.12919237 | 0.012314093 | 9.4914231 |
| 7 | `tray_L` | 4 | n-Propane | 0.19667928 | 0.0099878919 | 18.691771 |
| 8 | `tray_L` | 4 | n-Butane | -0.15683707 | 0.0099480958 | 14.765537 |
| 9 | `tray_L` | 3 | n-Propane | 0.23782299 | 0.0098044151 | 23.256724 |
| 10 | `tray_L` | 16 | n-Propane | 0.12410413 | 0.0097906981 | 11.675718 |
| 11 | `tray_L` | 10 | n-Pentane | -0.016535631 | 0.0095272394 | 0.73561614 |
| 12 | `tray_L` | 15 | n-Propane | 0.11275247 | 0.0089545461 | 11.591646 |
| 13 | `tray_L` | 5 | n-Propane | 0.14041208 | 0.0086324612 | 15.265591 |
| 14 | `tray_L` | 19 | n-Pentane | -0.067817242 | 0.0082585933 | 7.2117184 |
| 15 | `tray_L` | 2 | n-Propane | 0.23813174 | 0.007566517 | 30.471777 |
| 16 | `tray_L` | 14 | n-Propane | 0.09699265 | 0.0069430376 | 12.969772 |
| 17 | `tray_L` | 5 | n-Butane | -0.12039036 | 0.0066046514 | 17.228118 |
| 18 | `tray_L` | 6 | n-Propane | 0.091152534 | 0.0064889969 | 13.047246 |
| 19 | `tray_L` | 9 | n-Pentane | -0.0087437238 | 0.0063375208 | 0.37967577 |
| 20 | `tray_L` | 13 | n-Propane | 0.079315023 | 0.0051075754 | 14.528899 |
