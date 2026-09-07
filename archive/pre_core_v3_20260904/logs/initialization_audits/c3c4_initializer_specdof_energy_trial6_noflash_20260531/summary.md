# Column Initialization Residual Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_initializer_specdof_energy_trial6_noflash_20260531.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `parity`
- Pressure model: `spec`
- Vapor flow model: `profile`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.018197287 1/s`
- Worst absolute state rate: `563.59393 per s`
- Max tray total material residual: `34.373905 lbmol/h`
- Total state inventory residual: `-24.808271 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_L` | 0.018197287 | 0.22826725 | 2 | n-Butane |
| `tray_V` | 0.010771288 | 0.11849442 | 10 | n-Pentane |
| `bottom_L` | 0.00345424 | 0.13281525 | 21 | n-Propane |
| `tray_EL_BTU` | 0.0022314023 | 563.59393 | 2 |  |
| `top_L` | 0.0022118635 | 0.29641363 | 0 | n-Butane |
| `bottom_T_f` | 0 | 0 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |
| `tray_EV_BTU` | 0 | 0 | 1 |  |
| `tray_T_f` | 0 | 0 | 1 |  |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_L` | 2 | n-Butane | -0.15468335 | 0.018197287 | 7.5003524 |
| 2 | `tray_L` | 3 | n-Butane | -0.14137931 | 0.012546336 | 10.268573 |
| 3 | `tray_V` | 10 | n-Pentane | 0.013203679 | 0.010771288 | 0.2258218 |
| 4 | `tray_V` | 11 | n-Pentane | 0.013787451 | 0.010006806 | 0.37780734 |
| 5 | `tray_L` | 4 | n-Butane | -0.13505387 | 0.0094582353 | 13.278971 |
| 6 | `tray_V` | 18 | n-Propane | -0.08840497 | 0.0092361186 | 8.5716582 |
| 7 | `tray_V` | 17 | n-Propane | -0.10083893 | 0.008859536 | 10.381965 |
| 8 | `tray_V` | 9 | n-Pentane | 0.0096947171 | 0.0087086162 | 0.11323279 |
| 9 | `tray_V` | 19 | n-Pentane | 0.032722142 | 0.0087027196 | 2.7599904 |
| 10 | `tray_L` | 10 | n-Pentane | -0.014443011 | 0.0084608442 | 0.70704141 |
| 11 | `tray_V` | 18 | n-Pentane | 0.027128852 | 0.0082886804 | 2.2730001 |
| 12 | `tray_L` | 4 | n-Propane | 0.17535474 | 0.0082798151 | 20.178582 |
| 13 | `tray_L` | 3 | n-Propane | 0.2045914 | 0.0081049357 | 24.242815 |
| 14 | `tray_V` | 19 | n-Propane | -0.062968906 | 0.0078859952 | 6.9849029 |
| 15 | `tray_V` | 16 | n-Propane | -0.10439097 | 0.0078747358 | 12.25644 |
| 16 | `tray_V` | 4 | n-Butane | 0.065644598 | 0.0077662424 | 7.4525558 |
| 17 | `tray_L` | 5 | n-Propane | 0.13375854 | 0.0074754478 | 16.893047 |
| 18 | `tray_V` | 5 | n-Butane | 0.068092059 | 0.0074228597 | 8.1732919 |
| 19 | `tray_L` | 11 | n-Pentane | -0.014579092 | 0.0072068663 | 1.0229447 |
| 20 | `tray_L` | 2 | n-Propane | 0.22826725 | 0.0072028686 | 30.691158 |
