# Column Initialization Residual Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_iterative_coupled_closure_20260531\c3c4_coupled_iter05_blend0.0488.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `parity`
- Pressure model: `spec`
- Vapor flow model: `profile`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.02833078 1/s`
- Worst absolute state rate: `0.1971659 per s`
- Max tray total material residual: `0.09 lbmol/h`
- Total state inventory residual: `0.004 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_L` | 0.02833078 | 0.1971659 | 2 | n-Pentane |
| `tray_V` | 0.016092008 | 0.18757094 | 19 | n-Propane |
| `bottom_L` | 0.00046382544 | 0.048671912 | 21 | n-Pentane |
| `top_L` | 5.4793932e-11 | 1.3983607e-08 | 0 | n-Pentane |
| `bottom_T_f` | 0 | 0 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |
| `tray_T_f` | 0 | 0 | 1 |  |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_L` | 2 | n-Pentane | 0.03029911 | 0.02833078 | 0.069476729 |
| 2 | `tray_V` | 19 | n-Propane | 0.10458839 | 0.016092008 | 5.4993992 |
| 3 | `tray_V` | 19 | n-Pentane | 0.058857774 | 0.015857405 | 2.7116903 |
| 4 | `tray_L` | 2 | n-Butane | 0.11339381 | 0.013560194 | 7.3622556 |
| 5 | `tray_V` | 3 | n-Butane | 0.12549225 | 0.013079295 | 8.5947261 |
| 6 | `tray_V` | 2 | n-Butane | 0.11239426 | 0.012901054 | 7.7120214 |
| 7 | `tray_V` | 11 | n-Pentane | 0.023099688 | 0.012852078 | 0.7973505 |
| 8 | `tray_L` | 3 | n-Butane | -0.13447399 | 0.012231144 | 9.9943915 |
| 9 | `tray_V` | 18 | n-Propane | -0.099058737 | 0.01196006 | 7.2824619 |
| 10 | `tray_L` | 11 | n-Pentane | -0.023458195 | 0.010970749 | 1.1382491 |
| 11 | `tray_V` | 4 | n-Butane | 0.1154301 | 0.010381914 | 10.118383 |
| 12 | `tray_L` | 12 | n-Pentane | 0.044939211 | 0.010222169 | 3.3962502 |
| 13 | `tray_V` | 17 | n-Propane | -0.10036385 | 0.0099478454 | 9.0890037 |
| 14 | `tray_V` | 3 | n-Propane | -0.1870389 | 0.0096100872 | 18.462768 |
| 15 | `tray_V` | 4 | n-Propane | -0.15442398 | 0.0090220554 | 16.116275 |
| 16 | `tray_L` | 4 | n-Butane | -0.1211002 | 0.0088396179 | 12.69971 |
| 17 | `tray_V` | 16 | n-Propane | -0.096468856 | 0.008157732 | 10.825451 |
| 18 | `tray_V` | 2 | n-Propane | -0.18757094 | 0.0080748051 | 22.22916 |
| 19 | `tray_L` | 19 | n-Pentane | -0.052970054 | 0.0079332786 | 5.6769437 |
| 20 | `tray_L` | 10 | n-Pentane | -0.012894522 | 0.0079128231 | 0.62957284 |
