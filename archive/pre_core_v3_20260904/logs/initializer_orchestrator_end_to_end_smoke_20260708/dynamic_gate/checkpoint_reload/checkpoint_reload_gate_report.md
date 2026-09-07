# Initialization Dynamic Gate

Baseline: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\initializer_orchestrator_end_to_end_smoke_20260708\dynamic_gate\coupled-vle-topL\column_summary_20260708_134032.csv`

## checkpoint_reload: PASS

| Check | Value | Limit | Candidate | Baseline | Result |
|---|---:|---:|---:|---:|---|
| final score ratio | 0.916218 | 1.1 | 14.2512 | 15.5544 | PASS |
| peak score ratio | 0.916218 | 1.1 | 14.2512 | 15.5544 | PASS |
| final relative state-rate ratio | 0.916218 | 1.1 | 0.0427537 | 0.0466633 | PASS |
| peak relative state-rate ratio | 0.916218 | 1.1 | 0.0427537 | 0.0466633 | PASS |
| final temperature-rate ratio | 0.940807 | 1.1 | 1.39979 | 1.48787 | PASS |

### Failure Breakdown

| Family | Ratio | Abs delta | Candidate | Baseline | Field |
|---|---:|---:|---:|---:|---|
| top liquid component net | 1.01341 | 21.9323 | 1657.79 | 1635.86 | `top_L_net_worst_abs_lbmolph` |
| K-state over K-thermo | 1.02625 | 0.063975 | 2.50112 | 2.43715 | `K_state_over_K_thermo_max_abs` |
| pressure inner solve | 0.887997 | -0.0013524 | 0.0107223 | 0.0120747 | `pv_inner_dp_max_psia` |
| relative state rate | 0.916218 | -0.00390955 | 0.0427537 | 0.0466633 | `ss_max_rel_state_rate_per_s` |
| K-state minus K-thermo | 0.977583 | -0.018581 | 0.810296 | 0.828876 | `K_state_minus_K_thermo_max_abs` |
| temperature rate | 0.940807 | -0.0880717 | 1.39979 | 1.48787 | `ss_max_temp_rate_F_per_s` |
| pressure/vapor-flow inner solve | 0.884071 | -0.193623 | 1.47657 | 1.67019 | `pv_inner_dv_max_lbmolph` |
| top liquid total net | 0.999252 | -0.971633 | -1297.59 | -1298.56 | `top_L_net_lbmolph` |

