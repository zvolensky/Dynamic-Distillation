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
- Max tray total material residual: `1373.936 lbmol/h`
- Total state inventory residual: `-5.9366531 lbmol/h`

## Top Boundary Diagnostics

- Total condenser boundary energy residual: `0 Btu/s`
- Total condenser boundary energy residual relative scale: `0`
- Total condenser boundary energy owner: `1`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_EL_BTU` | 0.021527806 | 1210.56 | 12 |  |
| `tray_EV_BTU` | 0.011878662 | 1034.7467 | 14 |  |
| `tray_V` | 0.011564421 | 0.17757978 | 16 | n-Butane |
| `tray_T_f` | 0.0030408508 | 0.49472314 | 6 |  |
| `tray_L` | 0.0029058657 | 0.04511876 | 12 | n-Butane |
| `top_L` | 0.0021197663 | 0.71915783 | 0 | n-Pentane |
| `bottom_L` | 0.0014944997 | 0.36440748 | 21 | n-Propane |
| `bottom_T_f` | 1.4837613e-06 | 0.00032735809 | 21 | n-Propane |
| `bottom_V` | 0 | 0 | 21 | n-Propane |
| `top_V` | 0 | 0 | 0 | n-Propane |

## Worst State Rows

| Rank | Block | Stage | Component | Rate /s | Rel 1/s | Inventory |
|---:|---|---:|---|---:|---:|---:|
| 1 | `tray_EL_BTU` | 12 |  | -1210.56 | 0.021527806 | -56231.392 |
| 2 | `tray_EV_BTU` | 14 |  | 779.36596 | 0.011878662 | 65609.586 |
| 3 | `tray_V` | 16 | n-Butane | -0.16339148 | 0.011564421 | 13.128808 |
| 4 | `tray_EV_BTU` | 16 |  | -1034.7467 | 0.011413302 | 90660.463 |
| 5 | `tray_V` | 16 | n-Propane | -0.17757978 | 0.011347314 | 14.6495 |
| 6 | `tray_V` | 14 | n-Propane | 0.13304035 | 0.010757541 | 11.367171 |
| 7 | `tray_V` | 14 | n-Butane | 0.1158202 | 0.010241131 | 10.309318 |
| 8 | `tray_V` | 16 | n-Pentane | -0.018845248 | 0.0074679622 | 1.5234793 |
| 9 | `tray_EV_BTU` | 15 |  | 423.26044 | 0.0062561368 | 67654.24 |
| 10 | `tray_V` | 14 | n-Pentane | 0.013522019 | 0.0061652963 | 1.1932472 |
| 11 | `tray_EV_BTU` | 9 |  | -397.42497 | 0.0058980954 | 67380.915 |
| 12 | `tray_V` | 9 | n-Butane | -0.067833808 | 0.0054238927 | 11.50648 |
| 13 | `tray_V` | 15 | n-Propane | 0.066333037 | 0.0053755965 | 11.339661 |
| 14 | `tray_V` | 9 | n-Propane | -0.06500861 | 0.0049185688 | 12.216977 |
| 15 | `tray_V` | 15 | n-Butane | 0.055187302 | 0.0049183836 | 10.220618 |
| 16 | `tray_V` | 12 | n-Propane | 0.050679166 | 0.0043797044 | 10.571367 |
| 17 | `tray_EV_BTU` | 13 |  | 274.83683 | 0.0042938851 | 64005.565 |
| 18 | `tray_V` | 13 | n-Propane | 0.051155999 | 0.0041287516 | 11.390186 |
| 19 | `tray_EV_BTU` | 12 |  | 210.35825 | 0.0039981158 | 52613.348 |
| 20 | `tray_V` | 12 | n-Butane | 0.042065097 | 0.0039244663 | 9.7186796 |
