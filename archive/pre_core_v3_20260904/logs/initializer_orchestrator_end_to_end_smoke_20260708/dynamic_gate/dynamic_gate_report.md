# Initialization Dynamic Gate

Baseline: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\initializer_orchestrator_end_to_end_smoke_20260708\dynamic_gate\baseline\column_summary_20260708_134009.csv`

## coupled-vle-topL: PASS

| Check | Value | Limit | Candidate | Baseline | Result |
|---|---:|---:|---:|---:|---|
| final score ratio | 1 | 1 | 15.5544 | 15.5544 | PASS |
| peak score ratio | 1 | 1 | 15.5544 | 15.5544 | PASS |
| final relative state-rate ratio | 1 | 1 | 0.0466633 | 0.0466633 | PASS |
| peak relative state-rate ratio | 1 | 1 | 0.0466633 | 0.0466633 | PASS |

### Failure Breakdown

| Family | Ratio | Abs delta | Candidate | Baseline | Field |
|---|---:|---:|---:|---:|---|
| top liquid component net | 1 | 8.52886e-07 | 1635.86 | 1635.86 | `top_L_net_worst_abs_lbmolph` |
| K-state over K-thermo | 1 | 1.81204e-09 | 2.43715 | 2.43715 | `K_state_over_K_thermo_max_abs` |
| pressure inner solve | 1 | 5.11591e-13 | 0.0120747 | 0.0120747 | `pv_inner_dp_max_psia` |
| K-state minus K-thermo | 1 | 0 | 0.828876 | 0.828876 | `K_state_minus_K_thermo_max_abs` |
| temperature rate | 1 | -3.45466e-10 | 1.48787 | 1.48787 | `ss_max_temp_rate_F_per_s` |
| relative state rate | 1 | -1.68438e-09 | 0.0466633 | 0.0466633 | `ss_max_rel_state_rate_per_s` |
| pressure/vapor-flow inner solve | 1 | -6.46287e-09 | 1.67019 | 1.67019 | `pv_inner_dv_max_lbmolph` |
| top liquid total net | 1 | -1.70689e-08 | -1298.56 | -1298.56 | `top_L_net_lbmolph` |

