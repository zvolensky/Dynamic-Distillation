# Column Initialization Residual Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_splitter_openloop_seed_coupledclosure_blend010_iter3b_20260528.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `parity`
- Pressure model: `spec`
- Vapor flow model: `profile`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.039464693 1/s`
- Worst absolute state rate: `0.35183906 per s`
- Max tray total material residual: `0.09 lbmol/h`
- Total state inventory residual: `-0.0060691 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `top_L` | 0.039464693 | 0.35183906 | 0 | n-Pentane |
| `tray_V` | 0.018405532 | 0.19479454 | 19 | n-Pentane |
| `tray_L` | 0.016313711 | 0.20645053 | 2 | n-Butane |
| `bottom_L` | 0.0043343735 | 0.16804428 | 21 | n-Propane |
| `bottom_T_f` | 0 | 0 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |
| `tray_T_f` | 0 | 0 | 1 |  |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `top_L` | 0 | n-Pentane | 0.039788576 | 0.039464693 | 0.0082068935 |
| 2 | `tray_V` | 19 | n-Pentane | 0.067622509 | 0.018405532 | 2.6740318 |
| 3 | `tray_L` | 2 | n-Butane | -0.12973487 | 0.016313711 | 6.9525048 |
| 4 | `tray_V` | 2 | n-Butane | 0.11939699 | 0.014877238 | 7.025481 |
| 5 | `tray_V` | 3 | n-Butane | 0.13256495 | 0.014665184 | 8.0394329 |
| 6 | `tray_V` | 11 | n-Pentane | 0.024097373 | 0.013847129 | 0.7402433 |
| 7 | `tray_L` | 3 | n-Butane | -0.14102024 | 0.013108421 | 9.7579886 |
| 8 | `tray_V` | 18 | n-Propane | -0.1031181 | 0.012241618 | 7.4235675 |
| 9 | `tray_V` | 19 | n-Propane | 0.079427438 | 0.012094132 | 5.5674361 |
| 10 | `tray_L` | 11 | n-Pentane | -0.02443488 | 0.011486821 | 1.12721 |
| 11 | `tray_V` | 4 | n-Butane | 0.12134588 | 0.011392401 | 9.6514754 |
| 12 | `tray_V` | 17 | n-Propane | -0.10448191 | 0.010139706 | 9.3042342 |
| 13 | `tray_V` | 3 | n-Propane | -0.19429451 | 0.0096677611 | 19.097156 |
| 14 | `tray_L` | 4 | n-Butane | -0.12668369 | 0.009321103 | 12.591062 |
| 15 | `tray_V` | 4 | n-Propane | -0.16046096 | 0.0090862094 | 16.659836 |
| 16 | `tray_L` | 12 | n-Pentane | 0.03793825 | 0.0084441776 | 3.4928295 |
| 17 | `tray_L` | 10 | n-Pentane | -0.013431055 | 0.0084073467 | 0.59753789 |
| 18 | `tray_V` | 10 | n-Pentane | 0.013248738 | 0.0083357742 | 0.58938308 |
| 19 | `tray_L` | 19 | n-Propane | 0.096108326 | 0.0083331415 | 10.533265 |
| 20 | `tray_V` | 16 | n-Propane | -0.10041739 | 0.0082909033 | 11.111755 |
