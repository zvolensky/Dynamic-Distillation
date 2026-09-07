# Column Initialization Residual Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_initializer_profile_coeff_trial1_20260601.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.023805024 1/s`
- Worst absolute state rate: `2683.5759 per s`
- Max tray total material residual: `2503.8244 lbmol/h`
- Total state inventory residual: `-5.9366531 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_V` | 0.023805024 | 0.69148094 | 18 | n-Propane |
| `tray_L` | 0.014652805 | 0.19628944 | 3 | n-Butane |
| `tray_EL_BTU` | 0.011824095 | 2683.5759 | 2 |  |
| `tray_T_f` | 0.0038615454 | 0.4787244 | 2 |  |
| `bottom_L` | 0.0038121038 | 0.14657509 | 21 | n-Propane |
| `tray_EV_BTU` | 0.0038108459 | 108.31004 | 19 |  |
| `top_L` | 0.0014958993 | 0.19747376 | 0 | n-Butane |
| `top_V` | 0.00015474429 | 0.010288195 | 0 | n-Propane |
| `bottom_T_f` | 1.2511514e-05 | 0.0027739313 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_V` | 18 | n-Propane | -0.094014921 | 0.023805024 | 2.949373 |
| 2 | `tray_V` | 17 | n-Propane | -0.10419581 | 0.022664956 | 3.5972207 |
| 3 | `tray_V` | 4 | n-Butane | 0.084250859 | 0.022246092 | 2.7872206 |
| 4 | `tray_V` | 3 | n-Butane | 0.075474243 | 0.021955264 | 2.4376376 |
| 5 | `tray_V` | 5 | n-Butane | 0.088332547 | 0.021119702 | 3.1824712 |
| 6 | `tray_V` | 19 | n-Propane | -0.068155901 | 0.020143201 | 2.3835685 |
| 7 | `tray_V` | 16 | n-Propane | -0.10617911 | 0.02014014 | 4.2720146 |
| 8 | `tray_V` | 2 | n-Propane | -0.69148094 | 0.019704704 | 34.092176 |
| 9 | `tray_V` | 6 | n-Butane | 0.087765923 | 0.019156867 | 3.5814341 |
| 10 | `tray_V` | 15 | n-Butane | 0.13667497 | 0.018523833 | 6.3783311 |
| 11 | `tray_V` | 14 | n-Butane | 0.12737102 | 0.018423943 | 5.913342 |
| 12 | `tray_V` | 13 | n-Butane | 0.11516195 | 0.017765308 | 5.4824068 |
| 13 | `tray_V` | 12 | n-Butane | 0.10689167 | 0.01751884 | 5.1015269 |
| 14 | `tray_V` | 7 | n-Butane | 0.081675818 | 0.016478537 | 3.9564969 |
| 15 | `tray_V` | 15 | n-Propane | -0.084005808 | 0.015852951 | 4.2990643 |
| 16 | `tray_V` | 18 | n-Pentane | 0.027971405 | 0.015458818 | 0.80941416 |
| 17 | `tray_L` | 3 | n-Butane | -0.13306927 | 0.014652805 | 8.0814879 |
| 18 | `tray_V` | 11 | n-Pentane | 0.016949155 | 0.01413309 | 0.19925331 |
| 19 | `tray_V` | 10 | n-Pentane | 0.015649456 | 0.014003638 | 0.11752788 |
| 20 | `tray_V` | 8 | n-Butane | 0.072160689 | 0.013644762 | 4.288527 |
