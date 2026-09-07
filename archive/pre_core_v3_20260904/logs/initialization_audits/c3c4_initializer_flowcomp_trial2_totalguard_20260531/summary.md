# Column Initialization Residual Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_initializer_flowcomp_trial2_totalguard_20260531.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `parity`
- Pressure model: `spec`
- Vapor flow model: `profile`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.029075466 1/s`
- Worst absolute state rate: `0.63429506 per s`
- Max tray total material residual: `130.08257 lbmol/h`
- Total state inventory residual: `-1.1226575e-12 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_V` | 0.029075466 | 0.46480337 | 12 | n-Pentane |
| `tray_L` | 0.018080328 | 0.63429506 | 12 | n-Butane |
| `bottom_L` | 0.0030706061 | 0.11806456 | 21 | n-Propane |
| `top_L` | 0.0019832308 | 0.26180643 | 0 | n-Butane |
| `bottom_T_f` | 0 | 0 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |
| `tray_T_f` | 0 | 0 | 1 |  |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_V` | 12 | n-Pentane | 0.070315529 | 0.029075466 | 1.4183801 |
| 2 | `tray_V` | 12 | n-Butane | 0.46480337 | 0.023638005 | 18.663393 |
| 3 | `tray_V` | 11 | n-Pentane | 0.036022313 | 0.023340194 | 0.54335958 |
| 4 | `tray_V` | 10 | n-Pentane | 0.024247439 | 0.019041338 | 0.27341047 |
| 5 | `tray_L` | 12 | n-Butane | -0.63429506 | 0.018080328 | 34.082055 |
| 6 | `tray_L` | 2 | n-Butane | -0.14607884 | 0.017112075 | 7.5365943 |
| 7 | `tray_V` | 12 | n-Propane | 0.24813394 | 0.013702413 | 17.108777 |
| 8 | `tray_L` | 3 | n-Butane | -0.14667112 | 0.012704895 | 10.544457 |
| 9 | `tray_V` | 9 | n-Pentane | 0.013605469 | 0.012175831 | 0.11741606 |
| 10 | `tray_L` | 12 | n-Pentane | -0.050239151 | 0.011283525 | 3.452434 |
| 11 | `tray_L` | 11 | n-Pentane | -0.022939971 | 0.010510119 | 1.1826556 |
| 12 | `tray_V` | 18 | n-Propane | -0.093371179 | 0.0099596783 | 8.3749192 |
| 13 | `tray_V` | 19 | n-Pentane | 0.036789341 | 0.0098418525 | 2.7380504 |
| 14 | `tray_L` | 10 | n-Pentane | -0.016891396 | 0.0096461976 | 0.75109375 |
| 15 | `tray_L` | 4 | n-Butane | -0.14084857 | 0.0095785246 | 13.704621 |
| 16 | `tray_V` | 4 | n-Butane | 0.077197896 | 0.0093032714 | 7.2979301 |
| 17 | `tray_V` | 17 | n-Propane | -0.10510302 | 0.0092899653 | 10.313608 |
| 18 | `tray_V` | 18 | n-Pentane | 0.029121091 | 0.009044286 | 2.219833 |
| 19 | `tray_V` | 13 | n-Pentane | 0.016155765 | 0.008788261 | 0.83833472 |
| 20 | `tray_V` | 5 | n-Butane | 0.080257142 | 0.0087523832 | 8.1697472 |
