# Column Initialization Residual Audit

- Excel: `C:\Users\Thoma\Documents\Python Scripts\Dynamic_DistillationII\validation_gani_1986_debutanizer_chemsep_source_topology.xlsx`
- Thermo: `clapeyron`
- Runtime mode: `parity`
- Pressure model: `spec`
- Vapor flow model: `profile`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `False`

## Gate

- Pass: `True`
- Worst relative state rate: `3.2573685e-08 1/s`
- Worst absolute state rate: `1.2125134e-07 per s`
- Max tray total material residual: `0.00079366414 lbmol/h`
- Total state inventory residual: `-8.7832144e-06 lbmol/h`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_L` | 3.2573685e-08 | 1.2125134e-07 | 6 | Isobutene |
| `tray_T_f` | 0 | 0 | 1 |  |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_L` | 6 | Isobutene | -1.2125134e-07 | 3.2573685e-08 | 2.722371 |
| 2 | `tray_L` | 9 | Isobutene | 1.2066936e-07 | 3.2543434e-08 | 2.7079481 |
| 3 | `tray_L` | 14 | Isobutene | -1.2005787e-07 | 3.2476564e-08 | 2.6967542 |
| 4 | `tray_L` | 18 | Isobutene | 1.178379e-07 | 3.2453326e-08 | 2.6309961 |
| 5 | `tray_L` | 22 | Isobutene | -9.8634273e-08 | 3.1949962e-08 | 2.0871483 |
| 6 | `tray_L` | 18 | 1,3-butadiene | 9.8239669e-08 | 3.0411125e-08 | 2.2303859 |
| 7 | `tray_L` | 14 | 1,3-butadiene | -9.9999597e-08 | 3.0401884e-08 | 2.2892566 |
| 8 | `tray_L` | 9 | 1,3-butadiene | 9.9768386e-08 | 3.0313177e-08 | 2.2912547 |
| 9 | `tray_L` | 6 | 1,3-butadiene | -9.9206849e-08 | 3.0269175e-08 | 2.2774877 |
| 10 | `tray_L` | 22 | 1,3-butadiene | -8.2514247e-08 | 3.0019296e-08 | 1.748707 |
| 11 | `tray_L` | 1 | Isobutene | 7.0406299e-08 | 1.8175279e-08 | 2.8737397 |
| 12 | `tray_L` | 1 | 1,3-butadiene | 5.2082442e-08 | 1.6659683e-08 | 2.1262565 |
| 13 | `tray_L` | 22 | 1-pentene | -2.2465915e-08 | 1.3907626e-08 | 0.61536658 |
| 14 | `tray_L` | 23 | Isobutene | 3.1283873e-08 | 1.1553543e-08 | 1.70773 |
| 15 | `tray_L` | 23 | 1,3-butadiene | 2.6416712e-08 | 1.0904084e-08 | 1.4226438 |
| 16 | `tray_L` | 22 | N-pentane | -1.1424341e-08 | 8.5489836e-09 | 0.33633904 |
| 17 | `tray_L` | 23 | 1-pentene | 9.2291097e-09 | 5.4188904e-09 | 0.70313643 |
| 18 | `tray_L` | 28 | Isobutene | 6.5216091e-09 | 4.8137792e-09 | 0.35477944 |
| 19 | `tray_L` | 28 | 1,3-butadiene | 6.1797891e-09 | 4.5572903e-09 | 0.35602269 |
| 20 | `tray_L` | 23 | N-pentane | 4.8392994e-09 | 3.3368657e-09 | 0.45025299 |
