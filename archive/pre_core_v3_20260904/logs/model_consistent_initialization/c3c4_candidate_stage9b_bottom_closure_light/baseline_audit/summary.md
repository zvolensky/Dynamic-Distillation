# Column Initialization Residual Audit

- Excel: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_model_consistent_seed_candidate_stage8_bottom_state_balanced.xlsx`
- Thermo: `table`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.0041777544 1/s`
- Worst absolute state rate: `465.85276 per s`
- Max tray total material residual: `193.24498 lbmol/h`
- Total state inventory residual: `-306.78803 lbmol/h`

## Top Boundary Diagnostics

- Total condenser boundary energy residual: `0 Btu/s`
- Total condenser boundary energy residual relative scale: `0`
- Total condenser boundary energy owner: `1`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `bottom_L` | 0.0041777544 | 0.37255056 | 21 | n-Propane |
| `tray_V` | 0.0030626408 | 0.0051203077 | 18 | n-Pentane |
| `tray_L` | 0.0027930517 | 0.057719385 | 16 | n-Pentane |
| `tray_T_f` | 0.0026986457 | 0.33969511 | 3 |  |
| `tray_EL_BTU` | 0.0018512964 | 465.85276 | 2 |  |
| `top_L` | 0.00062441863 | 0.3879406 | 0 | n-Butane |
| `tray_EV_BTU` | 0.00059905105 | 43.33499 | 16 |  |
| `bottom_T_f` | 2.3381781e-05 | 0.0051839814 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `bottom_L` | 21 | n-Propane | 0.37255056 | 0.0041777544 | 88.174833 |
| 2 | `tray_V` | 18 | n-Pentane | 0.0039571517 | 0.0030626408 | 0.29207174 |
| 3 | `tray_V` | 17 | n-Pentane | 0.0038517467 | 0.0030543797 | 0.26105694 |
| 4 | `tray_V` | 16 | n-Pentane | 0.003745403 | 0.0030430075 | 0.2308228 |
| 5 | `tray_V` | 19 | n-Pentane | 0.0040191795 | 0.003036668 | 0.32354921 |
| 6 | `tray_V` | 15 | n-Pentane | 0.0034916287 | 0.0029676454 | 0.17656533 |
| 7 | `tray_V` | 14 | n-Pentane | 0.0033293403 | 0.0028853311 | 0.15388503 |
| 8 | `tray_V` | 13 | n-Pentane | 0.0031842504 | 0.0028111656 | 0.13271537 |
| 9 | `tray_L` | 16 | n-Pentane | 0.012633589 | 0.0027930517 | 3.5232205 |
| 10 | `tray_L` | 17 | n-Pentane | 0.011886722 | 0.002764889 | 3.2991678 |
| 11 | `tray_V` | 12 | n-Pentane | 0.0030562946 | 0.002746266 | 0.11289097 |
| 12 | `tray_T_f` | 3 |  | 0.33969511 | 0.0026986457 | 124.87614 |
| 13 | `tray_V` | 11 | n-Pentane | 0.0029472679 | 0.0026925107 | 0.094617002 |
| 14 | `tray_V` | 10 | n-Pentane | 0.0028669374 | 0.0026623118 | 0.076860123 |
| 15 | `tray_V` | 9 | n-Pentane | 0.0028061228 | 0.0026478067 | 0.059791397 |
| 16 | `tray_V` | 8 | n-Pentane | 0.00275857 | 0.0026439974 | 0.043333094 |
| 17 | `tray_V` | 7 | n-Pentane | 0.0027097133 | 0.0026371864 | 0.027501635 |
| 18 | `tray_L` | 18 | n-Pentane | 0.010392563 | 0.0026323726 | 2.9479832 |
| 19 | `tray_V` | 6 | n-Pentane | 0.0025943252 | 0.0025618745 | 0.012666763 |
| 20 | `tray_L` | 12 | n-Pentane | 0.012060059 | 0.0025428249 | 3.7427801 |
