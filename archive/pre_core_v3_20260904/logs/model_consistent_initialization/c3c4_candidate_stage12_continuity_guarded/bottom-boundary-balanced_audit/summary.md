# Column Initialization Residual Audit

- Excel: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\model_consistent_initialization\c3c4_candidate_stage12_continuity_guarded\bottom-boundary-balanced.xlsx`
- Thermo: `table`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.0064983928 1/s`
- Worst absolute state rate: `487.82891 per s`
- Max tray total material residual: `83.664795 lbmol/h`
- Total state inventory residual: `219.83595 lbmol/h`

## Top Boundary Diagnostics

- Total condenser boundary energy residual: `9.094947e-13 Btu/s`
- Total condenser boundary energy residual relative scale: `8.0097763e-17`
- Total condenser boundary energy owner: `1`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_V` | 0.0064983928 | 0.017953109 | 19 | n-Pentane |
| `tray_T_f` | 0.0028675479 | 0.36095587 | 3 |  |
| `tray_L` | 0.0024794103 | 0.081147824 | 16 | n-Pentane |
| `tray_EL_BTU` | 0.0019048597 | 487.82891 | 2 |  |
| `bottom_L` | 0.0012063344 | 0.32478432 | 21 | n-Propane |
| `top_L` | 0.00086419072 | 0.54873684 | 0 | n-Butane |
| `tray_EV_BTU` | 0.00036914558 | 22.675142 | 17 |  |
| `bottom_T_f` | 0.000220411 | 0.048867386 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_V` | 19 | n-Pentane | 0.0090314987 | 0.0064983928 | 0.38980498 |
| 2 | `tray_V` | 18 | n-Pentane | 0.0064086932 | 0.0047598135 | 0.34641686 |
| 3 | `tray_V` | 17 | n-Pentane | 0.0059858415 | 0.0045872768 | 0.30487907 |
| 4 | `tray_V` | 16 | n-Pentane | 0.0056208546 | 0.0044437587 | 0.26488746 |
| 5 | `tray_V` | 15 | n-Pentane | 0.00505787 | 0.0042186553 | 0.19892942 |
| 6 | `tray_V` | 14 | n-Pentane | 0.0046600088 | 0.0039823016 | 0.17017978 |
| 7 | `tray_V` | 13 | n-Pentane | 0.0042972921 | 0.00375617 | 0.14406218 |
| 8 | `tray_V` | 12 | n-Pentane | 0.0039691404 | 0.003542786 | 0.12034438 |
| 9 | `tray_V` | 11 | n-Pentane | 0.0036762637 | 0.0033446095 | 0.099160794 |
| 10 | `tray_V` | 10 | n-Pentane | 0.0034307328 | 0.0031785897 | 0.079325468 |
| 11 | `tray_V` | 9 | n-Pentane | 0.0032213661 | 0.0030363378 | 0.060937988 |
| 12 | `tray_V` | 8 | n-Pentane | 0.0030474587 | 0.0029195954 | 0.043794856 |
| 13 | `tray_T_f` | 3 |  | 0.36095587 | 0.0028675479 | 124.87614 |
| 14 | `tray_V` | 7 | n-Pentane | 0.002906078 | 0.0028277019 | 0.027717242 |
| 15 | `tray_V` | 6 | n-Pentane | 0.0027465727 | 0.0027118933 | 0.012787893 |
| 16 | `tray_L` | 16 | n-Pentane | 0.01195388 | 0.0024794103 | 3.8212594 |
| 17 | `tray_L` | 12 | n-Pentane | 0.011951401 | 0.0024554299 | 3.8673354 |
| 18 | `tray_L` | 17 | n-Pentane | 0.011176643 | 0.0024148398 | 3.6283166 |
| 19 | `tray_L` | 19 | n-Propane | 0.039377312 | 0.0023424152 | 15.81056 |
| 20 | `tray_L` | 13 | n-Pentane | 0.010637921 | 0.0022806915 | 3.6643403 |
