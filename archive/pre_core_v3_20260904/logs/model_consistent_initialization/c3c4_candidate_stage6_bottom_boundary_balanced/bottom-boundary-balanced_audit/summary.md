# Column Initialization Residual Audit

- Excel: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\model_consistent_initialization\c3c4_candidate_stage6_bottom_boundary_balanced\bottom-boundary-balanced.xlsx`
- Thermo: `table`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.0056903958 1/s`
- Worst absolute state rate: `484.61281 per s`
- Max tray total material residual: `160.25381 lbmol/h`
- Total state inventory residual: `50.275535 lbmol/h`

## Top Boundary Diagnostics

- Total condenser boundary energy residual: `0 Btu/s`
- Total condenser boundary energy residual relative scale: `0`
- Total condenser boundary energy owner: `1`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `bottom_L` | 0.0056903958 | 0.44114241 | 21 | n-Propane |
| `tray_L` | 0.0038941599 | 0.050247644 | 17 | n-Pentane |
| `tray_V` | 0.0034991309 | 0.004475829 | 16 | n-Pentane |
| `tray_T_f` | 0.0029587849 | 0.37244043 | 3 |  |
| `tray_EL_BTU` | 0.0019187265 | 484.61281 | 2 |  |
| `top_L` | 0.001172803 | 0.64587613 | 0 | n-Butane |
| `tray_EV_BTU` | 0.00061038917 | 32.664776 | 19 |  |
| `bottom_T_f` | 0.00027125297 | 0.060139573 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `bottom_L` | 21 | n-Propane | 0.21879527 | 0.0056903958 | 37.449921 |
| 2 | `tray_L` | 17 | n-Pentane | 0.015506015 | 0.0038941599 | 2.9818639 |
| 3 | `tray_L` | 16 | n-Pentane | 0.01662182 | 0.0038857005 | 3.2776895 |
| 4 | `tray_L` | 18 | n-Pentane | 0.013501257 | 0.0037680649 | 2.5830745 |
| 5 | `tray_L` | 19 | n-Pentane | 0.011828099 | 0.0036424506 | 2.2472916 |
| 6 | `tray_V` | 16 | n-Pentane | 0.0043035065 | 0.0034991309 | 0.22987868 |
| 7 | `tray_V` | 7 | n-Pentane | 0.0035906139 | 0.0034952357 | 0.027288079 |
| 8 | `tray_V` | 17 | n-Pentane | 0.0043784466 | 0.0034834045 | 0.25694464 |
| 9 | `tray_V` | 18 | n-Pentane | 0.004455086 | 0.0034687895 | 0.2843345 |
| 10 | `tray_L` | 15 | n-Pentane | 0.013931211 | 0.0034581254 | 3.0285442 |
| 11 | `tray_V` | 8 | n-Pentane | 0.0036107965 | 0.0034565398 | 0.044627471 |
| 12 | `tray_L` | 12 | n-Pentane | 0.016404405 | 0.0034529406 | 3.7508507 |
| 13 | `tray_V` | 15 | n-Pentane | 0.004057353 | 0.0034443919 | 0.17795917 |
| 14 | `tray_L` | 13 | n-Pentane | 0.015307878 | 0.0034302875 | 3.4625642 |
| 15 | `tray_V` | 19 | n-Pentane | 0.004475829 | 0.0034120249 | 0.31178085 |
| 16 | `tray_L` | 14 | n-Pentane | 0.014277838 | 0.0034062224 | 3.1916928 |
| 17 | `tray_V` | 9 | n-Pentane | 0.0036173138 | 0.0034050427 | 0.062340217 |
| 18 | `tray_V` | 14 | n-Pentane | 0.0039359446 | 0.0034024406 | 0.15680039 |
| 19 | `tray_V` | 6 | n-Pentane | 0.0034328692 | 0.0033956088 | 0.010973104 |
| 20 | `tray_V` | 13 | n-Pentane | 0.0038309095 | 0.0033706999 | 0.13653237 |
