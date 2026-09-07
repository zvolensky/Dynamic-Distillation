# Column Initialization Residual Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\validation_gani_1986_debutanizer.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `parity`
- Pressure model: `spec`
- Vapor flow model: `profile`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.084019148 1/s`
- Worst absolute state rate: `0.098925361 per s`
- Max tray total material residual: `1231.7613 lbmol/h`
- Total state inventory residual: `2.6455609e-08 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_V` | 0.084019148 | 0.085587593 | 26 | Isobutene |
| `tray_L` | 0.045367424 | 0.098925361 | 28 | Isobutene |
| `bottom_L` | 0.0033657157 | 0.088761706 | 29 | 1-pentene |
| `top_L` | 1.3801648e-09 | 7.0417357e-08 | 0 | Isobutene |
| `bottom_T_f` | 0 | 0 | 29 | 1,3-butadiene |
| `bottom_V` | 0 | 0 | 29 | 1,3-butadiene |
| `top_V` | 0 | 0 | 0 | 1,3-butadiene |
| `tray_T_f` | 0 | 0 | 1 |  |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_V` | 26 | Isobutene | -0.085587593 | 0.084019148 | 0.018667715 |
| 2 | `tray_V` | 26 | 1,3-butadiene | -0.070981151 | 0.069833921 | 0.016427971 |
| 3 | `tray_L` | 28 | Isobutene | 0.061462853 | 0.045367424 | 0.35477944 |
| 4 | `tray_L` | 28 | 1,3-butadiene | 0.058805053 | 0.043365833 | 0.35602269 |
| 5 | `tray_L` | 28 | 1-pentene | 0.098925361 | 0.043065429 | 1.2970945 |
| 6 | `tray_V` | 26 | Benzene | 0.041893153 | 0.041847313 | 0.0010953989 |
| 7 | `tray_V` | 26 | 1-pentene | 0.039006091 | 0.038686554 | 0.0082596278 |
| 8 | `tray_V` | 26 | N-pentane | 0.033567309 | 0.033419468 | 0.004423821 |
| 9 | `tray_V` | 27 | Benzene | 0.033047216 | 0.032817421 | 0.0070022197 |
| 10 | `tray_L` | 28 | N-pentane | 0.062909707 | 0.032410138 | 0.94105024 |
| 11 | `tray_V` | 26 | 1-hexene | 0.031386843 | 0.031351558 | 0.0011254658 |
| 12 | `tray_V` | 27 | Isobutene | -0.027274647 | 0.027078913 | 0.0072282755 |
| 13 | `tray_V` | 27 | 1,3-butadiene | -0.025341993 | 0.025166601 | 0.0069692238 |
| 14 | `tray_L` | 27 | Isobutene | 0.041411468 | 0.02403692 | 0.72282755 |
| 15 | `tray_V` | 25 | Isobutene | -0.022828079 | 0.022350414 | 0.021371629 |
| 16 | `tray_L` | 27 | 1,3-butadiene | 0.03589762 | 0.021154544 | 0.69692238 |
| 17 | `tray_V` | 27 | 1-hexene | 0.01771344 | 0.017615497 | 0.0055600836 |
| 18 | `tray_V` | 22 | Isobutene | -0.017773827 | 0.017333808 | 0.025384984 |
| 19 | `tray_V` | 25 | 1-pentene | 0.017000133 | 0.016901506 | 0.0058353798 |
| 20 | `tray_L` | 26 | Isobutene | 0.033838503 | 0.016104262 | 1.1012141 |
