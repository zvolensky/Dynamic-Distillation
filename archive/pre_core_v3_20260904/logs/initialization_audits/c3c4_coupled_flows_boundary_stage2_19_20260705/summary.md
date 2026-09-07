# Column Initialization Residual Audit

- Excel: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_initializer_coupled_flows_boundary_stage2_19_20260705.xlsx`
- Thermo: `table`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.011363638 1/s`
- Worst absolute state rate: `979.79567 per s`
- Max tray total material residual: `549.07809 lbmol/h`
- Total state inventory residual: `-8.0402936 lbmol/h`

## Top Boundary Diagnostics

- Total condenser boundary energy residual: `3.6379788e-12 Btu/s`
- Total condenser boundary energy residual relative scale: `2.7096745e-16`
- Total condenser boundary energy owner: `1`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_V` | 0.011363638 | 0.33176765 | 15 | n-Butane |
| `tray_L` | 0.0069936068 | 0.21139219 | 4 | n-Butane |
| `tray_T_f` | 0.0057274146 | 0.71001162 | 2 |  |
| `bottom_L` | 0.0036961762 | 0.14211768 | 21 | n-Propane |
| `tray_EL_BTU` | 0.0036237671 | 979.79567 | 2 |  |
| `tray_EV_BTU` | 0.0023252415 | 141.3619 | 19 |  |
| `top_L` | 0.0013446298 | 0.48275928 | 0 | n-Butane |
| `bottom_T_f` | 1.6680911e-05 | 0.0036983295 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_V` | 15 | n-Butane | 0.082941275 | 0.011363638 | 6.2988312 |
| 2 | `tray_V` | 14 | n-Butane | 0.079063269 | 0.011232804 | 6.0386048 |
| 3 | `tray_V` | 13 | n-Butane | 0.074010321 | 0.010935089 | 5.7681499 |
| 4 | `tray_V` | 10 | n-Pentane | 0.012033887 | 0.010695864 | 0.12509716 |
| 5 | `tray_V` | 11 | n-Pentane | 0.012653584 | 0.010610676 | 0.19253321 |
| 6 | `tray_V` | 2 | n-Propane | -0.33176765 | 0.010516644 | 30.546914 |
| 7 | `tray_V` | 12 | n-Butane | 0.068130038 | 0.010488164 | 5.4958972 |
| 8 | `tray_V` | 15 | n-Pentane | 0.015111737 | 0.010293727 | 0.46805292 |
| 9 | `tray_V` | 12 | n-Pentane | 0.012952505 | 0.010268551 | 0.26137613 |
| 10 | `tray_V` | 16 | n-Pentane | 0.016493915 | 0.010201488 | 0.61681456 |
| 11 | `tray_V` | 14 | n-Pentane | 0.014174945 | 0.010129882 | 0.39931977 |
| 12 | `tray_V` | 13 | n-Pentane | 0.013430738 | 0.010093856 | 0.33058545 |
| 13 | `tray_V` | 17 | n-Pentane | 0.017190926 | 0.010092711 | 0.70330104 |
| 14 | `tray_V` | 16 | n-Butane | 0.084700853 | 0.0099492587 | 7.5132827 |
| 15 | `tray_V` | 11 | n-Butane | 0.062146074 | 0.0099472905 | 5.2475378 |
| 16 | `tray_V` | 17 | n-Butane | 0.087394439 | 0.0099003296 | 7.8274272 |
| 17 | `tray_V` | 9 | n-Pentane | 0.010391475 | 0.0097428923 | 0.066569812 |
| 18 | `tray_V` | 18 | n-Butane | 0.087972228 | 0.0096758777 | 8.091912 |
| 19 | `tray_V` | 18 | n-Pentane | 0.017247817 | 0.009665555 | 0.78446212 |
| 20 | `tray_V` | 10 | n-Butane | 0.056858496 | 0.0094974522 | 4.9867103 |
