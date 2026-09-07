# Column Initialization Residual Audit

- Excel: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_initializer_residual_vapor_state_stage2_20260706.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `True`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.0141759 1/s`
- Worst absolute state rate: `2891.6814 per s`
- Max tray total material residual: `594.22326 lbmol/h`
- Total state inventory residual: `-5.9366531 lbmol/h`

## Top Boundary Diagnostics

- Total condenser boundary energy residual: `0 Btu/s`
- Total condenser boundary energy residual relative scale: `0`
- Total condenser boundary energy owner: `1`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_EV_BTU` | 0.0141759 | 1174.3683 | 2 |  |
| `tray_EL_BTU` | 0.012741028 | 2891.6814 | 2 |  |
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
| 1 | `tray_EV_BTU` | 2 |  | 1174.3683 | 0.0141759 | 82841.594 |
| 2 | `tray_EL_BTU` | 2 |  | 2891.6814 | 0.012741028 | -226957.25 |
| 3 | `tray_EV_BTU` | 19 |  | 360.45889 | 0.012682603 | 28420.522 |
| 4 | `tray_V` | 19 | n-Butane | 0.10050697 | 0.0095541834 | 9.5196816 |
| 5 | `tray_EV_BTU` | 18 |  | 260.78733 | 0.0091631736 | 28459.372 |
| 6 | `tray_V` | 18 | n-Butane | 0.094179005 | 0.0091465295 | 9.2966928 |
| 7 | `tray_V` | 9 | n-Pentane | 0.0094805689 | 0.0088578766 | 0.070298144 |
| 8 | `tray_V` | 17 | n-Butane | 0.08015238 | 0.0081252945 | 8.8645507 |
| 9 | `tray_EV_BTU` | 17 |  | 220.10332 | 0.0077219178 | 28502.711 |
| 10 | `tray_L` | 12 | n-Pentane | -0.040152952 | 0.007046057 | 4.6986413 |
| 11 | `tray_EV_BTU` | 6 |  | -174.50528 | 0.0069952599 | 24945.218 |
| 12 | `tray_V` | 16 | n-Butane | 0.065002382 | 0.0069819583 | 8.3100501 |
| 13 | `tray_V` | 8 | n-Pentane | 0.0071888409 | 0.0069777081 | 0.030258175 |
| 14 | `tray_EV_BTU` | 5 |  | -171.543 | 0.0068714802 | 24963.49 |
| 15 | `tray_EV_BTU` | 16 |  | 183.26262 | 0.0064200675 | 28544.28 |
| 16 | `tray_V` | 10 | n-Pentane | 0.0071981531 | 0.0063193404 | 0.13906716 |
| 17 | `tray_EV_BTU` | 7 |  | -154.61751 | 0.0062007286 | 24934.378 |
| 18 | `tray_V` | 2 | n-Propane | -0.21901098 | 0.0060829033 | 35.004351 |
| 19 | `tray_L` | 9 | n-Pentane | -0.0087190441 | 0.0059258665 | 0.47135346 |
| 20 | `tray_L` | 19 | n-Pentane | 0.036090701 | 0.0058615842 | 5.1571581 |
