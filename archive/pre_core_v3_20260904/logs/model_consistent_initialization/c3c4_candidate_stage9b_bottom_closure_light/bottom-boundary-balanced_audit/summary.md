# Column Initialization Residual Audit

- Excel: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\model_consistent_initialization\c3c4_candidate_stage9b_bottom_closure_light\bottom-boundary-balanced.xlsx`
- Thermo: `table`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.0063798959 1/s`
- Worst absolute state rate: `355.56096 per s`
- Max tray total material residual: `125.96949 lbmol/h`
- Total state inventory residual: `597.17206 lbmol/h`

## Top Boundary Diagnostics

- Total condenser boundary energy residual: `0 Btu/s`
- Total condenser boundary energy residual relative scale: `0`
- Total condenser boundary energy owner: `1`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_V` | 0.0063798959 | 0.059401014 | 19 | n-Butane |
| `tray_L` | 0.0031757684 | 0.11222732 | 16 | n-Pentane |
| `tray_T_f` | 0.0029668895 | 0.37346061 | 3 |  |
| `tray_EL_BTU` | 0.0014086779 | 355.56096 | 2 |  |
| `bottom_L` | 0.001033764 | 0.26448344 | 21 | n-Propane |
| `top_L` | 0.00095113814 | 0.61422862 | 0 | n-Butane |
| `tray_EV_BTU` | 0.0005899873 | 28.956604 | 19 |  |
| `bottom_T_f` | 0.0001812579 | 0.040186741 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_V` | 19 | n-Butane | 0.059401014 | 0.0063798959 | 8.3106558 |
| 2 | `tray_V` | 19 | n-Pentane | 0.0063171338 | 0.0046441925 | 0.36022221 |
| 3 | `tray_V` | 18 | n-Pentane | 0.0056722965 | 0.0042907688 | 0.32197675 |
| 4 | `tray_V` | 19 | n-Propane | -0.020946184 | 0.0042011534 | 3.9858176 |
| 5 | `tray_V` | 17 | n-Pentane | 0.0053858345 | 0.0041920975 | 0.28475888 |
| 6 | `tray_V` | 16 | n-Pentane | 0.0051080904 | 0.0040899363 | 0.24894131 |
| 7 | `tray_V` | 15 | n-Pentane | 0.0046335309 | 0.0038997581 | 0.18815855 |
| 8 | `tray_V` | 14 | n-Pentane | 0.0043194571 | 0.0037175134 | 0.16192105 |
| 9 | `tray_V` | 13 | n-Pentane | 0.0040350608 | 0.0035464099 | 0.13778747 |
| 10 | `tray_V` | 12 | n-Pentane | 0.0037723359 | 0.0033814395 | 0.11560058 |
| 11 | `tray_V` | 11 | n-Pentane | 0.0035332051 | 0.0032249994 | 0.0955677 |
| 12 | `tray_L` | 16 | n-Pentane | 0.014606266 | 0.0031757684 | 3.5992855 |
| 13 | `tray_L` | 17 | n-Pentane | 0.013591797 | 0.0031375403 | 3.3319911 |
| 14 | `tray_V` | 10 | n-Pentane | 0.0033276718 | 0.0030908121 | 0.076633491 |
| 15 | `tray_L` | 18 | n-Pentane | 0.011714151 | 0.0029805908 | 2.9301439 |
| 16 | `tray_V` | 9 | n-Pentane | 0.0031454212 | 0.0029702691 | 0.05896841 |
| 17 | `tray_T_f` | 3 |  | 0.37346061 | 0.0029668895 | 124.87614 |
| 18 | `tray_L` | 12 | n-Pentane | 0.014197176 | 0.0029192674 | 3.8632668 |
| 19 | `tray_L` | 13 | n-Pentane | 0.01329347 | 0.0028773785 | 3.6199936 |
| 20 | `tray_V` | 8 | n-Pentane | 0.0029800167 | 0.0028585855 | 0.042479443 |
