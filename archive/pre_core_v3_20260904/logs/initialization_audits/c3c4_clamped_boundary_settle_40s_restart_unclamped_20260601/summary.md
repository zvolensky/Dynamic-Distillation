# Column Initialization Residual Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_initializer_chemsep_specs_energy_trial7_boundary_seed_20260531__restart_20260601_104246.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.070319299 1/s`
- Worst absolute state rate: `1559.5284 per s`
- Max tray total material residual: `2400.0253 lbmol/h`
- Total state inventory residual: `-5.9366531 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_EV_BTU` | 0.070319299 | 1559.5284 | 19 |  |
| `tray_V` | 0.017728333 | 0.7709227 | 2 | n-Propane |
| `tray_L` | 0.016960652 | 0.23575305 | 2 | n-Butane |
| `tray_T_f` | 0.0038750686 | 0.5214708 | 3 |  |
| `tray_EL_BTU` | 0.0038131767 | 629.0988 | 2 |  |
| `bottom_L` | 0.0035289738 | 0.14025572 | 21 | n-Propane |
| `top_L` | 0.0030387441 | 0.42765177 | 0 | n-Butane |
| `bottom_T_f` | 1.6720925e-08 | 3.707201e-06 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_EV_BTU` | 19 |  | -423.24834 | 0.070319299 | 6017.9498 |
| 2 | `tray_EV_BTU` | 18 |  | -1162.6706 | 0.051188817 | 22712.371 |
| 3 | `tray_EV_BTU` | 17 |  | -1559.5284 | 0.034242154 | 45543.108 |
| 4 | `tray_EV_BTU` | 16 |  | -1342.4792 | 0.02048386 | 65537.39 |
| 5 | `tray_V` | 2 | n-Propane | -0.7709227 | 0.017728333 | 42.485347 |
| 6 | `tray_L` | 2 | n-Butane | -0.16157354 | 0.016960652 | 8.5263757 |
| 7 | `tray_EV_BTU` | 15 |  | -852.15691 | 0.011467596 | 74308.985 |
| 8 | `tray_L` | 19 | n-Propane | 0.11470141 | 0.011270361 | 9.1772614 |
| 9 | `tray_V` | 15 | n-Propane | -0.086518124 | 0.011007911 | 6.8596313 |
| 10 | `tray_V` | 19 | n-Pentane | 0.038691138 | 0.01068201 | 2.6220841 |
| 11 | `tray_V` | 3 | n-Butane | 0.12548235 | 0.010521505 | 10.926274 |
| 12 | `tray_V` | 14 | n-Propane | -0.097650378 | 0.01051028 | 8.2909401 |
| 13 | `tray_V` | 16 | n-Propane | -0.072538037 | 0.010460357 | 5.9345664 |
| 14 | `tray_V` | 8 | n-Pentane | 0.014820908 | 0.0096827204 | 0.53065542 |
| 15 | `tray_L` | 5 | n-Butane | -0.12469932 | 0.0096282518 | 11.951398 |
| 16 | `tray_V` | 7 | n-Pentane | 0.013005576 | 0.0095427839 | 0.36287016 |
| 17 | `tray_L` | 18 | n-Propane | 0.11509515 | 0.0093138327 | 11.357442 |
| 18 | `tray_V` | 13 | n-Propane | -0.097179954 | 0.0090331123 | 9.7581916 |
| 19 | `tray_V` | 9 | n-Pentane | 0.014580939 | 0.0084850886 | 0.71841921 |
| 20 | `tray_L` | 6 | n-Butane | -0.12853948 | 0.0083046184 | 14.478072 |
