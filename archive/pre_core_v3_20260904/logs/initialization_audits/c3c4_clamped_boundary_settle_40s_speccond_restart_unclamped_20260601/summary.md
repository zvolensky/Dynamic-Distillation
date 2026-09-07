# Column Initialization Residual Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_initializer_chemsep_specs_energy_trial7_boundary_seed_20260531__restart_20260601_104755.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.070246049 1/s`
- Worst absolute state rate: `7149.2682 per s`
- Max tray total material residual: `2273.1193 lbmol/h`
- Total state inventory residual: `-5.9366531 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_EV_BTU` | 0.070246049 | 1558.3932 | 19 |  |
| `tray_EL_BTU` | 0.02505321 | 7149.2682 | 1 |  |
| `tray_V` | 0.017074015 | 0.74457769 | 2 | n-Propane |
| `tray_L` | 0.016894678 | 0.23519608 | 2 | n-Butane |
| `tray_T_f` | 0.0036421293 | 0.49298533 | 3 |  |
| `bottom_L` | 0.0035289738 | 0.14025572 | 21 | n-Propane |
| `top_L` | 0.0028836355 | 0.40725007 | 0 | n-Butane |
| `bottom_T_f` | 1.6720925e-08 | 3.707201e-06 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_EV_BTU` | 19 |  | -423.39361 | 0.070246049 | 6026.2943 |
| 2 | `tray_EV_BTU` | 18 |  | -1162.4512 | 0.051128134 | 22735.037 |
| 3 | `tray_EV_BTU` | 17 |  | -1558.3932 | 0.034194683 | 45573.139 |
| 4 | `tray_EL_BTU` | 1 |  | -7149.2682 | 0.02505321 | -285362.36 |
| 5 | `tray_EV_BTU` | 16 |  | -1340.7546 | 0.020449557 | 65562.99 |
| 6 | `tray_V` | 2 | n-Propane | -0.74457769 | 0.017074015 | 42.608823 |
| 7 | `tray_L` | 2 | n-Butane | -0.16101565 | 0.016894678 | 8.5305545 |
| 8 | `tray_EV_BTU` | 15 |  | -850.52496 | 0.01144279 | 74327.462 |
| 9 | `tray_L` | 19 | n-Propane | 0.11470141 | 0.011270361 | 9.1772614 |
| 10 | `tray_V` | 15 | n-Propane | -0.086305085 | 0.010967656 | 6.8690548 |
| 11 | `tray_V` | 19 | n-Pentane | 0.038773825 | 0.010696454 | 2.6249231 |
| 12 | `tray_V` | 3 | n-Butane | 0.12737134 | 0.010672567 | 10.934461 |
| 13 | `tray_V` | 14 | n-Propane | -0.097365788 | 0.010466919 | 8.3022392 |
| 14 | `tray_V` | 16 | n-Propane | -0.072385675 | 0.010426972 | 5.9421569 |
| 15 | `tray_V` | 8 | n-Pentane | 0.01484076 | 0.0096938918 | 0.53093931 |
| 16 | `tray_L` | 5 | n-Butane | -0.12467469 | 0.0096261801 | 11.951626 |
| 17 | `tray_V` | 7 | n-Pentane | 0.013015827 | 0.0095493871 | 0.36300126 |
| 18 | `tray_L` | 18 | n-Propane | 0.11509515 | 0.0093138327 | 11.357442 |
| 19 | `tray_V` | 13 | n-Propane | -0.096824214 | 0.0089891917 | 9.7711813 |
| 20 | `tray_V` | 9 | n-Pentane | 0.014610685 | 0.0084998901 | 0.71892631 |
