# Column Initialization Residual Audit

- Excel: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_initializer_residual_stage2_vflowclosure_stageA_20260707.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `True`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.017931394 1/s`
- Worst absolute state rate: `1751.6004 per s`
- Max tray total material residual: `2192.7481 lbmol/h`
- Total state inventory residual: `-5.9366531 lbmol/h`

## Top Boundary Diagnostics

- Total condenser boundary energy residual: `0 Btu/s`
- Total condenser boundary energy residual relative scale: `0`
- Total condenser boundary energy owner: `1`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_V` | 0.017931394 | 0.65793651 | 2 | n-Propane |
| `tray_EL_BTU` | 0.0087797331 | 1751.6004 | 2 |  |
| `tray_L` | 0.0046183291 | 0.072309771 | 19 | n-Pentane |
| `bottom_L` | 0.0030477807 | 0.11718692 | 21 | n-Propane |
| `tray_T_f` | 0.002393438 | 0.29671985 | 2 |  |
| `tray_EV_BTU` | 0.0023927065 | 195.20485 | 2 |  |
| `top_L` | 0.0006542831 | 0.21047869 | 0 | n-Butane |
| `bottom_T_f` | 1.2511514e-05 | 0.0027739313 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_V` | 2 | n-Propane | -0.65793651 | 0.017931394 | 35.691877 |
| 2 | `tray_EL_BTU` | 2 |  | 1751.6004 | 0.0087797331 | -199503.98 |
| 3 | `tray_V` | 15 | n-Butane | 0.060009606 | 0.0076630005 | 6.8310848 |
| 4 | `tray_V` | 14 | n-Butane | 0.043965839 | 0.0059782484 | 6.3543011 |
| 5 | `tray_V` | 8 | n-Pentane | 0.0059558548 | 0.0057531381 | 0.035235849 |
| 6 | `tray_L` | 19 | n-Pentane | 0.030407385 | 0.0046183291 | 5.5840664 |
| 7 | `tray_V` | 15 | n-Propane | 0.022195707 | 0.0045749557 | 3.8515677 |
| 8 | `tray_V` | 13 | n-Butane | 0.031517582 | 0.0045456836 | 5.9335186 |
| 9 | `tray_V` | 12 | n-Propane | 0.026664643 | 0.0042301009 | 5.3035478 |
| 10 | `tray_V` | 9 | n-Pentane | 0.0044494195 | 0.0041208978 | 0.0797209 |
| 11 | `tray_V` | 12 | n-Butane | 0.026766997 | 0.0040698463 | 5.5769061 |
| 12 | `tray_L` | 18 | n-Pentane | 0.027089511 | 0.0040026692 | 5.7678615 |
| 13 | `tray_V` | 14 | n-Propane | 0.020739785 | 0.0038359318 | 4.4067136 |
| 14 | `tray_V` | 7 | n-Propane | 0.028287772 | 0.0038210162 | 6.4032065 |
| 15 | `tray_V` | 13 | n-Propane | 0.022451852 | 0.0038097519 | 4.8932583 |
| 16 | `tray_V` | 17 | n-Butane | 0.037208782 | 0.0037193828 | 9.0040206 |
| 17 | `tray_V` | 8 | n-Propane | 0.026401845 | 0.0037179542 | 6.1011754 |
| 18 | `tray_EL_BTU` | 3 |  | 760.51438 | 0.0037091194 | -205038.07 |
| 19 | `tray_V` | 2 | n-Butane | -0.025230367 | 0.0036948896 | 5.8284495 |
| 20 | `tray_V` | 6 | n-Propane | 0.028503438 | 0.0036287298 | 6.8549353 |
