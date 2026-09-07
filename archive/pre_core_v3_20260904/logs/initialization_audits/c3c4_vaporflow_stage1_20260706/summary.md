# Column Initialization Residual Audit

- Excel: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_initializer_residual_vaporflow_stage1_20260706.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `True`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.045695469 1/s`
- Worst absolute state rate: `2828.4139 per s`
- Max tray total material residual: `852.17286 lbmol/h`
- Total state inventory residual: `-5.9366531 lbmol/h`

## Top Boundary Diagnostics

- Total condenser boundary energy residual: `-1.8189894e-12 Btu/s`
- Total condenser boundary energy residual relative scale: `-1.4719309e-16`
- Total condenser boundary energy owner: `1`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_V` | 0.045695469 | 0.31137711 | 7 | n-Butane |
| `tray_L` | 0.019505306 | 0.2810738 | 8 | n-Propane |
| `tray_EV_BTU` | 0.016738893 | 1035.6445 | 19 |  |
| `tray_EL_BTU` | 0.012462265 | 2828.4139 | 2 |  |
| `bottom_L` | 0.0038121038 | 0.14657509 | 21 | n-Propane |
| `tray_T_f` | 0.0025172275 | 0.39388842 | 5 |  |
| `top_L` | 0.0011488777 | 0.4009902 | 0 | n-Butane |
| `bottom_T_f` | 1.2511514e-05 | 0.0027739313 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_V` | 7 | n-Butane | 0.22648945 | 0.045695469 | 3.9564969 |
| 2 | `tray_V` | 8 | n-Butane | 0.22769436 | 0.0430544 | 4.288527 |
| 3 | `tray_V` | 6 | n-Butane | 0.19486114 | 0.042532782 | 3.5814341 |
| 4 | `tray_V` | 9 | n-Butane | 0.20674194 | 0.037138067 | 4.5668471 |
| 5 | `tray_V` | 6 | n-Propane | -0.31137711 | 0.035222533 | 7.8402817 |
| 6 | `tray_V` | 7 | n-Propane | -0.29206756 | 0.034730244 | 7.4096028 |
| 7 | `tray_V` | 8 | n-Propane | -0.24698152 | 0.030735424 | 7.0357282 |
| 8 | `tray_V` | 10 | n-Butane | 0.17564527 | 0.030345529 | 4.7881764 |
| 9 | `tray_V` | 5 | n-Butane | 0.12651417 | 0.030248664 | 3.1824712 |
| 10 | `tray_V` | 3 | n-Butane | -0.1035199 | 0.030113676 | 2.4376376 |
| 11 | `tray_V` | 5 | n-Propane | -0.26700407 | 0.028619919 | 8.3293091 |
| 12 | `tray_V` | 11 | n-Butane | 0.1611255 | 0.027020431 | 4.9630988 |
| 13 | `tray_V` | 9 | n-Propane | -0.19516361 | 0.02532466 | 6.7064651 |
| 14 | `tray_V` | 19 | n-Propane | -0.083469583 | 0.024669098 | 2.3835685 |
| 15 | `tray_V` | 18 | n-Propane | -0.093735403 | 0.023734249 | 2.949373 |
| 16 | `tray_V` | 12 | n-Pentane | 0.02980601 | 0.02319318 | 0.28511963 |
| 17 | `tray_V` | 18 | n-Butane | 0.21278282 | 0.021408521 | 8.9391649 |
| 18 | `tray_V` | 2 | n-Butane | -0.17972644 | 0.021324616 | 7.4281206 |
| 19 | `tray_V` | 19 | n-Butane | 0.21673007 | 0.021016107 | 9.3125695 |
| 20 | `tray_V` | 10 | n-Propane | -0.14791702 | 0.019970071 | 6.4069351 |
