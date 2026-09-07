# Column Initialization Residual Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_initializer_pf_pass2_terminal_layers_trial2_buffer_20260601.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.036500667 1/s`
- Worst absolute state rate: `2486.5387 per s`
- Max tray total material residual: `2571.9657 lbmol/h`
- Total state inventory residual: `-5.9366531 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_V` | 0.036500667 | 0.75166878 | 14 | n-Propane |
| `tray_L` | 0.017938614 | 0.22480949 | 2 | n-Butane |
| `tray_EL_BTU` | 0.011116383 | 2486.5387 | 2 |  |
| `tray_T_f` | 0.0049141504 | 0.62761564 | 2 |  |
| `bottom_L` | 0.0044788258 | 0.1722105 | 21 | n-Propane |
| `tray_EV_BTU` | 0.0037956919 | 107.87934 | 19 |  |
| `top_L` | 0.0023457094 | 0.30965725 | 0 | n-Butane |
| `top_V` | 0.00024034186 | 0.014749469 | 0 | n-Propane |
| `bottom_T_f` | 7.5229609e-06 | 0.0016679178 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_V` | 14 | n-Propane | -0.2060257 | 0.036500667 | 4.6444364 |
| 2 | `tray_V` | 14 | n-Butane | 0.25651067 | 0.035788545 | 6.167396 |
| 3 | `tray_V` | 2 | n-Propane | -0.75166878 | 0.022695013 | 32.120439 |
| 4 | `tray_V` | 5 | n-Butane | 0.086194446 | 0.018791936 | 3.5867783 |
| 5 | `tray_L` | 2 | n-Butane | -0.150836 | 0.017938614 | 7.4084535 |
| 6 | `tray_V` | 13 | n-Butane | 0.11727483 | 0.017400762 | 5.7396373 |
| 7 | `tray_V` | 6 | n-Butane | 0.085277077 | 0.017174423 | 3.9653532 |
| 8 | `tray_V` | 12 | n-Butane | 0.10902318 | 0.017131599 | 5.3638647 |
| 9 | `tray_V` | 7 | n-Butane | 0.079043644 | 0.014868372 | 4.3162273 |
| 10 | `tray_V` | 18 | n-Propane | -0.056709671 | 0.014837888 | 2.8219503 |
| 11 | `tray_V` | 17 | n-Propane | -0.062049378 | 0.014689601 | 3.2240343 |
| 12 | `tray_V` | 14 | n-Pentane | 0.018520492 | 0.01355272 | 0.36655164 |
| 13 | `tray_V` | 16 | n-Propane | -0.059521811 | 0.01288114 | 3.6208496 |
| 14 | `tray_V` | 11 | n-Pentane | 0.014930966 | 0.012699188 | 0.17574178 |
| 15 | `tray_V` | 18 | n-Pentane | 0.022390443 | 0.012682218 | 0.765499 |
| 16 | `tray_V` | 10 | n-Pentane | 0.013740353 | 0.012444668 | 0.10411567 |
| 17 | `tray_V` | 8 | n-Butane | 0.069736371 | 0.01240267 | 4.6226901 |
| 18 | `tray_V` | 17 | n-Pentane | 0.020304034 | 0.012251438 | 0.65727765 |
| 19 | `tray_V` | 19 | n-Propane | -0.042000049 | 0.012091431 | 2.4735382 |
| 20 | `tray_L` | 3 | n-Butane | -0.12949331 | 0.011866754 | 9.912277 |
