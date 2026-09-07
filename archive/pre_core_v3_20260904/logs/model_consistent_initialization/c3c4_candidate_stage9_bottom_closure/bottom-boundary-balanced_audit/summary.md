# Column Initialization Residual Audit

- Excel: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\model_consistent_initialization\c3c4_candidate_stage9_bottom_closure\bottom-boundary-balanced.xlsx`
- Thermo: `table`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.0098164165 1/s`
- Worst absolute state rate: `360.88976 per s`
- Max tray total material residual: `86.259332 lbmol/h`
- Total state inventory residual: `597.16758 lbmol/h`

## Top Boundary Diagnostics

- Total condenser boundary energy residual: `1.8189894e-12 Btu/s`
- Total condenser boundary energy residual relative scale: `1.5717567e-16`
- Total condenser boundary energy owner: `1`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_V` | 0.0098164165 | 0.058529385 | 19 | n-Pentane |
| `tray_T_f` | 0.0029440977 | 0.37059166 | 3 |  |
| `tray_L` | 0.0027384212 | 0.098296656 | 19 | n-Propane |
| `tray_EL_BTU` | 0.0014305887 | 360.88976 | 2 |  |
| `bottom_L` | 0.00096536204 | 0.29461588 | 21 | n-Propane |
| `top_L` | 0.0008998598 | 0.58115994 | 0 | n-Butane |
| `tray_EV_BTU` | 0.000734416 | 33.58943 | 19 |  |
| `bottom_T_f` | 0.00019594483 | 0.043442985 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_V` | 19 | n-Pentane | 0.013639822 | 0.0098164165 | 0.38949098 |
| 2 | `tray_V` | 19 | n-Butane | 0.058529385 | 0.0062996638 | 8.2908743 |
| 3 | `tray_V` | 18 | n-Pentane | 0.0068256638 | 0.0050796312 | 0.34373216 |
| 4 | `tray_V` | 17 | n-Pentane | 0.0062903485 | 0.0048371933 | 0.3004129 |
| 5 | `tray_V` | 19 | n-Propane | -0.023163024 | 0.0046546396 | 3.9763303 |
| 6 | `tray_V` | 16 | n-Pentane | 0.005803657 | 0.004606971 | 0.2597555 |
| 7 | `tray_V` | 15 | n-Pentane | 0.0051325421 | 0.0042970831 | 0.19442469 |
| 8 | `tray_V` | 14 | n-Pentane | 0.0046892629 | 0.0040222126 | 0.16584163 |
| 9 | `tray_V` | 13 | n-Pentane | 0.0042937171 | 0.0037662578 | 0.14004863 |
| 10 | `tray_V` | 12 | n-Pentane | 0.0039396633 | 0.0035277634 | 0.11675952 |
| 11 | `tray_V` | 11 | n-Pentane | 0.0036288959 | 0.0033108662 | 0.096056324 |
| 12 | `tray_V` | 10 | n-Pentane | 0.0033708533 | 0.0031305683 | 0.076754439 |
| 13 | `tray_V` | 9 | n-Pentane | 0.0031541762 | 0.0029786763 | 0.058918765 |
| 14 | `tray_T_f` | 3 |  | 0.37059166 | 0.0029440977 | 124.87614 |
| 15 | `tray_V` | 8 | n-Pentane | 0.0029719538 | 0.0028511928 | 0.042354536 |
| 16 | `tray_L` | 19 | n-Propane | 0.043583868 | 0.0027384212 | 14.915692 |
| 17 | `tray_V` | 7 | n-Pentane | 0.0028107826 | 0.0027370233 | 0.026948737 |
| 18 | `tray_V` | 6 | n-Pentane | 0.0026162262 | 0.0025829961 | 0.012864933 |
| 19 | `tray_L` | 18 | n-Propane | 0.04509358 | 0.0025722736 | 16.530631 |
| 20 | `tray_L` | 17 | n-Propane | 0.04802135 | 0.0024947021 | 18.249333 |
