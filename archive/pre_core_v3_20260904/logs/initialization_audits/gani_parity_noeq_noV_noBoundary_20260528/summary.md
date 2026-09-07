# Column Initialization Residual Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\validation_gani_1986_debutanizer.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `parity`
- Pressure model: `spec`
- Vapor flow model: `profile`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `False`

## Gate

- Pass: `False`
- Worst relative state rate: `0.027447182 1/s`
- Worst absolute state rate: `0.051778635 per s`
- Max tray total material residual: `0.00079366414 lbmol/h`
- Total state inventory residual: `-8.7832144e-06 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_L` | 0.027447182 | 0.051778635 | 28 | Isobutene |
| `tray_T_f` | 0 | 0 | 1 |  |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_L` | 28 | Isobutene | 0.037184878 | 0.027447182 | 0.35477944 |
| 2 | `tray_L` | 28 | 1,3-butadiene | 0.034442001 | 0.025399281 | 0.35602269 |
| 3 | `tray_L` | 26 | Isobutene | -0.05174909 | 0.024628185 | 1.1012141 |
| 4 | `tray_L` | 26 | Benzene | 0.036323192 | 0.024027391 | 0.51174095 |
| 5 | `tray_L` | 28 | Benzene | -0.051778635 | 0.023400487 | 1.2127161 |
| 6 | `tray_L` | 26 | 1,3-butadiene | -0.044536825 | 0.022015544 | 1.0229718 |
| 7 | `tray_L` | 26 | 1-hexene | 0.025446189 | 0.018180949 | 0.39960731 |
| 8 | `tray_L` | 28 | 1-hexene | -0.028524408 | 0.015516419 | 0.838337 |
| 9 | `tray_L` | 27 | 1-pentene | -0.026521968 | 0.011061457 | 1.3976922 |
| 10 | `tray_L` | 26 | N-pentane | 0.018280748 | 0.010411983 | 0.75574129 |
| 11 | `tray_L` | 27 | Benzene | 0.015483205 | 0.0091065785 | 0.70022197 |
| 12 | `tray_L` | 27 | N-pentane | -0.016720216 | 0.0086798404 | 0.92632754 |
| 13 | `tray_L` | 27 | Isobutene | 0.014136821 | 0.0082055924 | 0.72282755 |
| 14 | `tray_L` | 26 | 1-pentene | 0.016235786 | 0.0073507519 | 1.2087245 |
| 15 | `tray_L` | 27 | 1,3-butadiene | 0.010555627 | 0.0062204534 | 0.69692238 |
| 16 | `tray_L` | 28 | 1-pentene | 0.010163655 | 0.0044245697 | 1.2970945 |
| 17 | `tray_L` | 27 | 1-hexene | 0.003066532 | 0.0019707683 | 0.55600836 |
| 18 | `tray_L` | 1 | 1,3-butadiene | 0.0048992888 | 0.0015671423 | 2.1262565 |
| 19 | `tray_L` | 1 | Isobutene | -0.0048997017 | 0.0012648505 | 2.8737397 |
| 20 | `tray_L` | 28 | N-pentane | -0.0014874692 | 0.00076632182 | 0.94105024 |
