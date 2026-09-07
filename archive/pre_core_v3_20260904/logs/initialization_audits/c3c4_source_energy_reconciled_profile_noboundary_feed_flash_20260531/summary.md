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
- Worst relative state rate: `0.053120235 1/s`
- Worst absolute state rate: `13841.785 per s`
- Max tray total material residual: `0.005555649 lbmol/h`
- Total state inventory residual: `1.6825652e-11 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_V` | 0.053120235 | 0.63370957 | 12 | n-Pentane |
| `tray_EL_BTU` | 0.041464754 | 13841.785 | 2 |  |
| `tray_L` | 0.021624056 | 0.63370983 | 12 | n-Pentane |
| `tray_EV_BTU` | 0 | 0 | 1 |  |
| `tray_T_f` | 0 | 0 | 1 |  |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_V` | 12 | n-Pentane | 0.11451325 | 0.053120235 | 1.155737 |
| 2 | `tray_V` | 2 | n-Butane | 0.16179753 | 0.041678272 | 2.8820595 |
| 3 | `tray_EL_BTU` | 2 |  | 13841.785 | 0.041464754 | -333819.49 |
| 4 | `tray_V` | 12 | n-Butane | 0.63370957 | 0.034757059 | 17.232543 |
| 5 | `tray_V` | 3 | n-Butane | 0.17537523 | 0.03090063 | 4.6754582 |
| 6 | `tray_L` | 12 | n-Pentane | -0.11451329 | 0.021624056 | 4.2956436 |
| 7 | `tray_V` | 11 | n-Pentane | 0.030172175 | 0.021597429 | 0.39702621 |
| 8 | `tray_L` | 19 | n-Propane | 0.11936992 | 0.021166411 | 4.6395918 |
| 9 | `tray_V` | 4 | n-Butane | 0.15775641 | 0.02018248 | 6.8165027 |
| 10 | `tray_L` | 12 | n-Butane | -0.63370983 | 0.019841087 | 30.93927 |
| 11 | `tray_V` | 19 | n-Pentane | 0.068150827 | 0.019755832 | 2.4496561 |
| 12 | `tray_L` | 2 | n-Butane | -0.16179764 | 0.018675923 | 7.6634345 |
| 13 | `tray_V` | 19 | n-Propane | -0.11906209 | 0.017178703 | 5.9307961 |
| 14 | `tray_L` | 12 | n-Propane | -0.28623542 | 0.017010254 | 15.827227 |
| 15 | `tray_L` | 18 | n-Propane | 0.12730925 | 0.016175519 | 6.8704894 |
| 16 | `tray_V` | 12 | n-Propane | 0.28623527 | 0.01445467 | 18.80227 |
| 17 | `tray_L` | 3 | n-Butane | -0.17537512 | 0.014382393 | 11.193738 |
| 18 | `tray_V` | 18 | n-Propane | -0.12730921 | 0.013814106 | 8.2158848 |
| 19 | `tray_V` | 10 | n-Pentane | 0.016569796 | 0.013741115 | 0.20585532 |
| 20 | `tray_L` | 11 | n-Pentane | -0.030172175 | 0.012650295 | 1.3850965 |
