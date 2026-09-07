# Column Initialization Residual Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_iterative_coupled_closure_continue_20260531\c3c4_coupled_cont_iter03_blend0.0156.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `parity`
- Pressure model: `spec`
- Vapor flow model: `profile`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.027583634 1/s`
- Worst absolute state rate: `0.19850029 per s`
- Max tray total material residual: `0.09 lbmol/h`
- Total state inventory residual: `0.004 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_L` | 0.027583634 | 0.19850029 | 2 | n-Pentane |
| `tray_V` | 0.016502701 | 0.18919959 | 19 | n-Pentane |
| `bottom_L` | 0.00046403626 | 0.049111657 | 21 | n-Pentane |
| `top_L` | 5.7062881e-11 | 1.4109947e-08 | 0 | n-Pentane |
| `bottom_T_f` | 0 | 0 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |
| `tray_T_f` | 0 | 0 | 1 |  |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_L` | 2 | n-Pentane | 0.029392307 | 0.027583634 | 0.065570507 |
| 2 | `tray_V` | 19 | n-Pentane | 0.061112799 | 0.016502701 | 2.7031997 |
| 3 | `tray_V` | 19 | n-Propane | 0.096449214 | 0.014804771 | 5.5147389 |
| 4 | `tray_V` | 3 | n-Butane | 0.12708687 | 0.013420612 | 8.4695289 |
| 5 | `tray_V` | 2 | n-Butane | 0.1139731 | 0.01331892 | 7.557233 |
| 6 | `tray_V` | 11 | n-Pentane | 0.023324628 | 0.013070862 | 0.78447503 |
| 7 | `tray_L` | 2 | n-Butane | 0.10509373 | 0.012570414 | 7.3604035 |
| 8 | `tray_L` | 3 | n-Butane | -0.13580123 | 0.012319914 | 10.022905 |
| 9 | `tray_V` | 18 | n-Propane | -0.099973967 | 0.012024375 | 7.3142758 |
| 10 | `tray_L` | 11 | n-Pentane | -0.023672467 | 0.01103647 | 1.144931 |
| 11 | `tray_V` | 4 | n-Butane | 0.11676388 | 0.010602259 | 10.013114 |
| 12 | `tray_V` | 17 | n-Propane | -0.10129231 | 0.0099918139 | 9.1375299 |
| 13 | `tray_L` | 12 | n-Pentane | 0.04335546 | 0.0097991234 | 3.4244223 |
| 14 | `tray_V` | 3 | n-Propane | -0.18867476 | 0.0096234163 | 18.605798 |
| 15 | `tray_V` | 4 | n-Propane | -0.15578509 | 0.0090368729 | 16.238827 |
| 16 | `tray_L` | 4 | n-Butane | -0.12226521 | 0.008889079 | 12.754541 |
| 17 | `tray_V` | 16 | n-Propane | -0.097359098 | 0.008188317 | 10.890001 |
| 18 | `tray_V` | 2 | n-Propane | -0.18919959 | 0.0080841792 | 22.403686 |
| 19 | `tray_L` | 10 | n-Pentane | -0.013012282 | 0.007975069 | 0.63162002 |
| 20 | `tray_L` | 19 | n-Pentane | -0.053448114 | 0.0079473608 | 5.7252659 |
