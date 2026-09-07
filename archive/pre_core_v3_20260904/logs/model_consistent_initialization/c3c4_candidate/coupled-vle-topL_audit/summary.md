# Column Initialization Residual Audit

- Excel: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\model_consistent_initialization\c3c4_candidate\coupled-vle-topL.xlsx`
- Thermo: `table`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.010904362 1/s`
- Worst absolute state rate: `1344.6597 per s`
- Max tray total material residual: `730.71531 lbmol/h`
- Total state inventory residual: `-5.9366531 lbmol/h`

## Top Boundary Diagnostics

- Total condenser boundary energy residual: `0 Btu/s`
- Total condenser boundary energy residual relative scale: `0`
- Total condenser boundary energy owner: `1`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_V` | 0.010904362 | 0.29030218 | 15 | n-Butane |
| `tray_L` | 0.00737909 | 0.15094443 | 4 | n-Butane |
| `tray_EL_BTU` | 0.0051063205 | 1344.6597 | 2 |  |
| `tray_T_f` | 0.0036030439 | 0.4466593 | 2 |  |
| `bottom_L` | 0.0035509451 | 0.13653356 | 21 | n-Propane |
| `tray_EV_BTU` | 0.0025099609 | 182.12521 | 19 |  |
| `top_L` | 0.0011697694 | 0.49876209 | 0 | n-Butane |
| `bottom_T_f` | 6.7281034e-06 | 0.0014916897 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_V` | 15 | n-Butane | 0.079411744 | 0.010904362 | 6.2825671 |
| 2 | `tray_V` | 14 | n-Butane | 0.075852296 | 0.010807358 | 6.0185788 |
| 3 | `tray_V` | 16 | n-Butane | 0.091437306 | 0.010757531 | 7.4998411 |
| 4 | `tray_V` | 17 | n-Butane | 0.09356042 | 0.010604663 | 7.8225736 |
| 5 | `tray_V` | 10 | n-Pentane | 0.01190071 | 0.010580852 | 0.12474026 |
| 6 | `tray_V` | 13 | n-Butane | 0.071058823 | 0.010534178 | 5.7455501 |
| 7 | `tray_V` | 11 | n-Pentane | 0.012487142 | 0.010474682 | 0.19212611 |
| 8 | `tray_V` | 16 | n-Pentane | 0.016740632 | 0.010329764 | 0.62062086 |
| 9 | `tray_V` | 18 | n-Butane | 0.093883987 | 0.010327248 | 8.0909007 |
| 10 | `tray_V` | 17 | n-Pentane | 0.017424088 | 0.010210304 | 0.70652005 |
| 11 | `tray_V` | 15 | n-Pentane | 0.014913315 | 0.010146973 | 0.46973041 |
| 12 | `tray_V` | 12 | n-Pentane | 0.012758058 | 0.01011682 | 0.26107385 |
| 13 | `tray_V` | 12 | n-Butane | 0.065424938 | 0.010108801 | 5.472077 |
| 14 | `tray_V` | 14 | n-Pentane | 0.01395924 | 0.0099712944 | 0.39994261 |
| 15 | `tray_V` | 13 | n-Pentane | 0.013217453 | 0.0099335185 | 0.33059124 |
| 16 | `tray_V` | 18 | n-Pentane | 0.017456093 | 0.0097716572 | 0.78640047 |
| 17 | `tray_V` | 9 | n-Pentane | 0.01029395 | 0.0096532752 | 0.066368603 |
| 18 | `tray_V` | 11 | n-Butane | 0.059621081 | 0.0095796772 | 5.2237046 |
| 19 | `tray_V` | 2 | n-Propane | -0.29030218 | 0.0092022379 | 30.546911 |
| 20 | `tray_V` | 10 | n-Butane | 0.054515709 | 0.0091407449 | 4.9640335 |
