# Column Initialization Residual Audit

- Excel: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_model_consistent_seed_candidate_stage3_balanced_full.xlsx`
- Thermo: `table`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.0079402468 1/s`
- Worst absolute state rate: `588.0655 per s`
- Max tray total material residual: `438.06123 lbmol/h`
- Total state inventory residual: `182.2465 lbmol/h`

## Top Boundary Diagnostics

- Total condenser boundary energy residual: `1.8189894e-12 Btu/s`
- Total condenser boundary energy residual relative scale: `1.300109e-16`
- Total condenser boundary energy owner: `1`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `bottom_L` | 0.0079402468 | 0.30530186 | 21 | n-Propane |
| `tray_V` | 0.00630182 | 0.040461109 | 9 | n-Pentane |
| `tray_T_f` | 0.0060617768 | 0.75146156 | 2 |  |
| `tray_L` | 0.0052287664 | 0.13384898 | 19 | n-Propane |
| `tray_EL_BTU` | 0.0023231263 | 588.0655 | 2 |  |
| `top_L` | 0.0021681072 | 0.71236896 | 0 | n-Butane |
| `tray_EV_BTU` | 0.00088803472 | 89.449727 | 19 |  |
| `bottom_T_f` | 1.9172848e-05 | 0.0042508175 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `bottom_L` | 21 | n-Propane | 0.30530186 | 0.0079402468 | 37.449921 |
| 2 | `tray_V` | 9 | n-Pentane | 0.0068082344 | 0.00630182 | 0.080360024 |
| 3 | `tray_V` | 10 | n-Pentane | 0.0069521551 | 0.0062512665 | 0.11211944 |
| 4 | `tray_V` | 8 | n-Pentane | 0.0065403211 | 0.0062282405 | 0.050107351 |
| 5 | `tray_V` | 11 | n-Pentane | 0.0070625436 | 0.0061695213 | 0.14474741 |
| 6 | `tray_V` | 12 | n-Pentane | 0.0071747961 | 0.0060930433 | 0.17753899 |
| 7 | `tray_T_f` | 2 |  | -0.75146156 | 0.0060617768 | 122.96721 |
| 8 | `tray_V` | 13 | n-Pentane | 0.0072839701 | 0.0060113263 | 0.21170766 |
| 9 | `tray_V` | 14 | n-Pentane | 0.0073841204 | 0.0059234214 | 0.24659717 |
| 10 | `tray_V` | 15 | n-Pentane | 0.0074734502 | 0.0058291289 | 0.28208697 |
| 11 | `tray_V` | 16 | n-Pentane | 0.0079216259 | 0.0058018749 | 0.3653562 |
| 12 | `tray_V` | 7 | n-Pentane | 0.0057694445 | 0.0056358193 | 0.023709994 |
| 13 | `tray_V` | 17 | n-Pentane | 0.0078629576 | 0.0055833522 | 0.40828616 |
| 14 | `tray_V` | 18 | n-Pentane | 0.007735505 | 0.0053354761 | 0.4498247 |
| 15 | `tray_L` | 19 | n-Propane | -0.12196648 | 0.0052287664 | 22.326053 |
| 16 | `tray_L` | 9 | n-Pentane | -0.0080769263 | 0.005118155 | 0.57809333 |
| 17 | `tray_L` | 19 | n-Pentane | 0.021918325 | 0.0050899072 | 3.3062327 |
| 18 | `tray_L` | 10 | n-Pentane | -0.008164512 | 0.0044689148 | 0.82695631 |
| 19 | `tray_L` | 8 | n-Pentane | -0.0054743019 | 0.0041248862 | 0.3271401 |
| 20 | `tray_L` | 4 | n-Propane | 0.11662176 | 0.0039873032 | 28.248279 |
