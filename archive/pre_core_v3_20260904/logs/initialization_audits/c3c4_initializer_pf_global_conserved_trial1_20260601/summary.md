# Column Initialization Residual Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_initializer_pf_global_conserved_trial1_20260601.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.022529854 1/s`
- Worst absolute state rate: `2878.0362 per s`
- Max tray total material residual: `2570.1087 lbmol/h`
- Total state inventory residual: `-5.9366531 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_V` | 0.022529854 | 0.76378767 | 2 | n-Propane |
| `tray_L` | 0.015757726 | 0.22958264 | 2 | n-Butane |
| `tray_EL_BTU` | 0.012447564 | 2878.0362 | 2 |  |
| `tray_EV_BTU` | 0.0045956224 | 130.61458 | 19 |  |
| `bottom_L` | 0.0039088478 | 0.15029489 | 21 | n-Propane |
| `tray_T_f` | 0.0034845371 | 0.44503114 | 2 |  |
| `top_L` | 0.0020330866 | 0.26838789 | 0 | n-Butane |
| `top_V` | 0.00040400627 | 0.025386135 | 0 | n-Propane |
| `bottom_T_f` | 9.8399397e-06 | 0.0021816158 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_V` | 2 | n-Propane | -0.76378767 | 0.022529854 | 32.901138 |
| 2 | `tray_V` | 17 | n-Propane | -0.090465196 | 0.020530994 | 3.4062746 |
| 3 | `tray_V` | 18 | n-Propane | -0.077018991 | 0.020069151 | 2.8376806 |
| 4 | `tray_V` | 16 | n-Propane | -0.099311023 | 0.019698379 | 4.0415835 |
| 5 | `tray_V` | 14 | n-Butane | 0.11909146 | 0.016267628 | 6.3207632 |
| 6 | `tray_V` | 19 | n-Propane | -0.054716888 | 0.016245723 | 2.3680795 |
| 7 | `tray_V` | 12 | n-Butane | 0.1042886 | 0.015799897 | 5.6005876 |
| 8 | `tray_V` | 13 | n-Butane | 0.10945143 | 0.015771592 | 5.9397835 |
| 9 | `tray_L` | 2 | n-Butane | -0.12125751 | 0.015757726 | 6.695115 |
| 10 | `tray_V` | 15 | n-Butane | 0.12144344 | 0.01573004 | 6.7204791 |
| 11 | `tray_V` | 6 | n-Butane | 0.07563459 | 0.01532045 | 3.9368388 |
| 12 | `tray_V` | 5 | n-Butane | 0.070328638 | 0.015140406 | 3.645096 |
| 13 | `tray_L` | 3 | n-Butane | -0.16636936 | 0.015018099 | 10.077924 |
| 14 | `tray_V` | 7 | n-Butane | 0.076784421 | 0.014663081 | 4.2365815 |
| 15 | `tray_V` | 18 | n-Pentane | 0.025408559 | 0.014363482 | 0.76896926 |
| 16 | `tray_V` | 4 | n-Butane | 0.060532664 | 0.013798745 | 3.3868238 |
| 17 | `tray_V` | 8 | n-Butane | 0.074766957 | 0.013512658 | 4.5331049 |
| 18 | `tray_V` | 19 | n-Pentane | 0.025716969 | 0.013496923 | 0.90539494 |
| 19 | `tray_V` | 15 | n-Propane | -0.067215784 | 0.013428967 | 4.0052832 |
| 20 | `tray_V` | 17 | n-Pentane | 0.021876461 | 0.013245611 | 0.65160078 |
