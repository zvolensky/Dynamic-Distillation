# Column Initialization Residual Audit

- Excel: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_initializer_profile_coeff_trial1_liqenergy_topboundary2_11_noeq_20260602.xlsx`
- Thermo: `table`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.023511888 1/s`
- Worst absolute state rate: `2439.7305 per s`
- Max tray total material residual: `78.204555 lbmol/h`
- Total state inventory residual: `-5.9366531 lbmol/h`

## Top Boundary Diagnostics

- Total condenser boundary energy residual: `-1.8189894e-12 Btu/s`
- Total condenser boundary energy residual relative scale: `-1.2678097e-16`
- Total condenser boundary energy owner: `1`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_V` | 0.023511888 | 0.12320326 | 18 | n-Propane |
| `tray_L` | 0.011614218 | 0.19628944 | 3 | n-Butane |
| `tray_EL_BTU` | 0.0082258456 | 2439.7305 | 2 |  |
| `tray_EV_BTU` | 0.0039244789 | 111.53966 | 19 |  |
| `tray_T_f` | 0.0034019935 | 0.42173565 | 2 |  |
| `bottom_L` | 0.0018821464 | 0.072368378 | 21 | n-Propane |
| `top_L` | 0.0014775795 | 0.20183813 | 0 | n-Butane |
| `bottom_T_f` | 6.7281034e-06 | 0.0014916897 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_V` | 18 | n-Propane | -0.092857216 | 0.023511888 | 2.949373 |
| 2 | `tray_V` | 17 | n-Propane | -0.10386395 | 0.022592771 | 3.5972207 |
| 3 | `tray_V` | 16 | n-Propane | -0.10719999 | 0.02033378 | 4.2720146 |
| 4 | `tray_V` | 15 | n-Propane | -0.10192085 | 0.019233744 | 4.2990643 |
| 5 | `tray_V` | 3 | n-Butane | 0.063664661 | 0.018519887 | 2.4376376 |
| 6 | `tray_V` | 4 | n-Butane | 0.069905685 | 0.018458308 | 2.7872206 |
| 7 | `tray_V` | 5 | n-Butane | 0.071756019 | 0.017156369 | 3.1824712 |
| 8 | `tray_V` | 14 | n-Propane | -0.095476085 | 0.016319922 | 4.8502784 |
| 9 | `tray_V` | 18 | n-Pentane | 0.0282543 | 0.015615165 | 0.80941416 |
| 10 | `tray_V` | 6 | n-Butane | 0.069447959 | 0.015158564 | 3.5814341 |
| 11 | `tray_V` | 15 | n-Butane | 0.11007592 | 0.014918809 | 6.3783311 |
| 12 | `tray_V` | 14 | n-Butane | 0.10149065 | 0.014680404 | 5.913342 |
| 13 | `tray_V` | 13 | n-Propane | -0.090005372 | 0.014135032 | 5.3675395 |
| 14 | `tray_V` | 13 | n-Butane | 0.089889347 | 0.013866662 | 5.4824068 |
| 15 | `tray_V` | 12 | n-Butane | 0.08293161 | 0.013591944 | 5.1015269 |
| 16 | `tray_V` | 10 | n-Pentane | 0.015104047 | 0.013515589 | 0.11752788 |
| 17 | `tray_V` | 11 | n-Pentane | 0.016031763 | 0.013368121 | 0.19925331 |
| 18 | `tray_V` | 17 | n-Pentane | 0.021494029 | 0.012683579 | 0.69463442 |
| 19 | `tray_V` | 7 | n-Butane | 0.061978471 | 0.012504491 | 3.9564969 |
| 20 | `tray_V` | 16 | n-Butane | 0.10976072 | 0.012354345 | 7.8843816 |
