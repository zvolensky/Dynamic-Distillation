# Column Initialization Residual Audit

- Excel: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\model_consistent_initialization\c3c4_candidate_stage13_bottom_vapor_interface\bottom-boundary-balanced.xlsx`
- Thermo: `table`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.0070890197 1/s`
- Worst absolute state rate: `484.50911 per s`
- Max tray total material residual: `98.713218 lbmol/h`
- Total state inventory residual: `473.62149 lbmol/h`

## Top Boundary Diagnostics

- Total condenser boundary energy residual: `0 Btu/s`
- Total condenser boundary energy residual relative scale: `0`
- Total condenser boundary energy owner: `1`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_V` | 0.0070890197 | 0.018780856 | 19 | n-Pentane |
| `tray_T_f` | 0.0028672435 | 0.36091754 | 3 |  |
| `tray_L` | 0.0025275878 | 0.081729696 | 16 | n-Pentane |
| `tray_EL_BTU` | 0.0018930033 | 484.50911 | 2 |  |
| `bottom_L` | 0.0011021341 | 0.30009225 | 21 | n-Propane |
| `top_L` | 0.00087657409 | 0.55667327 | 0 | n-Butane |
| `tray_EV_BTU` | 0.00049171349 | 24.909252 | 19 |  |
| `bottom_T_f` | 0.0001939531 | 0.043001397 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_V` | 19 | n-Pentane | 0.0098481323 | 0.0070890197 | 0.38920932 |
| 2 | `tray_V` | 18 | n-Pentane | 0.0064582988 | 0.0047975227 | 0.34617369 |
| 3 | `tray_V` | 17 | n-Pentane | 0.006145209 | 0.0047122637 | 0.30408853 |
| 4 | `tray_V` | 16 | n-Pentane | 0.0057176349 | 0.004523806 | 0.26389922 |
| 5 | `tray_V` | 15 | n-Pentane | 0.005111655 | 0.0042667569 | 0.19801882 |
| 6 | `tray_V` | 14 | n-Pentane | 0.0046944032 | 0.0040148103 | 0.16927147 |
| 7 | `tray_V` | 13 | n-Pentane | 0.0043161703 | 0.0037754743 | 0.14321275 |
| 8 | `tray_V` | 12 | n-Pentane | 0.0039765641 | 0.0035518063 | 0.11958924 |
| 9 | `tray_V` | 11 | n-Pentane | 0.0036759143 | 0.0033462513 | 0.098517102 |
| 10 | `tray_V` | 10 | n-Pentane | 0.003424932 | 0.0031747404 | 0.078806944 |
| 11 | `tray_V` | 9 | n-Pentane | 0.0032129453 | 0.0030295274 | 0.060543424 |
| 12 | `tray_V` | 8 | n-Pentane | 0.0030383323 | 0.0029116312 | 0.043515525 |
| 13 | `tray_T_f` | 3 |  | 0.36091754 | 0.0028672435 | 124.87614 |
| 14 | `tray_V` | 7 | n-Pentane | 0.0028971187 | 0.0028194647 | 0.027542126 |
| 15 | `tray_V` | 6 | n-Pentane | 0.002737488 | 0.0027031348 | 0.012708659 |
| 16 | `tray_L` | 16 | n-Pentane | 0.012191985 | 0.0025275878 | 3.8235652 |
| 17 | `tray_L` | 19 | n-Propane | 0.041598385 | 0.0025144629 | 15.543646 |
| 18 | `tray_L` | 12 | n-Pentane | 0.012227788 | 0.0025082587 | 3.8750107 |
| 19 | `tray_L` | 17 | n-Pentane | 0.011386673 | 0.0024606025 | 3.6275956 |
| 20 | `tray_L` | 18 | n-Propane | 0.043080397 | 0.0023864498 | 17.052086 |
