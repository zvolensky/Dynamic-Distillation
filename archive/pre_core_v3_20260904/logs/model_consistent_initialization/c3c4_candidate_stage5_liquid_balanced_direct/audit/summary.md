# Column Initialization Residual Audit

- Excel: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_model_consistent_seed_candidate_stage5_liquid_balanced.xlsx`
- Thermo: `table`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.0052172538 1/s`
- Worst absolute state rate: `455.9343 per s`
- Max tray total material residual: `217.86797 lbmol/h`
- Total state inventory residual: `594.69656 lbmol/h`

## Top Boundary Diagnostics

- Total condenser boundary energy residual: `0 Btu/s`
- Total condenser boundary energy residual relative scale: `0`
- Total condenser boundary energy owner: `1`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `bottom_L` | 0.0052172538 | 0.34469048 | 21 | n-Propane |
| `tray_L` | 0.0042314389 | 0.057191559 | 17 | n-Pentane |
| `tray_V` | 0.0041785579 | 0.0048371589 | 7 | n-Pentane |
| `tray_T_f` | 0.0035637622 | 0.44178966 | 2 |  |
| `tray_EL_BTU` | 0.0018054668 | 455.9343 | 2 |  |
| `top_L` | 0.0016036741 | 0.76296719 | 0 | n-Butane |
| `tray_EV_BTU` | 0.00047825772 | 25.98225 | 19 |  |
| `bottom_T_f` | 0.00020239336 | 0.04487269 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `bottom_L` | 21 | n-Propane | 0.20060299 | 0.0052172538 | 37.449921 |
| 2 | `tray_L` | 17 | n-Pentane | 0.016637666 | 0.0042314389 | 2.9319168 |
| 3 | `tray_L` | 18 | n-Pentane | 0.014705206 | 0.0041944686 | 2.5058567 |
| 4 | `tray_V` | 7 | n-Pentane | 0.0042920425 | 0.0041785579 | 0.027158795 |
| 5 | `tray_V` | 8 | n-Pentane | 0.0043103039 | 0.0041203475 | 0.04610205 |
| 6 | `tray_L` | 19 | n-Pentane | 0.012955487 | 0.0041175068 | 2.1464398 |
| 7 | `tray_L` | 16 | n-Pentane | 0.017513881 | 0.0041147796 | 3.2563352 |
| 8 | `tray_V` | 9 | n-Pentane | 0.0042815193 | 0.0040188259 | 0.065365706 |
| 9 | `tray_V` | 6 | n-Pentane | 0.0040048786 | 0.0039663623 | 0.0097107233 |
| 10 | `tray_V` | 10 | n-Pentane | 0.0042532806 | 0.0039211331 | 0.084707001 |
| 11 | `tray_V` | 11 | n-Pentane | 0.0042411656 | 0.0038413252 | 0.10408917 |
| 12 | `tray_V` | 12 | n-Pentane | 0.0042563963 | 0.0037894696 | 0.12321692 |
| 13 | `tray_V` | 16 | n-Pentane | 0.0046458652 | 0.0037595872 | 0.2357381 |
| 14 | `tray_V` | 13 | n-Pentane | 0.0042915229 | 0.0037543979 | 0.14306553 |
| 15 | `tray_V` | 14 | n-Pentane | 0.0043448706 | 0.0037349576 | 0.16329852 |
| 16 | `tray_V` | 15 | n-Pentane | 0.0044178635 | 0.0037313472 | 0.18398617 |
| 17 | `tray_V` | 17 | n-Pentane | 0.0046918255 | 0.0037199402 | 0.26126369 |
| 18 | `tray_V` | 18 | n-Pentane | 0.0047548468 | 0.003695187 | 0.28676757 |
| 19 | `tray_V` | 19 | n-Pentane | 0.0048371589 | 0.003686653 | 0.31207326 |
| 20 | `tray_L` | 15 | n-Pentane | 0.014411883 | 0.0035771595 | 3.0288622 |
