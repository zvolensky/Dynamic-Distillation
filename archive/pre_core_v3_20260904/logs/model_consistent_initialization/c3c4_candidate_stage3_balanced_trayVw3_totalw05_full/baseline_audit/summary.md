# Column Initialization Residual Audit

- Excel: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_model_consistent_seed_candidate_stage2.xlsx`
- Thermo: `table`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.0089353882 1/s`
- Worst absolute state rate: `753.69364 per s`
- Max tray total material residual: `444.18454 lbmol/h`
- Total state inventory residual: `16.983384 lbmol/h`

## Top Boundary Diagnostics

- Total condenser boundary energy residual: `-1.8189894e-12 Btu/s`
- Total condenser boundary energy residual relative scale: `-1.4230681e-16`
- Total condenser boundary energy owner: `1`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_V` | 0.0089353882 | 0.14280615 | 16 | n-Pentane |
| `tray_T_f` | 0.0064744183 | 0.80261558 | 2 |  |
| `bottom_L` | 0.0064105025 | 0.24648331 | 21 | n-Propane |
| `tray_L` | 0.0056924809 | 0.19704057 | 9 | n-Pentane |
| `tray_EL_BTU` | 0.0029097586 | 753.69364 | 2 |  |
| `tray_EV_BTU` | 0.0020553127 | 208.93104 | 2 |  |
| `top_L` | 0.0014869034 | 0.72981776 | 0 | n-Butane |
| `bottom_T_f` | 1.3610248e-05 | 0.0030175319 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_V` | 16 | n-Pentane | 0.01352552 | 0.0089353882 | 0.51370256 |
| 2 | `tray_V` | 17 | n-Pentane | 0.013977927 | 0.0088155771 | 0.58559412 |
| 3 | `tray_V` | 15 | n-Pentane | 0.012075808 | 0.0086990821 | 0.38817041 |
| 4 | `tray_V` | 18 | n-Pentane | 0.014327196 | 0.0086533835 | 0.65567561 |
| 5 | `tray_V` | 14 | n-Pentane | 0.011487852 | 0.0086304638 | 0.33108168 |
| 6 | `tray_V` | 13 | n-Pentane | 0.010920715 | 0.0085574198 | 0.27616913 |
| 7 | `tray_V` | 12 | n-Pentane | 0.010379435 | 0.0084824805 | 0.22363205 |
| 8 | `tray_V` | 11 | n-Pentane | 0.0098708701 | 0.008405859 | 0.17428453 |
| 9 | `tray_V` | 10 | n-Pentane | 0.0093815048 | 0.0083269054 | 0.12664962 |
| 10 | `tray_V` | 9 | n-Pentane | 0.0088178087 | 0.00815008 | 0.0819291 |
| 11 | `tray_V` | 8 | n-Pentane | 0.0079413492 | 0.0076220945 | 0.041885435 |
| 12 | `tray_T_f` | 2 |  | -0.80261558 | 0.0064744183 | 122.96721 |
| 13 | `bottom_L` | 21 | n-Propane | 0.24648331 | 0.0064105025 | 37.449921 |
| 14 | `tray_V` | 18 | n-Butane | 0.046689558 | 0.0058594702 | 6.9682217 |
| 15 | `tray_V` | 17 | n-Butane | 0.045555799 | 0.0057976272 | 6.8576628 |
| 16 | `tray_V` | 19 | n-Butane | 0.046644123 | 0.005786566 | 7.0607606 |
| 17 | `tray_V` | 16 | n-Butane | 0.04408176 | 0.0056991186 | 6.7348381 |
| 18 | `tray_L` | 9 | n-Pentane | -0.0090229534 | 0.0056924809 | 0.58506521 |
| 19 | `tray_L` | 4 | n-Butane | -0.080518265 | 0.0053506879 | 14.048208 |
| 20 | `tray_L` | 10 | n-Pentane | -0.010009474 | 0.0053159589 | 0.8829103 |
