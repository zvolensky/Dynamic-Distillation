# Column Initialization Residual Audit

- Excel: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_initializer_profile_coeff_trial1_20260601.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `True`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.055261611 1/s`
- Worst absolute state rate: `2828.3947 per s`
- Max tray total material residual: `2503.8244 lbmol/h`
- Total state inventory residual: `-5.9366531 lbmol/h`

## Top Boundary Diagnostics

- Total condenser boundary energy residual: `-1.8189894e-12 Btu/s`
- Total condenser boundary energy residual relative scale: `-1.3170728e-16`
- Total condenser boundary energy owner: `1`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_V` | 0.055261611 | 0.50202646 | 7 | n-Butane |
| `tray_L` | 0.019505306 | 0.2810738 | 8 | n-Propane |
| `tray_EL_BTU` | 0.01246218 | 2828.3947 | 2 |  |
| `tray_T_f` | 0.0038615454 | 0.4787244 | 2 |  |
| `bottom_L` | 0.0038121038 | 0.14657509 | 21 | n-Propane |
| `tray_EV_BTU` | 0.0038108459 | 108.31004 | 19 |  |
| `top_L` | 0.0014789185 | 0.20102683 | 0 | n-Butane |
| `bottom_T_f` | 1.2511514e-05 | 0.0027739313 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_V` | 7 | n-Butane | 0.27390401 | 0.055261611 | 3.9564969 |
| 2 | `tray_V` | 6 | n-Butane | 0.2508666 | 0.054757221 | 3.5814341 |
| 3 | `tray_V` | 8 | n-Butane | 0.25944407 | 0.049057909 | 4.288527 |
| 4 | `tray_V` | 5 | n-Butane | 0.17397274 | 0.041595682 | 3.1824712 |
| 5 | `tray_V` | 9 | n-Butane | 0.22554298 | 0.040515389 | 4.5668471 |
| 6 | `tray_V` | 3 | n-Butane | -0.13165279 | 0.038297461 | 2.4376376 |
| 7 | `tray_V` | 19 | n-Propane | -0.11428448 | 0.033776317 | 2.3835685 |
| 8 | `tray_V` | 18 | n-Propane | -0.12844588 | 0.032523108 | 2.949373 |
| 9 | `tray_V` | 2 | n-Butane | -0.26755019 | 0.03174494 | 7.4281206 |
| 10 | `tray_V` | 10 | n-Butane | 0.18293113 | 0.031604278 | 4.7881764 |
| 11 | `tray_V` | 11 | n-Butane | 0.16686562 | 0.027983038 | 4.9630988 |
| 12 | `tray_V` | 17 | n-Propane | -0.12585517 | 0.02737636 | 3.5972207 |
| 13 | `tray_V` | 8 | n-Propane | -0.21681873 | 0.02698184 | 7.0357282 |
| 14 | `tray_V` | 7 | n-Propane | -0.22548171 | 0.026812409 | 7.4096028 |
| 15 | `tray_V` | 12 | n-Pentane | 0.033193624 | 0.025829209 | 0.28511963 |
| 16 | `tray_V` | 9 | n-Propane | -0.18662586 | 0.024216791 | 6.7064651 |
| 17 | `tray_V` | 6 | n-Propane | -0.20403757 | 0.023080437 | 7.8402817 |
| 18 | `tray_V` | 16 | n-Propane | -0.11603358 | 0.022009344 | 4.2720146 |
| 19 | `tray_V` | 12 | n-Butane | 0.13415156 | 0.021986556 | 5.1015269 |
| 20 | `tray_V` | 10 | n-Propane | -0.15405775 | 0.020799123 | 6.4069351 |
