# Vapor/Equilibrium/Energy Coupling Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_baseline_pressureaudit_60s_20260706\column_profile_20260706_182513.csv`
Time: `40 s`
Stage rows: `20`

## Summary

| Check | Value |
|---|---:|
| max \|ln(K_state/K_thermo)\| | 0.689451 |
| max \|sum(y)-1\| | 2.22045e-16 |
| max \|y-normalized(Kx)\| | 0.11714 |
| max \|sum(Kx)-1\| | 0.114039 |
| max \|sum(y/K)-1\| | 0.011724 |
| max \|P_from_vapor_holdup-P_state\| psia | 29.7686 |
| max \|relative pressure error\| | 0.132268 |
| max \|energy residual\| BTU/s | 961.997 |
| max \|raw dT/dt\| F/s | 0.293493 |
| max \|V_calc-V_used\| lbmol/h | 43.8823 |
| max \|estimated dV/dP\| lbmol/h/psi | 20127.6 |

## Worst Records

### K-State vs K-Thermo

| Field | Value |
|---|---:|
| time_s | 40 |
| stage_1based | 20 |
| component | n_Propane |
| K_state | 1 |
| K_thermo | 1.99262 |
| ln_K_ratio | -0.689451 |
| K_ratio | 0.501852 |

### Vapor y vs normalized(Kx)

| Field | Value |
|---|---:|
| time_s | 40 |
| stage_1based | 20 |
| sum_y_error | 0 |
| max_abs_y_minus_normalized_Kx | 0.11714 |
| worst_component | n_Propane |
| y | 0.148533 |
| normalized_Kx | 0.265673 |

### Bubble Residual

| Field | Value |
|---|---:|
| time_s | 40 |
| stage_1based | 20 |
| bubble_residual | 0.114039 |
| dew_residual | 0.000929358 |

### Dew Residual

| Field | Value |
|---|---:|
| time_s | 40 |
| stage_1based | 4 |
| bubble_residual | 0.0227593 |
| dew_residual | 0.011724 |

### Pressure From Vapor Holdup

| Field | Value |
|---|---:|
| time_s | 40 |
| stage_1based | 3 |
| P_state_psia | 225.063 |
| P_from_vapor_holdup_psia | 195.295 |
| P_error_psia | -29.7686 |
| relative_P_error | -0.132268 |
| MV_lbmol | 11.1788 |
| tray_vapor_volume_ft3 | 254.209 |
| Z_tray | 0.711954 |

### Relative Pressure From Vapor Holdup

| Field | Value |
|---|---:|
| time_s | 40 |
| stage_1based | 3 |
| P_state_psia | 225.063 |
| P_from_vapor_holdup_psia | 195.295 |
| P_error_psia | -29.7686 |
| relative_P_error | -0.132268 |
| MV_lbmol | 11.1788 |
| tray_vapor_volume_ft3 | 254.209 |
| Z_tray | 0.711954 |

### Energy Residual

| Field | Value |
|---|---:|
| time_s | 40 |
| stage_1based | 4 |
| energy_residual_BTUps | 961.997 |
| dT_energy_raw_F_per_s | -0.175702 |
| energy_residual_over_heat_capacity_F_per_s | 1.20151 |

### Temperature Rate

| Field | Value |
|---|---:|
| time_s | 40 |
| stage_1based | 3 |
| energy_residual_BTUps | 833.576 |
| dT_energy_raw_F_per_s | -0.293493 |
| energy_residual_over_heat_capacity_F_per_s | 1.01269 |

### Vapor Flow Calc-Used

| Field | Value |
|---|---:|
| time_s | 40 |
| stage_1based | 16 |
| V_used_lbmolph | 7675.5 |
| V_calc_lbmolph | 7631.61 |
| V_calc_minus_used_lbmolph | -43.8823 |
| hydraulic_dp_used_psia | 0.466112 |
| hydraulic_dp_raw_psia | 0.00233316 |
| estimated_dVdP_lbmolph_per_psia | 16372.9 |
| negative_or_zero_flow | False |

### Vapor Flow Sensitivity

| Field | Value |
|---|---:|
| time_s | 40 |
| stage_1based | 4 |
| V_used_lbmolph | 7877.49 |
| V_calc_lbmolph | 7892.54 |
| V_calc_minus_used_lbmolph | 15.0503 |
| hydraulic_dp_used_psia | 0.392125 |
| hydraulic_dp_raw_psia | 0.00196281 |
| estimated_dVdP_lbmolph_per_psia | 20127.6 |
| negative_or_zero_flow | False |

## Pressure Holdup Consistency

Available: `True`

Records: `19`
