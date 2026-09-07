# Column Initialization Residual Audit

- Excel: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_checkpoint_guided_seed_from_900s_fixed2_20260708.xlsx`
- Thermo: `table`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.2057522 1/s`
- Worst absolute state rate: `57887.557 per s`
- Max tray total material residual: `4103.3123 lbmol/h`
- Total state inventory residual: `-5.9366531 lbmol/h`

## Top Boundary Diagnostics

- Total condenser boundary energy residual: `1.8189894e-12 Btu/s`
- Total condenser boundary energy residual relative scale: `1.6750193e-16`
- Total condenser boundary energy owner: `1`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_EL_BTU` | 0.2057522 | 57887.557 | 12 |  |
| `tray_EV_BTU` | 0.093428568 | 2655.3821 | 19 |  |
| `tray_V` | 0.019816068 | 0.57880212 | 2 | n-Butane |
| `tray_T_f` | 0.0075631588 | 1.3675405 | 12 |  |
| `tray_L` | 0.0029058657 | 0.04511876 | 12 | n-Butane |
| `bottom_L` | 0.0015477034 | 0.37738026 | 21 | n-Propane |
| `top_L` | 0.0014934562 | 0.87707046 | 0 | n-Pentane |
| `bottom_T_f` | 5.6869427e-06 | 0.0012608537 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_EL_BTU` | 12 |  | 57887.557 | 0.2057522 | -281344.99 |
| 2 | `tray_EL_BTU` | 13 |  | -52903.407 | 0.19291717 | -274227.6 |
| 3 | `tray_EV_BTU` | 19 |  | 2655.3821 | 0.093428568 | 28420.522 |
| 4 | `tray_EV_BTU` | 16 |  | 803.29193 | 0.028140972 | 28544.28 |
| 5 | `tray_EL_BTU` | 2 |  | -5564.3516 | 0.024517071 | -226957.25 |
| 6 | `tray_EL_BTU` | 19 |  | -5981.7681 | 0.020084331 | -297831.58 |
| 7 | `tray_V` | 2 | n-Butane | -0.57880212 | 0.019816068 | 28.208727 |
| 8 | `tray_V` | 2 | n-Propane | -0.5710897 | 0.019734461 | 27.938702 |
| 9 | `tray_V` | 2 | n-Pentane | -0.063855164 | 0.015311112 | 3.1705113 |
| 10 | `tray_EV_BTU` | 12 |  | -322.41208 | 0.012925337 | 24943.192 |
| 11 | `tray_EV_BTU` | 9 |  | 313.97544 | 0.012593185 | 24931.17 |
| 12 | `tray_EL_BTU` | 15 |  | 2226.9514 | 0.0082086135 | -271293.46 |
| 13 | `tray_EL_BTU` | 6 |  | 1953.1168 | 0.0081841643 | -238644.85 |
| 14 | `tray_EL_BTU` | 5 |  | 1904.7928 | 0.0080439698 | -236796.61 |
| 15 | `tray_EV_BTU` | 15 |  | -197.23401 | 0.0079242971 | 24888.78 |
| 16 | `tray_EV_BTU` | 2 |  | -633.56521 | 0.0076478195 | 82841.594 |
| 17 | `tray_T_f` | 12 |  | -1.3675405 | 0.0075631588 | 179.81605 |
| 18 | `tray_V` | 19 | n-Pentane | 0.015516652 | 0.0067823823 | 1.287788 |
| 19 | `tray_EV_BTU` | 4 |  | 168.74354 | 0.006753291 | 24985.861 |
| 20 | `tray_EL_BTU` | 11 |  | -1548.0043 | 0.0066619169 | -232365.2 |
