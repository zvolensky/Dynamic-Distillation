# Column Initialization Residual Audit

- Excel: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\model_consistent_initialization\c3c4_candidate_stage11_buffered_lower_interface\bottom-boundary-balanced.xlsx`
- Thermo: `table`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.041528818 1/s`
- Worst absolute state rate: `464.69708 per s`
- Max tray total material residual: `650.16693 lbmol/h`
- Total state inventory residual: `530.68107 lbmol/h`

## Top Boundary Diagnostics

- Total condenser boundary energy residual: `-1.8189894e-12 Btu/s`
- Total condenser boundary energy residual relative scale: `-1.7057571e-16`
- Total condenser boundary energy owner: `1`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_V` | 0.041528818 | 0.30496727 | 9 | n-Butane |
| `tray_EV_BTU` | 0.016003477 | 353.66975 | 9 |  |
| `tray_L` | 0.0043669884 | 0.11810141 | 17 | n-Pentane |
| `tray_T_f` | 0.0026977306 | 0.33957992 | 3 |  |
| `tray_EL_BTU` | 0.0018467037 | 464.69708 | 2 |  |
| `bottom_L` | 0.0011045049 | 0.27579953 | 21 | n-Propane |
| `top_L` | 0.00062240918 | 0.38724455 | 0 | n-Butane |
| `bottom_T_f` | 0.0001912135 | 0.042394 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_V` | 9 | n-Butane | 0.30496727 | 0.041528818 | 6.3435096 |
| 2 | `tray_V` | 9 | n-Propane | -0.13249796 | 0.022350891 | 4.9280841 |
| 3 | `tray_EV_BTU` | 9 |  | 353.66975 | 0.016003477 | 22098.557 |
| 4 | `tray_V` | 9 | n-Pentane | 0.0075438453 | 0.007118236 | 0.059791397 |
| 5 | `tray_L` | 17 | n-Pentane | 0.017080577 | 0.0043669884 | 2.9112945 |
| 6 | `tray_L` | 16 | n-Pentane | 0.01835308 | 0.0043103121 | 3.2579468 |
| 7 | `tray_L` | 18 | n-Pentane | 0.014846419 | 0.0042962664 | 2.455656 |
| 8 | `tray_L` | 19 | n-Pentane | 0.013007665 | 0.0042506419 | 2.0601648 |
| 9 | `tray_L` | 15 | n-Pentane | 0.015395693 | 0.0038118586 | 3.038894 |
| 10 | `tray_L` | 12 | n-Pentane | 0.017947146 | 0.003760521 | 3.7725157 |
| 11 | `tray_L` | 13 | n-Pentane | 0.016818444 | 0.0037464404 | 3.4891796 |
| 12 | `tray_L` | 14 | n-Pentane | 0.015737934 | 0.0037344928 | 3.2142091 |
| 13 | `tray_V` | 19 | n-Pentane | 0.0036089026 | 0.0027943922 | 0.29148035 |
| 14 | `tray_V` | 16 | n-Pentane | 0.0033524009 | 0.0027465581 | 0.22058256 |
| 15 | `tray_V` | 17 | n-Pentane | 0.0034148778 | 0.0027447505 | 0.24414872 |
| 16 | `tray_V` | 18 | n-Pentane | 0.0034591223 | 0.0027281861 | 0.2679202 |
| 17 | `tray_L` | 19 | n-Butane | -0.11810141 | 0.0027174362 | 42.460601 |
| 18 | `tray_T_f` | 3 |  | 0.33957992 | 0.0026977306 | 124.87614 |
| 19 | `tray_V` | 15 | n-Pentane | 0.0031406228 | 0.0026779371 | 0.17277691 |
| 20 | `tray_V` | 8 | n-Pentane | 0.0027743844 | 0.002659155 | 0.043333094 |
