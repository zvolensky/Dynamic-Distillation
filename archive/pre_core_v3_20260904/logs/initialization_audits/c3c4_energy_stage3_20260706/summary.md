# Column Initialization Residual Audit

- Excel: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_initializer_residual_energy_stage3_20260706.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `True`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.012400006 1/s`
- Worst absolute state rate: `2777.9329 per s`
- Max tray total material residual: `594.22326 lbmol/h`
- Total state inventory residual: `-5.9366531 lbmol/h`

## Top Boundary Diagnostics

- Total condenser boundary energy residual: `-1.8189894e-12 Btu/s`
- Total condenser boundary energy residual relative scale: `-1.5636514e-16`
- Total condenser boundary energy owner: `1`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_EL_BTU` | 0.012400006 | 2777.9329 | 2 |  |
| `tray_EV_BTU` | 0.01146858 | 952.32943 | 2 |  |
| `tray_V` | 0.0095541834 | 0.21901098 | 19 | n-Butane |
| `tray_L` | 0.007046057 | 0.060384183 | 12 | n-Pentane |
| `bottom_L` | 0.0038121038 | 0.14657509 | 21 | n-Propane |
| `tray_T_f` | 0.0037239137 | 0.4616619 | 2 |  |
| `top_L` | 0.00067466403 | 0.44733177 | 0 | n-Butane |
| `bottom_T_f` | 1.2511514e-05 | 0.0027739313 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_EL_BTU` | 2 |  | 2777.9329 | 0.012400006 | -224025.74 |
| 2 | `tray_EV_BTU` | 2 |  | 952.32943 | 0.01146858 | 83037.131 |
| 3 | `tray_V` | 19 | n-Butane | 0.10050697 | 0.0095541834 | 9.5196816 |
| 4 | `tray_V` | 18 | n-Butane | 0.094179005 | 0.0091465295 | 9.2966928 |
| 5 | `tray_V` | 9 | n-Pentane | 0.0094805689 | 0.0088578766 | 0.070298144 |
| 6 | `tray_V` | 17 | n-Butane | 0.08015238 | 0.0081252945 | 8.8645507 |
| 7 | `tray_L` | 12 | n-Pentane | -0.040152952 | 0.007046057 | 4.6986413 |
| 8 | `tray_V` | 16 | n-Butane | 0.065002382 | 0.0069819583 | 8.3100501 |
| 9 | `tray_V` | 8 | n-Pentane | 0.0071888409 | 0.0069777081 | 0.030258175 |
| 10 | `tray_V` | 10 | n-Pentane | 0.0071981531 | 0.0063193404 | 0.13906716 |
| 11 | `tray_V` | 2 | n-Propane | -0.21901098 | 0.0060829033 | 35.004351 |
| 12 | `tray_L` | 9 | n-Pentane | -0.0087190441 | 0.0059258665 | 0.47135346 |
| 13 | `tray_L` | 19 | n-Pentane | 0.036090701 | 0.0058615842 | 5.1571581 |
| 14 | `tray_EV_BTU` | 18 |  | 164.98306 | 0.0057975861 | 28456.2 |
| 15 | `tray_EV_BTU` | 17 |  | 163.48633 | 0.0056609462 | 28878.683 |
| 16 | `tray_L` | 3 | n-Butane | 0.049800026 | 0.0054836858 | 8.0814879 |
| 17 | `tray_L` | 18 | n-Pentane | 0.036191979 | 0.0054494321 | 5.6414221 |
| 18 | `tray_EV_BTU` | 19 |  | 151.40342 | 0.0054376536 | 27842.521 |
| 19 | `tray_V` | 15 | n-Butane | 0.041171241 | 0.0053124858 | 6.7499013 |
| 20 | `tray_EV_BTU` | 6 |  | -122.1644 | 0.0049452919 | 24702.173 |
