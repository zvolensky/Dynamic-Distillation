# Column Initialization Residual Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_splitter_openloop_seed_20260526.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.99171931 1/s`
- Worst absolute state rate: `9096.7235 per s`
- Max tray total material residual: `7961.8786 lbmol/h`
- Total state inventory residual: `-0.0060691 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_EL_BTU` | 0.99171931 | 9096.7235 | 12 |  |
| `tray_V` | 0.095166065 | 1.7631122 | 2 | n-Butane |
| `tray_EV_BTU` | 0.055555218 | 472.05144 | 19 |  |
| `tray_L` | 0.021100071 | 0.23813174 | 19 | n-Propane |
| `tray_T_f` | 0.0011186966 | 0.14299627 | 2 |  |
| `bottom_L` | 5.0226481e-06 | 0.00049468407 | 21 | n-Propane |
| `top_L` | 3.7559185e-07 | 0.00047240504 | 0 | n-Propane |
| `bottom_T_f` | 3.5630762e-08 | 7.8976654e-06 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_EL_BTU` | 12 |  | -9096.7235 | 0.99171931 | 9171.6797 |
| 2 | `tray_V` | 2 | n-Butane | 0.37178512 | 0.095166065 | 2.9066985 |
| 3 | `tray_V` | 2 | n-Propane | 1.7631122 | 0.061545712 | 27.647198 |
| 4 | `tray_EV_BTU` | 19 |  | -472.05144 | 0.055555218 | 8495.9775 |
| 5 | `tray_V` | 3 | n-Butane | 0.22660193 | 0.039698691 | 4.7080454 |
| 6 | `tray_V` | 19 | n-Propane | -0.2553985 | 0.036613058 | 5.9756124 |
| 7 | `tray_V` | 18 | n-Propane | -0.30694616 | 0.033111396 | 8.2701064 |
| 8 | `tray_V` | 4 | n-Butane | 0.25163994 | 0.032054656 | 6.8503397 |
| 9 | `tray_V` | 17 | n-Propane | -0.34729304 | 0.029950745 | 10.595473 |
| 10 | `tray_V` | 11 | n-Pentane | 0.039590834 | 0.028326951 | 0.39763839 |
| 11 | `tray_V` | 15 | n-Propane | -0.44006501 | 0.027748749 | 14.858914 |
| 12 | `tray_V` | 5 | n-Butane | 0.26521456 | 0.027372705 | 8.6890154 |
| 13 | `tray_V` | 16 | n-Propane | -0.37530402 | 0.02713815 | 12.829388 |
| 14 | `tray_V` | 14 | n-Propane | -0.45294399 | 0.025728457 | 16.604787 |
| 15 | `tray_V` | 6 | n-Butane | 0.26877269 | 0.024318391 | 10.05224 |
| 16 | `tray_V` | 13 | n-Propane | -0.45782932 | 0.024055218 | 18.032433 |
| 17 | `tray_V` | 7 | n-Butane | 0.26925247 | 0.022577505 | 10.925696 |
| 18 | `tray_V` | 8 | n-Butane | 0.2670658 | 0.021478112 | 11.434324 |
| 19 | `tray_L` | 19 | n-Propane | 0.11977447 | 0.021100071 | 4.6764961 |
| 20 | `tray_V` | 11 | n-Propane | 0.27876306 | 0.020863839 | 12.361063 |
