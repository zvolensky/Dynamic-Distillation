# Column Initialization Residual Audit

- Excel: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_initializer_trayV_comp_stage14_18_20260705.xlsx`
- Thermo: `table`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.088070937 1/s`
- Worst absolute state rate: `2439.6707 per s`
- Max tray total material residual: `2545.1388 lbmol/h`
- Total state inventory residual: `-5.9366531 lbmol/h`

## Top Boundary Diagnostics

- Total condenser boundary energy residual: `-1.8189894e-12 Btu/s`
- Total condenser boundary energy residual relative scale: `-1.2678024e-16`
- Total condenser boundary energy owner: `1`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_V` | 0.088070937 | 0.70094001 | 13 | n-Propane |
| `tray_L` | 0.011614218 | 0.19628944 | 3 | n-Butane |
| `tray_EL_BTU` | 0.0082256439 | 2439.6707 | 2 |  |
| `tray_EV_BTU` | 0.0039244789 | 111.53966 | 19 |  |
| `tray_T_f` | 0.0034021378 | 0.42175353 | 2 |  |
| `bottom_L` | 0.0018821464 | 0.072368378 | 21 | n-Propane |
| `top_L` | 0.0014775795 | 0.20183813 | 0 | n-Butane |
| `bottom_T_f` | 6.7281034e-06 | 0.0014916897 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_V` | 13 | n-Propane | -0.56079517 | 0.088070937 | 5.3675395 |
| 2 | `tray_V` | 13 | n-Butane | 0.52622305 | 0.081177109 | 5.4824068 |
| 3 | `tray_V` | 13 | n-Pentane | 0.099401474 | 0.07330452 | 0.35600742 |
| 4 | `tray_V` | 4 | n-Butane | 0.087025511 | 0.022978728 | 2.7872206 |
| 5 | `tray_V` | 3 | n-Butane | 0.078086978 | 0.022715302 | 2.4376376 |
| 6 | `tray_V` | 5 | n-Butane | 0.089595322 | 0.021421623 | 3.1824712 |
| 7 | `tray_V` | 2 | n-Propane | -0.70094001 | 0.019974253 | 34.092176 |
| 8 | `tray_V` | 6 | n-Butane | 0.086966561 | 0.018982388 | 3.5814341 |
| 9 | `tray_V` | 12 | n-Butane | 0.10787234 | 0.017679565 | 5.1015269 |
| 10 | `tray_V` | 7 | n-Butane | 0.079613027 | 0.016062358 | 3.9564969 |
| 11 | `tray_V` | 11 | n-Pentane | 0.016859217 | 0.014058095 | 0.19925331 |
| 12 | `tray_V` | 10 | n-Pentane | 0.015563524 | 0.013926744 | 0.11752788 |
| 13 | `tray_V` | 8 | n-Butane | 0.069017518 | 0.013050424 | 4.288527 |
| 14 | `tray_V` | 12 | n-Pentane | 0.015356058 | 0.011949128 | 0.28511963 |
| 15 | `tray_V` | 19 | n-Pentane | -0.022841538 | 0.011650532 | 0.96055752 |
| 16 | `tray_L` | 3 | n-Butane | -0.13306927 | 0.011614218 | 10.457445 |
| 17 | `tray_V` | 9 | n-Butane | 0.059737504 | 0.01073094 | 4.5668471 |
| 18 | `tray_V` | 9 | n-Pentane | 0.011288558 | 0.010668981 | 0.058072781 |
| 19 | `tray_V` | 2 | n-Butane | -0.080012544 | 0.0094935214 | 7.4281206 |
| 20 | `tray_L` | 4 | n-Butane | -0.14239914 | 0.0092942137 | 14.321268 |
