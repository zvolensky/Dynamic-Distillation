# Column Initialization Residual Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_initializer_specdof_energy_trial6a_noflash_20260531.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `parity`
- Pressure model: `spec`
- Vapor flow model: `profile`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.018194851 1/s`
- Worst absolute state rate: `583.39267 per s`
- Max tray total material residual: `35.764673 lbmol/h`
- Total state inventory residual: `-24.515462 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_L` | 0.018194851 | 0.22835401 | 2 | n-Butane |
| `tray_V` | 0.010773136 | 0.11895481 | 10 | n-Pentane |
| `bottom_L` | 0.0034173846 | 0.13139817 | 21 | n-Propane |
| `tray_EL_BTU` | 0.0023052805 | 583.39267 | 2 |  |
| `top_L` | 0.0021878677 | 0.29335288 | 0 | n-Butane |
| `bottom_T_f` | 0 | 0 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |
| `tray_EV_BTU` | 0 | 0 | 1 |  |
| `tray_T_f` | 0 | 0 | 1 |  |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_L` | 2 | n-Butane | -0.15465496 | 0.018194851 | 7.4999296 |
| 2 | `tray_L` | 3 | n-Butane | -0.14138832 | 0.012547352 | 10.26838 |
| 3 | `tray_V` | 10 | n-Pentane | 0.013205965 | 0.010773136 | 0.22582361 |
| 4 | `tray_V` | 11 | n-Pentane | 0.013792108 | 0.01000998 | 0.37783566 |
| 5 | `tray_L` | 4 | n-Butane | -0.13506031 | 0.0094587176 | 13.278924 |
| 6 | `tray_V` | 18 | n-Propane | -0.089080029 | 0.009320688 | 8.5572375 |
| 7 | `tray_V` | 17 | n-Propane | -0.1012432 | 0.0089006571 | 10.374801 |
| 8 | `tray_V` | 19 | n-Pentane | 0.033448958 | 0.0088566899 | 2.7766884 |
| 9 | `tray_V` | 9 | n-Pentane | 0.0096955712 | 0.0087094476 | 0.11322458 |
| 10 | `tray_L` | 10 | n-Pentane | -0.01444338 | 0.0084610529 | 0.70704291 |
| 11 | `tray_V` | 18 | n-Pentane | 0.027539287 | 0.0083901618 | 2.2823308 |
| 12 | `tray_L` | 4 | n-Propane | 0.17536119 | 0.0082801011 | 20.178629 |
| 13 | `tray_L` | 3 | n-Propane | 0.20460041 | 0.0081052308 | 24.243009 |
| 14 | `tray_V` | 19 | n-Propane | -0.064010558 | 0.0080431797 | 6.9583648 |
| 15 | `tray_V` | 16 | n-Propane | -0.10462478 | 0.0078941406 | 12.253473 |
| 16 | `tray_V` | 4 | n-Butane | 0.06601553 | 0.0078333075 | 7.4275423 |
| 17 | `tray_L` | 5 | n-Propane | 0.13376424 | 0.0074758002 | 16.892966 |
| 18 | `tray_V` | 5 | n-Butane | 0.06840588 | 0.0074735696 | 8.1530397 |
| 19 | `tray_L` | 16 | n-Propane | 0.095275521 | 0.0072202459 | 12.195606 |
| 20 | `tray_L` | 11 | n-Pentane | -0.014582806 | 0.0072084121 | 1.0230261 |
