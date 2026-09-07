# Column Initialization Residual Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_initializer_chemsep_specs_energy_trial7_boundary_seed_20260531__restart_20260601_103656.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.098680895 1/s`
- Worst absolute state rate: `2829.7158 per s`
- Max tray total material residual: `19257.336 lbmol/h`
- Total state inventory residual: `-5.9366531 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_T_f` | 0.098680895 | 13.531912 | 5 |  |
| `tray_EV_BTU` | 0.06487345 | 2829.7158 | 12 |  |
| `tray_V` | 0.0621037 | 2.952855 | 2 | n-Propane |
| `tray_L` | 0.026345103 | 0.6318586 | 2 | n-Propane |
| `top_L` | 0.014195184 | 1.3224854 | 0 | n-Pentane |
| `bottom_L` | 0.0058658931 | 0.4088022 | 21 | n-Propane |
| `tray_EL_BTU` | 0.0024991944 | 661.98782 | 2 |  |
| `bottom_T_f` | 1.6795123e-08 | 3.7236514e-06 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_T_f` | 5 |  | 13.531912 | 0.098680895 | 136.12798 |
| 2 | `tray_EV_BTU` | 12 |  | -31.637385 | 0.06487345 | 486.67848 |
| 3 | `tray_EV_BTU` | 13 |  | -15.285315 | 0.063564017 | 239.47119 |
| 4 | `tray_V` | 2 | n-Propane | -2.299306 | 0.0621037 | 36.023655 |
| 5 | `tray_EV_BTU` | 14 |  | -5.4548296 | 0.061218297 | 88.104562 |
| 6 | `tray_EV_BTU` | 11 |  | -113.23067 | 0.057265009 | 1976.3099 |
| 7 | `tray_EV_BTU` | 16 |  | -1.3393523 | 0.052183406 | 24.666249 |
| 8 | `tray_V` | 2 | n-Butane | -2.952855 | 0.050842352 | 57.078646 |
| 9 | `tray_EV_BTU` | 10 |  | -181.62475 | 0.049949654 | 3635.1563 |
| 10 | `tray_EV_BTU` | 17 |  | -0.21244771 | 0.04962357 | 3.2811855 |
| 11 | `tray_EV_BTU` | 15 |  | -1.8315121 | 0.046977085 | 37.98735 |
| 12 | `tray_EV_BTU` | 9 |  | -292.3222 | 0.042048563 | 6951.0139 |
| 13 | `tray_EV_BTU` | 8 |  | -394.50096 | 0.035514531 | 11107.156 |
| 14 | `tray_V` | 2 | n-Pentane | -0.17103701 | 0.034125161 | 4.0120499 |
| 15 | `tray_EV_BTU` | 18 |  | -0.048626273 | 0.029588037 | 0.64344373 |
| 16 | `tray_EV_BTU` | 7 |  | -500.3114 | 0.029474039 | 16973.647 |
| 17 | `tray_V` | 19 | n-Pentane | 0.062763187 | 0.028643727 | 1.1911669 |
| 18 | `tray_EV_BTU` | 6 |  | -649.23298 | 0.026817299 | 24208.485 |
| 19 | `tray_L` | 2 | n-Propane | 0.6318586 | 0.026345103 | 22.983911 |
| 20 | `tray_EV_BTU` | 5 |  | -708.00595 | 0.021717612 | 32599.544 |
