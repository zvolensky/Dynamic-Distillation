# Column Initialization Residual Audit

- Excel: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_initializer_trayV_comp_stage2_19_20260705.xlsx`
- Thermo: `table`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.022597319 1/s`
- Worst absolute state rate: `2052.8338 per s`
- Max tray total material residual: `2545.2284 lbmol/h`
- Total state inventory residual: `-5.9366531 lbmol/h`

## Top Boundary Diagnostics

- Total condenser boundary energy residual: `-1.8189894e-12 Btu/s`
- Total condenser boundary energy residual relative scale: `-1.2218224e-16`
- Total condenser boundary energy owner: `1`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_V` | 0.022597319 | 0.69623477 | 2 | n-Propane |
| `tray_L` | 0.011614218 | 0.19628944 | 3 | n-Butane |
| `tray_EL_BTU` | 0.0070599851 | 2052.8338 | 12 |  |
| `tray_T_f` | 0.0043413687 | 0.53818737 | 2 |  |
| `tray_EV_BTU` | 0.0039241162 | 111.52935 | 19 |  |
| `top_L` | 0.0032850333 | 0.44045218 | 0 | n-Butane |
| `bottom_L` | 0.0018821464 | 0.072368378 | 21 | n-Propane |
| `bottom_T_f` | 6.7281034e-06 | 0.0014916897 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_V` | 2 | n-Propane | -0.69623477 | 0.022597319 | 29.810503 |
| 2 | `tray_V` | 12 | n-Butane | 0.09649577 | 0.013053616 | 6.3922635 |
| 3 | `tray_V` | 19 | n-Propane | -0.047290964 | 0.012824453 | 2.6875618 |
| 4 | `tray_V` | 6 | n-Butane | 0.073021118 | 0.012725783 | 4.7380453 |
| 5 | `tray_V` | 5 | n-Butane | 0.068472515 | 0.012478899 | 4.4870638 |
| 6 | `tray_V` | 18 | n-Propane | -0.049898133 | 0.012454129 | 3.0065533 |
| 7 | `tray_V` | 7 | n-Butane | 0.074668029 | 0.01242852 | 5.0077974 |
| 8 | `tray_V` | 17 | n-Propane | -0.052752912 | 0.012100817 | 3.3594506 |
| 9 | `tray_V` | 16 | n-Propane | -0.056828804 | 0.011981067 | 3.7432172 |
| 10 | `tray_V` | 4 | n-Butane | 0.062538423 | 0.011887936 | 4.2606628 |
| 11 | `tray_V` | 13 | n-Butane | 0.090652833 | 0.011825041 | 6.666175 |
| 12 | `tray_V` | 8 | n-Butane | 0.07395223 | 0.011761476 | 5.287666 |
| 13 | `tray_V` | 14 | n-Butane | 0.092510278 | 0.011675605 | 6.9233818 |
| 14 | `tray_L` | 3 | n-Butane | -0.13306927 | 0.011614218 | 10.457445 |
| 15 | `tray_V` | 3 | n-Butane | 0.058032299 | 0.011464014 | 4.0621274 |
| 16 | `tray_V` | 9 | n-Butane | 0.07506992 | 0.011425022 | 5.5706586 |
| 17 | `tray_V` | 15 | n-Butane | 0.092421138 | 0.011320291 | 7.1642019 |
| 18 | `tray_V` | 11 | n-Butane | 0.076066109 | 0.010663008 | 6.1336444 |
| 19 | `tray_V` | 10 | n-Butane | 0.072422882 | 0.010568583 | 5.8526574 |
| 20 | `tray_V` | 12 | n-Pentane | 0.012328331 | 0.0099034509 | 0.24485202 |
