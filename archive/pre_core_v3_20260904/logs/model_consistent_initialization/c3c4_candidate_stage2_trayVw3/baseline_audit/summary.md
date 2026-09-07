# Column Initialization Residual Audit

- Excel: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_model_consistent_seed_candidate.xlsx`
- Thermo: `table`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.010894017 1/s`
- Worst absolute state rate: `970.56701 per s`
- Max tray total material residual: `337.75516 lbmol/h`
- Total state inventory residual: `16.983384 lbmol/h`

## Top Boundary Diagnostics

- Total condenser boundary energy residual: `-1.8189894e-12 Btu/s`
- Total condenser boundary energy residual relative scale: `-1.3814807e-16`
- Total condenser boundary energy owner: `1`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_V` | 0.010894017 | 0.2896607 | 15 | n-Butane |
| `tray_L` | 0.006894511 | 0.21135545 | 4 | n-Butane |
| `tray_T_f` | 0.0057332024 | 0.71072911 | 2 |  |
| `bottom_L` | 0.0036690467 | 0.14107456 | 21 | n-Propane |
| `tray_EL_BTU` | 0.003602885 | 970.56701 | 2 |  |
| `tray_EV_BTU` | 0.0024851093 | 156.4746 | 19 |  |
| `top_L` | 0.0013290266 | 0.4934833 | 0 | n-Butane |
| `bottom_T_f` | 1.3610248e-05 | 0.0030175319 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_V` | 15 | n-Butane | 0.079329596 | 0.010894017 | 6.2819417 |
| 2 | `tray_V` | 14 | n-Butane | 0.075782551 | 0.010798498 | 6.0178788 |
| 3 | `tray_V` | 16 | n-Butane | 0.091382791 | 0.010751867 | 7.4992486 |
| 4 | `tray_V` | 17 | n-Butane | 0.093484427 | 0.010596503 | 7.8221963 |
| 5 | `tray_V` | 10 | n-Pentane | 0.011901452 | 0.010581596 | 0.12473134 |
| 6 | `tray_V` | 13 | n-Butane | 0.070999804 | 0.010526579 | 5.7448126 |
| 7 | `tray_V` | 11 | n-Pentane | 0.012486965 | 0.010474742 | 0.19210247 |
| 8 | `tray_V` | 16 | n-Pentane | 0.01673413 | 0.010326152 | 0.62055822 |
| 9 | `tray_V` | 18 | n-Butane | 0.093782177 | 0.010316247 | 8.0907263 |
| 10 | `tray_V` | 17 | n-Pentane | 0.017416194 | 0.010205999 | 0.70646643 |
| 11 | `tray_V` | 15 | n-Pentane | 0.014906606 | 0.010142818 | 0.4696711 |
| 12 | `tray_V` | 12 | n-Pentane | 0.012755276 | 0.010114926 | 0.26103493 |
| 13 | `tray_V` | 12 | n-Butane | 0.065350652 | 0.010098479 | 5.4713363 |
| 14 | `tray_V` | 14 | n-Pentane | 0.013954157 | 0.0099680661 | 0.39988605 |
| 15 | `tray_V` | 13 | n-Pentane | 0.013214034 | 0.0099313132 | 0.33054245 |
| 16 | `tray_V` | 18 | n-Pentane | 0.017446963 | 0.0097667279 | 0.78636727 |
| 17 | `tray_V` | 9 | n-Pentane | 0.010296089 | 0.0096552658 | 0.066370346 |
| 18 | `tray_V` | 11 | n-Butane | 0.059583514 | 0.0095747154 | 5.2230062 |
| 19 | `tray_V` | 2 | n-Propane | -0.2896607 | 0.0091819037 | 30.546911 |
| 20 | `tray_V` | 10 | n-Butane | 0.054472452 | 0.0091344769 | 4.9633905 |
