# Column Initialization Residual Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_iterative_coupled_closure_continue_20260531\c3c4_coupled_cont_iter02_blend0.0312.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `parity`
- Pressure model: `spec`
- Vapor flow model: `profile`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.02870149 1/s`
- Worst absolute state rate: `0.19608962 per s`
- Max tray total material residual: `0.09 lbmol/h`
- Total state inventory residual: `0.004 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_L` | 0.02870149 | 0.19608962 | 2 | n-Pentane |
| `tray_V` | 0.016988459 | 0.18631245 | 19 | n-Propane |
| `bottom_L` | 0.00046354089 | 0.048332109 | 21 | n-Pentane |
| `top_L` | 5.3135008e-11 | 1.388598e-08 | 0 | n-Pentane |
| `bottom_T_f` | 0 | 0 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |
| `tray_T_f` | 0 | 0 | 1 |  |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_L` | 2 | n-Pentane | 0.030871452 | 0.02870149 | 0.075604515 |
| 2 | `tray_V` | 19 | n-Propane | 0.11021341 | 0.016988459 | 5.4875458 |
| 3 | `tray_V` | 19 | n-Pentane | 0.057190384 | 0.01538099 | 2.7182511 |
| 4 | `tray_L` | 2 | n-Butane | 0.11880075 | 0.014163057 | 7.3880724 |
| 5 | `tray_V` | 3 | n-Butane | 0.12426005 | 0.01282159 | 8.6914695 |
| 6 | `tray_V` | 11 | n-Pentane | 0.022925871 | 0.012685152 | 0.80729973 |
| 7 | `tray_V` | 2 | n-Butane | 0.11117424 | 0.012588189 | 7.8316307 |
| 8 | `tray_L` | 3 | n-Butane | -0.13340834 | 0.012134213 | 9.994396 |
| 9 | `tray_V` | 18 | n-Propane | -0.098351514 | 0.011910022 | 7.2578784 |
| 10 | `tray_L` | 11 | n-Pentane | -0.023291022 | 0.010906303 | 1.1355561 |
| 11 | `tray_L` | 12 | n-Pentane | 0.04616159 | 0.010548318 | 3.376204 |
| 12 | `tray_V` | 4 | n-Butane | 0.11439945 | 0.010214484 | 10.199728 |
| 13 | `tray_V` | 17 | n-Propane | -0.099646399 | 0.0099135789 | 9.0515062 |
| 14 | `tray_V` | 3 | n-Propane | -0.18577483 | 0.0095996524 | 18.352245 |
| 15 | `tray_V` | 4 | n-Propane | -0.15337222 | 0.0090104594 | 16.021576 |
| 16 | `tray_L` | 4 | n-Butane | -0.12017468 | 0.0087855293 | 12.678707 |
| 17 | `tray_V` | 16 | n-Propane | -0.095780942 | 0.0081338685 | 10.775571 |
| 18 | `tray_V` | 2 | n-Propane | -0.18631245 | 0.0080674645 | 22.0943 |
| 19 | `tray_L` | 19 | n-Pentane | -0.052601 | 0.0079198819 | 5.6416395 |
| 20 | `tray_L` | 10 | n-Pentane | -0.012802661 | 0.0078520431 | 0.63048786 |
