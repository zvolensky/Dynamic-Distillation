# Column Initialization Residual Audit

- Excel: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_initializer_residual_vapor_state_stage2_20260706.xlsx`
- Thermo: `table`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.053786704 1/s`
- Worst absolute state rate: `2591.3603 per s`
- Max tray total material residual: `639.56157 lbmol/h`
- Total state inventory residual: `-5.9366531 lbmol/h`

## Top Boundary Diagnostics

- Total condenser boundary energy residual: `0 Btu/s`
- Total condenser boundary energy residual relative scale: `0`
- Total condenser boundary energy owner: `1`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_V` | 0.053786704 | 0.30982807 | 3 | n-Butane |
| `tray_L` | 0.014652805 | 0.19628944 | 3 | n-Butane |
| `tray_EV_BTU` | 0.014169598 | 1173.8462 | 2 |  |
| `tray_T_f` | 0.013191509 | 1.6353809 | 2 |  |
| `tray_EL_BTU` | 0.011417784 | 2591.3603 | 2 |  |
| `bottom_L` | 0.0018821464 | 0.072368378 | 21 | n-Propane |
| `top_L` | 0.00067517939 | 0.44696629 | 0 | n-Butane |
| `bottom_T_f` | 6.7281034e-06 | 0.0014916897 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_V` | 3 | n-Butane | 0.17967947 | 0.053786704 | 2.3405927 |
| 2 | `tray_V` | 4 | n-Butane | 0.14414903 | 0.034261587 | 3.2073074 |
| 3 | `tray_V` | 19 | n-Propane | 0.069272104 | 0.022123743 | 2.1311204 |
| 4 | `tray_V` | 5 | n-Butane | 0.099789247 | 0.020168717 | 3.947724 |
| 5 | `tray_V` | 18 | n-Pentane | 0.034696815 | 0.018819746 | 0.84363892 |
| 6 | `tray_V` | 4 | n-Propane | -0.17540142 | 0.018565154 | 8.4478836 |
| 7 | `tray_V` | 3 | n-Propane | -0.19308996 | 0.018361999 | 9.5157375 |
| 8 | `tray_V` | 11 | n-Pentane | 0.021601103 | 0.017588839 | 0.22811417 |
| 9 | `tray_V` | 17 | n-Propane | -0.069134921 | 0.016622869 | 3.1590246 |
| 10 | `tray_V` | 17 | n-Pentane | 0.027113552 | 0.01588103 | 0.70729176 |
| 11 | `tray_V` | 5 | n-Propane | -0.13509529 | 0.01577497 | 7.5639016 |
| 12 | `tray_V` | 16 | n-Propane | -0.07555609 | 0.015593481 | 3.8453639 |
| 13 | `tray_V` | 15 | n-Butane | 0.1186914 | 0.015315214 | 6.7499013 |
| 14 | `tray_V` | 16 | n-Butane | 0.14077731 | 0.015121005 | 8.3100501 |
| 15 | `tray_V` | 14 | n-Butane | 0.10884716 | 0.014961473 | 6.2751628 |
| 16 | `tray_L` | 3 | n-Butane | -0.13306927 | 0.014652805 | 8.0814879 |
| 17 | `tray_V` | 15 | n-Propane | -0.071705565 | 0.014559624 | 3.92496 |
| 18 | `tray_EV_BTU` | 2 |  | 1173.8462 | 0.014169598 | 82841.594 |
| 19 | `tray_V` | 17 | n-Butane | 0.13915784 | 0.014106861 | 8.8645507 |
| 20 | `tray_V` | 13 | n-Butane | 0.094656379 | 0.013830117 | 5.8442214 |
