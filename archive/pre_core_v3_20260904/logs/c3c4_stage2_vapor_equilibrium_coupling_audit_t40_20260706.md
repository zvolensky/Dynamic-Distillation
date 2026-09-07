# Vapor/Equilibrium/Energy Coupling Audit

Profile: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_stage2_residual_60s_20260706\column_profile_20260706_175720.csv`
Time: `40 s`
Stage rows: `20`

## Summary

| Check | Value |
|---|---:|
| max \|ln(K_state/K_thermo)\| | 1.37701 |
| max \|sum(y)-1\| | 2.22045e-16 |
| max \|y-normalized(Kx)\| | 0.126378 |
| max \|sum(Kx)-1\| | 0.123855 |
| max \|sum(y/K)-1\| | 0.14116 |
| max \|energy residual\| BTU/s | 975.731 |
| max \|raw dT/dt\| F/s | 1.04917 |
| max \|V_calc-V_used\| lbmol/h | 911.791 |
| max \|estimated dV/dP\| lbmol/h/psi | 19483.3 |

## Worst Records

### K-State vs K-Thermo

| Field | Value |
|---|---:|
| time_s | 40 |
| stage_1based | 4 |
| component | n_Pentane |
| K_state | 0.902313 |
| K_thermo | 0.227682 |
| ln_K_ratio | 1.37701 |
| K_ratio | 3.96304 |

### Vapor y vs normalized(Kx)

| Field | Value |
|---|---:|
| time_s | 40 |
| stage_1based | 4 |
| sum_y_error | 0 |
| max_abs_y_minus_normalized_Kx | 0.126378 |
| worst_component | n_Propane |
| y | 0.710741 |
| normalized_Kx | 0.837119 |

### Bubble Residual

| Field | Value |
|---|---:|
| time_s | 40 |
| stage_1based | 20 |
| bubble_residual | 0.123855 |
| dew_residual | -0.00816326 |

### Dew Residual

| Field | Value |
|---|---:|
| time_s | 40 |
| stage_1based | 4 |
| bubble_residual | -0.00312895 |
| dew_residual | 0.14116 |

### Energy Residual

| Field | Value |
|---|---:|
| time_s | 40 |
| stage_1based | 4 |
| energy_residual_BTUps | 975.731 |
| dT_energy_raw_F_per_s | -0.108419 |
| energy_residual_over_heat_capacity_F_per_s | 1.20426 |

### Temperature Rate

| Field | Value |
|---|---:|
| time_s | 40 |
| stage_1based | 19 |
| energy_residual_BTUps | -311.956 |
| dT_energy_raw_F_per_s | 1.04917 |
| energy_residual_over_heat_capacity_F_per_s | -0.210736 |

### Vapor Flow Calc-Used

| Field | Value |
|---|---:|
| time_s | 40 |
| stage_1based | 19 |
| V_used_lbmolph | 7890.02 |
| V_calc_lbmolph | 8801.81 |
| V_calc_minus_used_lbmolph | 911.791 |
| hydraulic_dp_used_psia | 0.550163 |
| hydraulic_dp_raw_psia | 0.00250215 |
| estimated_dVdP_lbmolph_per_psia | 15998.6 |
| negative_or_zero_flow | False |

### Vapor Flow Sensitivity

| Field | Value |
|---|---:|
| time_s | 40 |
| stage_1based | 9 |
| V_used_lbmolph | 6733.52 |
| V_calc_lbmolph | 6675.38 |
| V_calc_minus_used_lbmolph | -58.1406 |
| hydraulic_dp_used_psia | 0.34262 |
| hydraulic_dp_raw_psia | 0.00155824 |
| estimated_dVdP_lbmolph_per_psia | 19483.3 |
| negative_or_zero_flow | False |

## Pressure Holdup Consistency

Available: `False`

profile CSV does not include tray vapor volume/Z data needed to compute P_from_vapor_holdup
