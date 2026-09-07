# Column Initialization Residual Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_depropanizer_chemsep_warmer_feed_pr76_source_energy_reconciled_20260531.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `parity`
- Pressure model: `spec`
- Vapor flow model: `profile`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.041678272 1/s`
- Worst absolute state rate: `13841.785 per s`
- Max tray total material residual: `0.005555649 lbmol/h`
- Total state inventory residual: `2.0777112e-11 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_V` | 0.041678272 | 0.23858972 | 2 | n-Butane |
| `tray_EL_BTU` | 0.041464754 | 13841.785 | 2 |  |
| `tray_L` | 0.021166411 | 0.23859027 | 19 | n-Propane |
| `bottom_L` | 5.0172774e-06 | 0.00050480376 | 21 | n-Propane |
| `top_L` | 3.3908892e-14 | 4.4763152e-12 | 0 | n-Butane |
| `bottom_T_f` | 0 | 0 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |
| `tray_EV_BTU` | 0 | 0 | 1 |  |
| `tray_T_f` | 0 | 0 | 1 |  |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_V` | 2 | n-Butane | 0.16179753 | 0.041678272 | 2.8820595 |
| 2 | `tray_EL_BTU` | 2 |  | 13841.785 | 0.041464754 | -333819.49 |
| 3 | `tray_V` | 3 | n-Butane | 0.17537523 | 0.03090063 | 4.6754582 |
| 4 | `tray_EL_BTU` | 12 |  | -6330.3346 | 0.026240129 | -241245.33 |
| 5 | `tray_V` | 11 | n-Pentane | 0.030172175 | 0.021597429 | 0.39702621 |
| 6 | `tray_L` | 19 | n-Propane | 0.11936992 | 0.021166411 | 4.6395918 |
| 7 | `tray_V` | 4 | n-Butane | 0.15775641 | 0.02018248 | 6.8165027 |
| 8 | `tray_V` | 19 | n-Pentane | 0.068150827 | 0.019755832 | 2.4496561 |
| 9 | `tray_L` | 2 | n-Butane | -0.16179764 | 0.018675923 | 7.6634345 |
| 10 | `tray_V` | 19 | n-Propane | -0.11906209 | 0.017178703 | 5.9307961 |
| 11 | `tray_L` | 18 | n-Propane | 0.12730925 | 0.016175519 | 6.8704894 |
| 12 | `tray_L` | 3 | n-Butane | -0.17537512 | 0.014382393 | 11.193738 |
| 13 | `tray_V` | 18 | n-Propane | -0.12730921 | 0.013814106 | 8.2158848 |
| 14 | `tray_V` | 10 | n-Pentane | 0.016569796 | 0.013741115 | 0.20585532 |
| 15 | `tray_L` | 11 | n-Pentane | -0.030172175 | 0.012650295 | 1.3850965 |
| 16 | `tray_V` | 5 | n-Butane | 0.12147958 | 0.012572384 | 8.6624143 |
| 17 | `tray_L` | 17 | n-Propane | 0.12931943 | 0.012394286 | 9.4337942 |
| 18 | `tray_V` | 17 | n-Propane | -0.12931942 | 0.011208702 | 10.537413 |
| 19 | `tray_L` | 4 | n-Butane | -0.15775641 | 0.010039548 | 14.713498 |
| 20 | `tray_L` | 4 | n-Propane | 0.19805938 | 0.010031406 | 18.74393 |
