# Column Initialization Residual Audit

- Excel: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\model_consistent_initialization\smoke_20260705\coupled-vle-topL.xlsx`
- Thermo: `table`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.023622972 1/s`
- Worst absolute state rate: `2439.7305 per s`
- Max tray total material residual: `2544.8739 lbmol/h`
- Total state inventory residual: `-5.9366531 lbmol/h`

## Top Boundary Diagnostics

- Total condenser boundary energy residual: `-1.8189894e-12 Btu/s`
- Total condenser boundary energy residual relative scale: `-1.2678097e-16`
- Total condenser boundary energy owner: `1`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_V` | 0.023622972 | 0.7008796 | 18 | n-Propane |
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
| 1 | `tray_V` | 18 | n-Propane | -0.093295928 | 0.023622972 | 2.949373 |
| 2 | `tray_V` | 4 | n-Butane | 0.087026621 | 0.022979021 | 2.7872206 |
| 3 | `tray_V` | 3 | n-Butane | 0.078088047 | 0.022715613 | 2.4376376 |
| 4 | `tray_V` | 17 | n-Propane | -0.10329361 | 0.022468708 | 3.5972207 |
| 5 | `tray_V` | 5 | n-Butane | 0.08959642 | 0.021421886 | 3.1824712 |
| 6 | `tray_V` | 2 | n-Propane | -0.7008796 | 0.019972532 | 34.092176 |
| 7 | `tray_V` | 16 | n-Propane | -0.10528431 | 0.019970413 | 4.2720146 |
| 8 | `tray_V` | 6 | n-Butane | 0.086967634 | 0.018982623 | 3.5814341 |
| 9 | `tray_V` | 15 | n-Butane | 0.13821353 | 0.018732357 | 6.3783311 |
| 10 | `tray_V` | 14 | n-Butane | 0.12866388 | 0.018610952 | 5.913342 |
| 11 | `tray_V` | 13 | n-Butane | 0.11595286 | 0.017887317 | 5.4824068 |
| 12 | `tray_V` | 12 | n-Butane | 0.10787027 | 0.017679226 | 5.1015269 |
| 13 | `tray_V` | 7 | n-Butane | 0.079614106 | 0.016062576 | 3.9564969 |
| 14 | `tray_V` | 15 | n-Propane | -0.08295579 | 0.0156548 | 4.2990643 |
| 15 | `tray_V` | 18 | n-Pentane | 0.028133902 | 0.015548625 | 0.80941416 |
| 16 | `tray_V` | 11 | n-Pentane | 0.016859262 | 0.014058132 | 0.19925331 |
| 17 | `tray_V` | 10 | n-Pentane | 0.015563552 | 0.013926769 | 0.11752788 |
| 18 | `tray_V` | 8 | n-Butane | 0.069018605 | 0.013050629 | 4.288527 |
| 19 | `tray_V` | 16 | n-Butane | 0.11329628 | 0.012752297 | 7.8843816 |
| 20 | `tray_V` | 17 | n-Pentane | 0.021604164 | 0.012748569 | 0.69463442 |
