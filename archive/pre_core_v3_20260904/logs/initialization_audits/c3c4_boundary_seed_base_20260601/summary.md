# Column Initialization Residual Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_initializer_chemsep_specs_energy_trial7_boundary_seed_20260531.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `parity`
- Pressure model: `spec`
- Vapor flow model: `profile`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.018186912 1/s`
- Worst absolute state rate: `628.0414 per s`
- Max tray total material residual: `14.839252 lbmol/h`
- Total state inventory residual: `-5.9366531 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_L` | 0.018186912 | 0.22852868 | 2 | n-Butane |
| `tray_V` | 0.010775886 | 0.12015736 | 10 | n-Pentane |
| `bottom_L` | 0.0033155561 | 0.12748287 | 21 | n-Propane |
| `tray_EL_BTU` | 0.0024708105 | 628.0414 | 2 |  |
| `top_L` | 0.0021257664 | 0.28639975 | 0 | n-Butane |
| `bottom_T_f` | 0 | 0 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |
| `tray_EV_BTU` | 0 | 0 | 1 |  |
| `tray_T_f` | 0 | 0 | 1 |  |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_L` | 2 | n-Butane | -0.15455499 | 0.018186912 | 7.4981435 |
| 2 | `tray_L` | 3 | n-Butane | -0.1414327 | 0.01255204 | 10.267706 |
| 3 | `tray_V` | 10 | n-Pentane | 0.013209288 | 0.010775886 | 0.22581921 |
| 4 | `tray_V` | 11 | n-Pentane | 0.013797203 | 0.01001343 | 0.37786987 |
| 5 | `tray_L` | 4 | n-Butane | -0.13508203 | 0.0094603582 | 13.278744 |
| 6 | `tray_V` | 18 | n-Propane | -0.090264578 | 0.0094601942 | 8.5415143 |
| 7 | `tray_V` | 19 | n-Pentane | 0.0347102 | 0.0091240213 | 2.8042655 |
| 8 | `tray_V` | 17 | n-Propane | -0.10184364 | 0.0089573384 | 10.369855 |
| 9 | `tray_V` | 9 | n-Pentane | 0.0096971039 | 0.0087109997 | 0.11320218 |
| 10 | `tray_V` | 18 | n-Pentane | 0.028180791 | 0.0085437951 | 2.2983927 |
| 11 | `tray_L` | 10 | n-Pentane | -0.014442323 | 0.0084606302 | 0.70700327 |
| 12 | `tray_L` | 4 | n-Propane | 0.17538291 | 0.0082810565 | 20.178809 |
| 13 | `tray_V` | 19 | n-Propane | -0.065157352 | 0.0082255064 | 6.9213788 |
| 14 | `tray_L` | 3 | n-Propane | 0.20464479 | 0.0081067724 | 24.243683 |
| 15 | `tray_V` | 4 | n-Butane | 0.066937083 | 0.0080013022 | 7.3657736 |
| 16 | `tray_V` | 16 | n-Propane | -0.10491068 | 0.0079156009 | 12.253659 |
| 17 | `tray_V` | 5 | n-Butane | 0.069170269 | 0.0075985426 | 8.1030968 |
| 18 | `tray_L` | 5 | n-Propane | 0.13377798 | 0.007476622 | 16.892837 |
| 19 | `tray_V` | 3 | n-Butane | 0.056946128 | 0.0074123807 | 6.6825692 |
| 20 | `tray_L` | 16 | n-Propane | 0.09599994 | 0.0073022034 | 12.146709 |
