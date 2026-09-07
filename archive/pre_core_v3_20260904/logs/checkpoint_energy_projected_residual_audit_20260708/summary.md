# Column Initialization Residual Audit

- Excel: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_initializer_residual_vapor_state_stage2_20260706.xlsx`
- Initial state source: `native_checkpoint`
- Native checkpoint: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_liq_eq_vap_linearsteady_900s_eqcompguard_m1_20260708\c3c4_initializer_residual_vapor_state_stage2_20260706__checkpoint_energy_projected_20260708.npz`
- Checkpoint restored memory keys: `last_HL, last_HV, last_K_tray, last_P_diag, last_P_hyd, last_T_tray, last_Zfac, last_bottom_sump_cp_packet, last_condenser_duty_packet, last_reb_T, last_reb_beta, last_reb_x, last_reb_y, last_tray_bubble_target_F, last_tray_thermo_packet, last_z_overall`
- Thermo: `table`
- Runtime mode: `hydraulic`
- Pressure model: `hydraulic`
- Vapor flow model: `energy`
- Equilibrium relaxation: `False`
- Uses Excel vapor holdup: `True`

## Gate

- Pass: `False`
- Worst relative state rate: `0.021710038 1/s`
- Worst absolute state rate: `2836.5632 per s`
- Max tray total material residual: `1373.936 lbmol/h`
- Total state inventory residual: `-5.9366531 lbmol/h`

## Top Boundary Diagnostics

- Total condenser boundary energy residual: `-1.8189894e-12 Btu/s`
- Total condenser boundary energy residual relative scale: `-1.3735848e-16`
- Total condenser boundary energy owner: `1`

## Block Ranking

| Block | Max rel 1/s | Max abs /s | Worst stage | Worst comp |
|---|---:|---:|---:|---|
| `tray_EL_BTU` | 0.021710038 | 2836.5632 | 15 |  |
| `tray_V` | 0.011564421 | 0.17757978 | 16 | n-Butane |
| `tray_EV_BTU` | 0.0098108176 | 505.18635 | 14 |  |
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
| 1 | `tray_EL_BTU` | 15 |  | -2836.5632 | 0.021710038 | -130655.76 |
| 2 | `tray_V` | 16 | n-Butane | -0.16339148 | 0.011564421 | 13.128808 |
| 3 | `tray_V` | 16 | n-Propane | -0.17757978 | 0.011347314 | 14.6495 |
| 4 | `tray_V` | 14 | n-Propane | 0.13304035 | 0.010757541 | 11.367171 |
| 5 | `tray_V` | 14 | n-Butane | 0.1158202 | 0.010241131 | 10.309318 |
| 6 | `tray_EV_BTU` | 14 |  | 505.18635 | 0.0098108176 | 51491.788 |
| 7 | `tray_V` | 16 | n-Pentane | -0.018845248 | 0.0074679622 | 1.5234793 |
| 8 | `tray_EL_BTU` | 11 |  | -1171.313 | 0.0068917979 | -169956.54 |
| 9 | `tray_V` | 14 | n-Pentane | 0.013522019 | 0.0061652963 | 1.1932472 |
| 10 | `tray_EV_BTU` | 18 |  | 327.45724 | 0.0054857409 | 59691.436 |
| 11 | `tray_V` | 9 | n-Butane | -0.067833808 | 0.0054238927 | 11.50648 |
| 12 | `tray_EV_BTU` | 17 |  | 316.15345 | 0.0053782302 | 58782.918 |
| 13 | `tray_V` | 15 | n-Propane | 0.066333037 | 0.0053755965 | 11.339661 |
| 14 | `tray_V` | 9 | n-Propane | -0.06500861 | 0.0049185688 | 12.216977 |
| 15 | `tray_V` | 15 | n-Butane | 0.055187302 | 0.0049183836 | 10.220618 |
| 16 | `tray_EV_BTU` | 12 |  | -231.66069 | 0.0048438431 | 47824.803 |
| 17 | `tray_EV_BTU` | 4 |  | 233.29944 | 0.004836214 | 48239.099 |
| 18 | `tray_EV_BTU` | 15 |  | 236.4273 | 0.0045735255 | 51693.758 |
| 19 | `tray_V` | 12 | n-Propane | 0.050679166 | 0.0043797044 | 10.571367 |
| 20 | `tray_EV_BTU` | 16 |  | 290.82287 | 0.0042859521 | 67853.904 |
