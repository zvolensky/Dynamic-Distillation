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
- Worst relative state rate: `0.041315884 1/s`
- Worst absolute state rate: `0.23813174 per s`
- Max tray total material residual: `0.09 lbmol/h`
- Total state inventory residual: `-0.0060691 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_V` | 0.041315884 | 0.2381313 | 2 | n-Butane |
| `tray_L` | 0.021100071 | 0.23813174 | 19 | n-Propane |
| `bottom_L` | 5.0226481e-06 | 0.00049468407 | 21 | n-Propane |
| `top_L` | 1.0200089e-09 | 1.2829282e-06 | 0 | n-Propane |
| `bottom_T_f` | 0 | 0 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |
| `tray_T_f` | 0 | 0 | 1 |  |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_V` | 2 | n-Butane | 0.1614087 | 0.041315884 | 2.9066985 |
| 2 | `tray_V` | 3 | n-Butane | 0.17499639 | 0.030657848 | 4.7080454 |
| 3 | `tray_V` | 11 | n-Pentane | 0.030082812 | 0.021524031 | 0.39763839 |
| 4 | `tray_L` | 19 | n-Propane | 0.11977447 | 0.021100071 | 4.6764961 |
| 5 | `tray_V` | 4 | n-Butane | 0.15683661 | 0.019978322 | 6.8503397 |
| 6 | `tray_V` | 19 | n-Pentane | 0.06795239 | 0.019707162 | 2.4481063 |
| 7 | `tray_L` | 2 | n-Butane | -0.16140914 | 0.018510821 | 7.7197181 |
| 8 | `tray_V` | 19 | n-Propane | -0.11946284 | 0.017125786 | 5.9756124 |
| 9 | `tray_L` | 18 | n-Propane | 0.1274661 | 0.016095481 | 6.9193718 |
| 10 | `tray_L` | 3 | n-Butane | -0.17499609 | 0.01428007 | 11.254568 |
| 11 | `tray_V` | 18 | n-Propane | -0.12747154 | 0.013750818 | 8.2701064 |
| 12 | `tray_V` | 10 | n-Pentane | 0.016535719 | 0.013707108 | 0.20636093 |
| 13 | `tray_L` | 11 | n-Pentane | -0.030082983 | 0.012599038 | 1.3877206 |
| 14 | `tray_V` | 5 | n-Butane | 0.12039114 | 0.012425529 | 8.6890154 |
| 15 | `tray_L` | 17 | n-Propane | 0.12919237 | 0.012314093 | 9.4914231 |
| 16 | `tray_V` | 17 | n-Propane | -0.1291875 | 0.011141201 | 10.595473 |
| 17 | `tray_L` | 4 | n-Propane | 0.19667928 | 0.0099878919 | 18.691771 |
| 18 | `tray_V` | 3 | n-Propane | -0.23782329 | 0.0099494916 | 22.903059 |
| 19 | `tray_L` | 4 | n-Butane | -0.15683707 | 0.0099480958 | 14.765537 |
| 20 | `tray_V` | 18 | n-Pentane | 0.028801986 | 0.0098311309 | 1.9296718 |
