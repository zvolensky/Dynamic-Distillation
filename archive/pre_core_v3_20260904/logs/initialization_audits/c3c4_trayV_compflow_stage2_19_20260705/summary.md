# Column Initialization Residual Audit

- Excel: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_initializer_trayV_compflow_stage2_19_20260705.xlsx`
- Thermo: `table`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.013062335 1/s`
- Worst absolute state rate: `2030.9648 per s`
- Max tray total material residual: `805.72221 lbmol/h`
- Total state inventory residual: `-5.9366531 lbmol/h`

## Top Boundary Diagnostics

- Total condenser boundary energy residual: `0 Btu/s`
- Total condenser boundary energy residual relative scale: `0`
- Total condenser boundary energy owner: `1`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_EV_BTU` | 0.013062335 | 1082.1177 | 2 |  |
| `tray_V` | 0.011829416 | 0.29751982 | 19 | n-Butane |
| `tray_L` | 0.011614218 | 0.19628944 | 3 | n-Butane |
| `tray_EL_BTU` | 0.0070594188 | 2030.9648 | 12 |  |
| `tray_T_f` | 0.0044720283 | 0.55438488 | 2 |  |
| `top_L` | 0.0029607997 | 0.71201014 | 0 | n-Butane |
| `bottom_L` | 0.0018821464 | 0.072368378 | 21 | n-Propane |
| `bottom_T_f` | 6.7281034e-06 | 0.0014916897 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_EV_BTU` | 2 |  | 1082.1177 | 0.013062335 | 82841.594 |
| 2 | `tray_EV_BTU` | 19 |  | 353.00022 | 0.012420173 | 28420.522 |
| 3 | `tray_V` | 19 | n-Butane | 0.1206173 | 0.011829416 | 9.1963866 |
| 4 | `tray_L` | 3 | n-Butane | -0.13306927 | 0.011614218 | 10.457445 |
| 5 | `tray_V` | 18 | n-Butane | 0.11464984 | 0.011502075 | 8.967752 |
| 6 | `tray_V` | 14 | n-Butane | 0.087616574 | 0.011279799 | 6.767565 |
| 7 | `tray_V` | 17 | n-Butane | 0.10739337 | 0.011083759 | 8.6892551 |
| 8 | `tray_V` | 15 | n-Butane | 0.08785577 | 0.010932019 | 7.0365547 |
| 9 | `tray_V` | 13 | n-Butane | 0.080802921 | 0.010797025 | 6.4838134 |
| 10 | `tray_V` | 16 | n-Butane | 0.098571554 | 0.010523693 | 8.3666313 |
| 11 | `tray_V` | 12 | n-Butane | 0.072997805 | 0.010149166 | 6.1924928 |
| 12 | `tray_V` | 2 | n-Propane | -0.29751982 | 0.0099643997 | 28.858278 |
| 13 | `tray_V` | 11 | n-Butane | 0.065647117 | 0.0094841839 | 5.9217465 |
| 14 | `tray_V` | 16 | n-Pentane | 0.014735094 | 0.0093384111 | 0.57790159 |
| 15 | `tray_V` | 17 | n-Pentane | 0.015410382 | 0.0093245517 | 0.65266733 |
| 16 | `tray_V` | 15 | n-Pentane | 0.013413701 | 0.009313296 | 0.44027433 |
| 17 | `tray_L` | 4 | n-Butane | -0.14239914 | 0.0092942137 | 14.321268 |
| 18 | `tray_V` | 14 | n-Pentane | 0.012786533 | 0.0092832925 | 0.37737051 |
| 19 | `tray_V` | 18 | n-Pentane | 0.015808139 | 0.0091907109 | 0.7200126 |
| 20 | `tray_V` | 13 | n-Pentane | 0.012011598 | 0.0091413709 | 0.31398211 |
