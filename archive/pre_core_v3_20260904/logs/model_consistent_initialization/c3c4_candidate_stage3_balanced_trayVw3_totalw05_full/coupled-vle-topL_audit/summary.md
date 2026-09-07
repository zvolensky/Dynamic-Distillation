# Column Initialization Residual Audit

- Excel: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\model_consistent_initialization\c3c4_candidate_stage3_balanced_trayVw3_totalw05_full\coupled-vle-topL.xlsx`
- Thermo: `table`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.0079242276 1/s`
- Worst absolute state rate: `515.45835 per s`
- Max tray total material residual: `649.69241 lbmol/h`
- Total state inventory residual: `16.983384 lbmol/h`

## Top Boundary Diagnostics

- Total condenser boundary energy residual: `-1.8189894e-12 Btu/s`
- Total condenser boundary energy residual relative scale: `-1.2996357e-16`
- Total condenser boundary energy owner: `1`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `bottom_L` | 0.0079242276 | 0.30468592 | 21 | n-Propane |
| `tray_T_f` | 0.0073441175 | 0.91042976 | 2 |  |
| `tray_V` | 0.0063118153 | 0.039273195 | 9 | n-Pentane |
| `tray_L` | 0.0056186472 | 0.18559054 | 19 | n-Pentane |
| `top_L` | 0.0020681615 | 0.84359842 | 0 | n-Butane |
| `tray_EL_BTU` | 0.0020013788 | 515.45835 | 2 |  |
| `tray_EV_BTU` | 0.00089640484 | 84.411584 | 19 |  |
| `bottom_T_f` | 1.3610248e-05 | 0.0030175319 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `bottom_L` | 21 | n-Propane | 0.30468592 | 0.0079242276 | 37.449921 |
| 2 | `tray_T_f` | 2 |  | -0.91042976 | 0.0073441175 | 122.96721 |
| 3 | `tray_V` | 9 | n-Pentane | 0.0068195174 | 0.0063118153 | 0.08043678 |
| 4 | `tray_V` | 10 | n-Pentane | 0.0069658822 | 0.0062629167 | 0.11224251 |
| 5 | `tray_V` | 8 | n-Pentane | 0.0065493266 | 0.0062365655 | 0.050149581 |
| 6 | `tray_V` | 11 | n-Pentane | 0.0070790447 | 0.0061829495 | 0.14493006 |
| 7 | `tray_V` | 12 | n-Pentane | 0.0071945064 | 0.0061084518 | 0.1777954 |
| 8 | `tray_V` | 13 | n-Pentane | 0.0073070876 | 0.006028675 | 0.21205533 |
| 9 | `tray_V` | 14 | n-Pentane | 0.0074109551 | 0.0059427663 | 0.24705477 |
| 10 | `tray_V` | 15 | n-Pentane | 0.0075043416 | 0.0058505392 | 0.28267522 |
| 11 | `tray_V` | 16 | n-Pentane | 0.0079594937 | 0.0058259734 | 0.36620839 |
| 12 | `tray_V` | 7 | n-Pentane | 0.0057763396 | 0.0056424585 | 0.023727437 |
| 13 | `tray_L` | 19 | n-Pentane | 0.024242653 | 0.0056186472 | 3.3146779 |
| 14 | `tray_V` | 17 | n-Pentane | 0.0079092948 | 0.0056119833 | 0.40935823 |
| 15 | `tray_V` | 18 | n-Pentane | 0.0077909775 | 0.0053687663 | 0.45116718 |
| 16 | `tray_L` | 9 | n-Pentane | -0.0084076514 | 0.0053380082 | 0.57505405 |
| 17 | `tray_L` | 2 | n-Propane | 0.18559054 | 0.0047710175 | 37.899572 |
| 18 | `tray_L` | 10 | n-Pentane | -0.008295532 | 0.0045527554 | 0.82209043 |
| 19 | `tray_L` | 8 | n-Pentane | -0.0058532649 | 0.0044097291 | 0.32735249 |
| 20 | `tray_L` | 5 | n-Butane | -0.073685213 | 0.0042536304 | 16.3229 |
