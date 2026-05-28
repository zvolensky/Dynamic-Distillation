# DD-025 Frozen Thermo Cadence Probe

Date: 2026-04-08

## Purpose

Measure whether long-run wall clock can be reduced materially by running live Clapeyron thermo on a fixed cadence instead of every hydraulic timestep.

This follows the direction laid out in [dd_024_long_run_wall_clock_roadmap_2026-04-08.md](/c:/Users/Thoma/Documents/Python%20Scripts/Dynamic_DistillationII/docs/dd_024_long_run_wall_clock_roadmap_2026-04-08.md#L1): prioritize long-run throughput over further startup trimming.

## What Changed

The runner now has an explicit runtime thermo execution planner in [dynamic_run_scaffold_v1.py](/c:/Users/Thoma/Documents/Python%20Scripts/Dynamic_DistillationII/src/dynamic_distillation/dynamic_run_scaffold_v1.py#L438), plus a CLI switch to disable cadence guardrails when we want a true frozen-thermo probe:

- `--thermo-every N`
- `--disable-thermo-cadence-guardrails`

I also adjusted the auto guardrail defaults in [dynamic_run_scaffold_v1.py](/c:/Users/Thoma/Documents/Python%20Scripts/Dynamic_DistillationII/src/dynamic_distillation/dynamic_run_scaffold_v1.py#L3280) so hydraulic cadence runs no longer auto-enable pressure-drift refreshes. The live traces showed that default `dP` refreshes effectively defeated cadence.

## Probe Results

### 60 s Simulated, Cadence-Only Thermo

Command family:

```powershell
python -m dynamic_distillation.dynamic_run_scaffold_v1 `
  --excel distillation_column_template_20stage_chemsep_warmer_feed_seed_20260323.xlsx `
  --runtime-mode hydraulic `
  --thermo clapeyron `
  --clapeyron-model PR `
  --n-steps 300 `
  --dt 0.2 `
  --log-every 5 `
  --thermo-every 5 `
  --disable-thermo-cadence-guardrails `
  --fast-startup
```

Measured run:
- metadata: [run_metadata_20260408_143712.json](/c:/Users/Thoma/Documents/Python%20Scripts/Dynamic_DistillationII/logs/depropanizer_20stage_hydraulic_clapeyron_pr_60s_te5_noguard_20260408/run_metadata_20260408_143712.json)
- trace: [startup_trace_20260408_143621.log](/c:/Users/Thoma/Documents/Python%20Scripts/Dynamic_DistillationII/logs/depropanizer_20stage_hydraulic_clapeyron_pr_60s_te5_noguard_20260408/startup_trace_20260408_143621.log)

Observed:
- `final_time_s = 60.0`
- `elapsed_wall_sec = 15.20` for the runtime window
- `thermo_reason=hold` on `240` steps
- `thermo_reason=cadence` on `61` steps
- progress line at `60 s` simulated reported `sim/wall = 3.993`

Important thermo counters:
- `main_tray_refresh.backend_flash_equivalents = 1081`
- `energy_vapor_flow_enthalpy_refresh.backend_flash_equivalents = 1832`
- `temperature_state_enthalpy_refresh.backend_flash_equivalents = 770`
- `condenser_duty_bubble_point_helper_flash.backend_flash_equivalents = 30`

### 5 min Simulated, Cadence-Only Thermo

Measured run:
- metadata: [run_metadata_20260408_143854.json](/c:/Users/Thoma/Documents/Python%20Scripts/Dynamic_DistillationII/logs/depropanizer_20stage_hydraulic_clapeyron_pr_5min_te5_noguard_20260408/run_metadata_20260408_143854.json)
- trace: [startup_trace_20260408_143804.log](/c:/Users/Thoma/Documents/Python%20Scripts/Dynamic_DistillationII/logs/depropanizer_20stage_hydraulic_clapeyron_pr_5min_te5_noguard_20260408/startup_trace_20260408_143804.log)

Observed:
- `final_time_s = 300.0`
- `elapsed_wall_sec = 34.71` for the runtime window
- `thermo_reason=hold` on `1200` steps
- `thermo_reason=cadence` on `301` steps
- progress line at `300 s` simulated reported `sim/wall = 8.668`

Important thermo counters:
- `main_tray_refresh.backend_flash_equivalents = 5401`
- `energy_vapor_flow_enthalpy_refresh.backend_flash_equivalents = 9057`
- `temperature_state_enthalpy_refresh.backend_flash_equivalents = 1056`
- `condenser_duty_bubble_point_helper_flash.backend_flash_equivalents = 120`

## Interpretation

This is the first strong evidence that the long-run target is realistic.

The key point is not just that the run is faster. It is that the runtime trace now shows the intended control pattern:

- most steps are true hold steps
- live thermo is only re-entered on the configured cadence
- the column stayed numerically well-behaved enough to finish both the 60 s and 5 min probes

Using the 5 min probe as the best current long-run reference:

- runtime window ratio is about `300 / 34.71 = 8.64 sim-seconds per wall-second`
- adding fresh startup still leaves total wall well below the old multi-hour extrapolations
- a fresh-process 5 min run was roughly `49.16 s` startup + `34.71 s` runtime window, or about `84 s` total before final file writes finish

That is a dramatic shift from the earlier April 7 cold-path outlook.

## Remaining Bottleneck

Even in cadence-only mode, the largest remaining wall consumer inside the runtime window is still the condenser bubble helper:

- `condenser_duty_bubble_point_helper_flash.wall_sec ≈ 8.77 s` on the 60 s probe
- `condenser_duty_bubble_point_helper_flash.wall_sec ≈ 9.10 s` on the 5 min probe

So the next throughput work should focus there, not on the integrator.

## Recommendation

Do not make cadence-without-guardrails the silent default yet.

Instead:

1. Keep it as an explicit benchmarked mode while we gather a little more stability evidence.
2. Target condenser-duty cadence/reuse next, because that is now the dominant runtime bucket.
3. Re-run the same cadence-only pattern on at least one more column family before promoting it to a broader default.

## Modules Involved

- runner orchestration: [dynamic_run_scaffold_v1.py](/c:/Users/Thoma/Documents/Python%20Scripts/Dynamic_DistillationII/src/dynamic_distillation/dynamic_run_scaffold_v1.py)
- main RHS and temperature/condenser work: [column_rhs_v1.py](/c:/Users/Thoma/Documents/Python%20Scripts/Dynamic_DistillationII/src/dynamic_distillation/column_rhs_v1.py)
- thermo refresh coordination: [thermo_step_coordinator_v1.py](/c:/Users/Thoma/Documents/Python%20Scripts/Dynamic_DistillationII/src/dynamic_distillation/thermo_step_coordinator_v1.py)
- Clapeyron backend: [thermo_clapeyron_provider_v1.py](/c:/Users/Thoma/Documents/Python%20Scripts/Dynamic_DistillationII/src/dynamic_distillation/thermo_clapeyron_provider_v1.py)
- benchmark harness and manifest: [bench_live_thermo_refactor_v1.py](/c:/Users/Thoma/Documents/Python%20Scripts/Dynamic_DistillationII/tools/bench_live_thermo_refactor_v1.py) and [thermo_refactor_benchmark_manifest_2026-04-05.json](/c:/Users/Thoma/Documents/Python%20Scripts/Dynamic_DistillationII/docs/thermo_refactor_benchmark_manifest_2026-04-05.json)
