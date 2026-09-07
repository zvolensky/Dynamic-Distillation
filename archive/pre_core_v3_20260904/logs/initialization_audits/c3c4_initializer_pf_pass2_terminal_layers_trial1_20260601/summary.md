# Column Initialization Residual Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_initializer_pf_pass2_terminal_layers_trial1_20260601.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.040774972 1/s`
- Worst absolute state rate: `2204.9631 per s`
- Max tray total material residual: `2571.1641 lbmol/h`
- Total state inventory residual: `-5.9366531 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_V` | 0.040774972 | 0.73553093 | 17 | n-Propane |
| `tray_L` | 0.0170749 | 0.24390206 | 2 | n-Butane |
| `tray_EL_BTU` | 0.010205476 | 2204.9631 | 2 |  |
| `tray_T_f` | 0.004786237 | 0.61127905 | 2 |  |
| `bottom_L` | 0.0042353996 | 0.16285078 | 21 | n-Propane |
| `tray_EV_BTU` | 0.0035929959 | 102.11841 | 19 |  |
| `top_L` | 0.002209361 | 0.2916579 | 0 | n-Butane |
| `top_V` | 0.00031140242 | 0.019310202 | 0 | n-Propane |
| `bottom_T_f` | 1.019336e-05 | 0.0022599729 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_V` | 17 | n-Propane | -0.17877937 | 0.040774972 | 3.3845369 |
| 2 | `tray_V` | 17 | n-Pentane | 0.044610835 | 0.027411491 | 0.62745013 |
| 3 | `tray_V` | 2 | n-Propane | -0.73553093 | 0.021981155 | 32.461887 |
| 4 | `tray_V` | 16 | n-Propane | -0.10451972 | 0.020695345 | 4.0503977 |
| 5 | `tray_V` | 4 | n-Butane | 0.082561652 | 0.019625748 | 3.2068029 |
| 6 | `tray_V` | 5 | n-Butane | 0.086194353 | 0.018791916 | 3.5867783 |
| 7 | `tray_V` | 15 | n-Butane | 0.13886342 | 0.018199751 | 6.629963 |
| 8 | `tray_V` | 14 | n-Butane | 0.13007023 | 0.018147488 | 6.167396 |
| 9 | `tray_V` | 13 | n-Butane | 0.11729309 | 0.017403472 | 5.7396373 |
| 10 | `tray_V` | 6 | n-Butane | 0.085277076 | 0.017174423 | 3.9653532 |
| 11 | `tray_V` | 12 | n-Butane | 0.10902346 | 0.017131644 | 5.3638647 |
| 12 | `tray_L` | 2 | n-Butane | -0.13848918 | 0.0170749 | 7.1106876 |
| 13 | `tray_V` | 15 | n-Propane | -0.08343315 | 0.016359904 | 4.0998559 |
| 14 | `tray_V` | 17 | n-Butane | 0.15853954 | 0.016312532 | 8.7188799 |
| 15 | `tray_V` | 7 | n-Butane | 0.079043643 | 0.014868372 | 4.3162273 |
| 16 | `tray_L` | 4 | n-Butane | -0.20359406 | 0.014258541 | 13.278744 |
| 17 | `tray_V` | 14 | n-Propane | -0.073204562 | 0.01296933 | 4.6444364 |
| 18 | `tray_V` | 11 | n-Pentane | 0.014930966 | 0.012699188 | 0.17574178 |
| 19 | `tray_V` | 10 | n-Pentane | 0.013740353 | 0.012444668 | 0.10411567 |
| 20 | `tray_V` | 8 | n-Butane | 0.069736371 | 0.01240267 | 4.6226901 |
