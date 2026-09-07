# Column Initialization Residual Audit

- Excel: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\model_consistent_initialization\c3c4_candidate_stage2_trayVw3\coupled-flows-boundary.xlsx`
- Thermo: `table`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.008978859 1/s`
- Worst absolute state rate: `716.99977 per s`
- Max tray total material residual: `403.07253 lbmol/h`
- Total state inventory residual: `166.10742 lbmol/h`

## Top Boundary Diagnostics

- Total condenser boundary energy residual: `9.094947e-13 Btu/s`
- Total condenser boundary energy residual relative scale: `7.1054585e-17`
- Total condenser boundary energy owner: `1`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_V` | 0.008978859 | 0.14281252 | 16 | n-Pentane |
| `bottom_L` | 0.0073586438 | 0.28293927 | 21 | n-Propane |
| `tray_L` | 0.0058241513 | 0.17019568 | 19 | n-Propane |
| `tray_T_f` | 0.0057774912 | 0.71621947 | 2 |  |
| `tray_EL_BTU` | 0.0027993111 | 716.99977 | 2 |  |
| `tray_EV_BTU` | 0.0019923106 | 202.84051 | 2 |  |
| `top_L` | 0.0016351384 | 0.61079675 | 0 | n-Butane |
| `bottom_T_f` | 0.00010484352 | 0.023244887 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_V` | 16 | n-Pentane | 0.013606024 | 0.008978859 | 0.51533999 |
| 2 | `tray_V` | 17 | n-Pentane | 0.014066072 | 0.0088593512 | 0.58770904 |
| 3 | `tray_V` | 15 | n-Pentane | 0.0121406 | 0.0087387654 | 0.38928093 |
| 4 | `tray_V` | 18 | n-Pentane | 0.014423185 | 0.008697463 | 0.65832094 |
| 5 | `tray_V` | 14 | n-Pentane | 0.011544935 | 0.008667829 | 0.33192925 |
| 6 | `tray_V` | 13 | n-Pentane | 0.010970871 | 0.008592474 | 0.2768 |
| 7 | `tray_V` | 12 | n-Pentane | 0.010423361 | 0.008515214 | 0.22408674 |
| 8 | `tray_V` | 11 | n-Pentane | 0.0099092424 | 0.0084362776 | 0.1745989 |
| 9 | `tray_V` | 10 | n-Pentane | 0.0094148876 | 0.0083550399 | 0.1268513 |
| 10 | `tray_V` | 9 | n-Pentane | 0.0088467878 | 0.0081760173 | 0.082041227 |
| 11 | `tray_V` | 8 | n-Pentane | 0.0079668121 | 0.007646262 | 0.041922449 |
| 12 | `bottom_L` | 21 | n-Propane | 0.28293927 | 0.0073586438 | 37.449921 |
| 13 | `tray_L` | 19 | n-Propane | -0.11926865 | 0.0058241513 | 19.478289 |
| 14 | `tray_V` | 18 | n-Butane | 0.046063555 | 0.0057976671 | 6.945188 |
| 15 | `tray_T_f` | 2 |  | -0.71621947 | 0.0057774912 | 122.96721 |
| 16 | `tray_V` | 17 | n-Butane | 0.044963979 | 0.0057376669 | 6.836631 |
| 17 | `tray_V` | 16 | n-Butane | 0.043526556 | 0.0056411657 | 6.7158796 |
| 18 | `tray_L` | 9 | n-Pentane | -0.0086289702 | 0.0054331123 | 0.58821863 |
| 19 | `tray_V` | 19 | n-Butane | 0.042410139 | 0.0052776398 | 7.0358154 |
| 20 | `tray_V` | 2 | n-Propane | -0.14281252 | 0.0052744792 | 26.076137 |
