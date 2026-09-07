# Column Initialization Residual Audit

- Excel: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_initializer_residual_vapor_state_stage2_20260706.xlsx`
- Initial state source: `native_checkpoint`
- Native checkpoint: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_liq_eq_vap_linearsteady_900s_eqcompguard_m1_20260708\c3c4_initializer_residual_vapor_state_stage2_20260706__checkpoint_20260708_084013.npz`
- Checkpoint restored memory keys: `last_HL, last_HV, last_K_tray, last_P_diag, last_P_hyd, last_T_tray, last_Zfac, last_bottom_sump_cp_packet, last_condenser_duty_packet, last_reb_T, last_reb_beta, last_reb_x, last_reb_y, last_tray_bubble_target_F, last_tray_thermo_packet, last_z_overall`
- Thermo: `table`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.021527806 1/s`
- Worst absolute state rate: `1210.56 per s`
- Max tray total material residual: `2004.1725 lbmol/h`
- Total state inventory residual: `-5.9366531 lbmol/h`

## Top Boundary Diagnostics

- Total condenser boundary energy residual: `0 Btu/s`
- Total condenser boundary energy residual relative scale: `0`
- Total condenser boundary energy owner: `1`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_EL_BTU` | 0.021527806 | 1210.56 | 12 |  |
| `tray_V` | 0.011952131 | 0.22826836 | 16 | n-Butane |
| `tray_EV_BTU` | 0.011907869 | 1101.8397 | 16 |  |
| `tray_T_f` | 0.010023247 | 1.812364 | 12 |  |
| `tray_L` | 0.0029058657 | 0.04511876 | 12 | n-Butane |
| `top_L` | 0.0021860771 | 0.70243878 | 0 | n-Pentane |
| `bottom_L` | 0.0014944997 | 0.36440748 | 21 | n-Propane |
| `bottom_T_f` | 1.4837613e-06 | 0.00032735809 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_EL_BTU` | 12 |  | -1210.56 | 0.021527806 | -56231.392 |
| 2 | `tray_V` | 16 | n-Butane | -0.16886937 | 0.011952131 | 13.128808 |
| 3 | `tray_EV_BTU` | 16 |  | -1079.5848 | 0.011907869 | 90660.463 |
| 4 | `tray_V` | 16 | n-Propane | -0.18366685 | 0.011736276 | 14.6495 |
| 5 | `tray_EV_BTU` | 12 |  | 536.50751 | 0.010196981 | 52613.348 |
| 6 | `tray_T_f` | 12 |  | 1.812364 | 0.010023247 | 179.81605 |
| 7 | `tray_EV_BTU` | 9 |  | -631.66897 | 0.0093744585 | 67380.915 |
| 8 | `tray_T_f` | 2 |  | 1.1053902 | 0.0089149221 | 122.99325 |
| 9 | `tray_EV_BTU` | 2 |  | 1101.8397 | 0.0084957475 | 129692.08 |
| 10 | `tray_V` | 12 | n-Propane | 0.093799842 | 0.0081062023 | 10.571367 |
| 11 | `tray_V` | 2 | n-Propane | 0.22826836 | 0.0078879958 | 27.938702 |
| 12 | `tray_V` | 2 | n-Butane | 0.2271674 | 0.007777381 | 28.208727 |
| 13 | `tray_V` | 16 | n-Pentane | -0.019480293 | 0.0077196167 | 1.5234793 |
| 14 | `tray_V` | 12 | n-Butane | 0.080625305 | 0.0075219437 | 9.7186796 |
| 15 | `tray_V` | 9 | n-Butane | -0.093553845 | 0.0074804296 | 11.50648 |
| 16 | `tray_T_f` | 14 |  | -1.3885814 | 0.007395095 | 186.77059 |
| 17 | `tray_V` | 9 | n-Propane | -0.090868236 | 0.006875115 | 12.216977 |
| 18 | `tray_V` | 2 | n-Pentane | 0.027340825 | 0.006555749 | 3.1705113 |
| 19 | `tray_V` | 9 | n-Pentane | -0.010628857 | 0.0045746178 | 1.3234416 |
| 20 | `tray_V` | 12 | n-Pentane | 0.0094253872 | 0.0044417208 | 1.1220125 |
