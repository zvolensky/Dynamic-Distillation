# DD-013 Hydraulic-Energy Temperature Closure Design Note

Date: 2026-03-25 (local)
Status: active design note
Related notes:
- `docs/dd_012_hydraulic_energy_chemsep_checkpoint_2026-03-22.md`
- `docs/dd_011_hydraulic_parity_drift_report_2026-02-19.md`
- `docs/dd_011_hydraulic_parity_followup_2026-02-21.md`

## Purpose

Record the current understanding of the remaining hydraulic-energy mismatch in the 20-stage warmer-feed ChemSep case, summarize the experiments performed on temperature handling, and define the recommended architectural direction for a general-purpose fix.

## Problem Statement

The current hydraulic-energy branch can now start near the intended ChemSep operating point and remain credible over short horizons, but it still exhibits drift over longer horizons.

In the active hydraulic branch:
1. `pressure_model = "hydraulic"`
2. `vapor_flow_model = "energy"`
3. tray temperature is still advanced with a separate `dT = dE / C` style ODE

This creates a likely dual thermal closure:
1. vapor flow is being used as the algebraic slack variable to satisfy the tray energy balance
2. tray temperature is also trying to satisfy the same energy balance through the differential path

The evidence from March 24-25, 2026 is that this over-participation is real:
1. suppressing the tray temperature response reduces the early `~96 s` instability
2. replacing the tray temperature path with crude follower logic can improve short-horizon stability
3. but simple global follower laws drift over longer horizons because they do not handle local composition sensitivity correctly

## Current Best Reference Branch

For general-purpose use today, the best longer-horizon reference remains the plain cap-law hydraulic branch:
- `logs/case20_hydraulic_240s_level_pressure_caplaw_chemsep_warmer_20260324/column_summary_20260324_103221.csv`

At `240 s`:
1. `P_top_drum_psia ~= 221.02`
2. `P_bot_psia ~= 232.26`
3. `Distillate_x_n_Butane ~= 0.10371`
4. `Bottoms_x_n_Propane ~= 0.05661`
5. `steady_state_score ~= 14.17`

This is not final parity, but it is still the most defensible general branch over `240 s`.

## Short-Horizon Temperature-Closure Findings

### 1. Startup top-drum pressure mismatch was fixed

The top-drum vapor-holdup initializer was corrected so startup pressure now matches the thermo-backed runtime pressure calculation rather than an inconsistent ideal-gas inversion.

Effect:
1. startup no longer begins near `171 psia`
2. the case starts near the ChemSep seed top pressure (`~220.44 psia`)

This was a real bug and is considered resolved.

### 2. Direct latent-energy correction in the tray temperature ODE was not viable

Adding explicit interphase latent terms into the tray temperature energy path caused an early instability near `96 s`.

Evidence:
- `logs/case20_hydraulic_240s_level_pressure_caplaw_energyfix_chemsep_warmer_20260324/column_summary_20260324_134730.csv`
- `logs/case20_hydraulic_240s_level_pressure_caplaw_internalizedlatent_chemsep_warmer_20260324/column_summary_20260324_140652.csv`

Interpretation:
1. missing latent-energy consistency was a real conceptual issue
2. but simply adding latent terms into the current mixed `temperature + energy-vapor-flow` formulation is not compatible with the existing thermal closure

### 3. Scalar damping of tray `dT` was a useful diagnostic

Applying scalar damping to tray `dT` in hydraulic-energy mode materially reduced the early shock.

Evidence:
- `0.1` damping:
  - `logs/case20_hydraulic_240s_level_pressure_caplaw_tdamp01_chemsep_warmer_20260324/column_summary_20260324_143656.csv`
- `0.25` damping:
  - `logs/case20_hydraulic_240s_level_pressure_caplaw_tdamp025_chemsep_warmer_20260324/column_summary_20260324_145055.csv`

Interpretation:
1. the tray temperature path is over-participating in hydraulic-energy mode
2. but blunt scalar damping is too crude to be the final fix

### 4. Bubble-point follower proved the architecture point, but not a usable implementation

An explicit bubble-point follower was attempted first by solving bubble point in the RHS and later with cached tray targets.

Cached-target run:
- `logs/case20_hydraulic_120s_level_pressure_bpfollow_cache_chemsep_warmer_20260324/column_summary_20260324_160654.csv`

Result:
1. performance problem solved
2. physics degraded badly
3. stale bubble-point targets made the thermal path nonphysical

Interpretation:
1. a follower-style temperature mode is directionally useful
2. but a stale or globally imposed follower target is not sufficient

### 5. Pressure-correction follower is the best short-horizon diagnostic mode

The best short-horizon result of the campaign came from the pressure-correction follower:
- `logs/case20_hydraulic_120s_level_pressure_pcfollow_tau02_slope15_chemsep_warmer_20260324/column_summary_20260324_172336.csv`

Settings:
1. `hydraulic_energy_temperature_mode = pressure-correction-follower`
2. `hydraulic_energy_temperature_damping = 0.1`
3. `hydraulic_energy_temperature_follow_tau_sec = 0.2`
4. `hydraulic_energy_temperature_pressure_slope_F_per_psi = 1.5`

At `120 s`:
1. `P_top_drum_psia ~= 218.85`
2. `P_bot_psia ~= 232.39`
3. `Distillate_x_n_Butane ~= 0.09902`
4. `Bottoms_x_n_Propane ~= 0.05111`
5. `steady_state_score ~= 3.95`

This beat the `120 s` cap-law baseline:
- `logs/case20_hydraulic_120s_level_pressure_caplaw_chemsep_warmer_20260324/column_summary_20260324_102428.csv`
- baseline score `~= 7.07`

### 6. Pressure-correction follower did not hold up at `240 s`

Run:
- `logs/case20_hydraulic_240s_level_pressure_pcfollow_tau02_slope15_chemsep_warmer_20260324/column_summary_20260324_180907.csv`

At `240 s`:
1. `P_top_drum_psia ~= 219.15`
2. `P_bot_psia ~= 232.32`
3. `Distillate_x_n_Butane ~= 0.10203`
4. `Bottoms_x_n_Propane ~= 0.05630`
5. `steady_state_score ~= 43.04`

Interpretation:
1. the pressure-correction follower is an excellent short-horizon stabilizer
2. but it still leaks drift over longer horizons
3. the global correction slope is too crude for a general-use production model

## Why the Pressure-Correction Follower Drifts

The best current interpretation is:
1. the follower suppresses the short-horizon dual-closure fight
2. but the global `dT/dP` correction ignores local composition sensitivity
3. over longer horizons, this biases some sections of the column onto the wrong thermal path

Evidence from the `240 s` comparison shows the upper-middle section is especially affected.

Example: stage `10`, comparing the `240 s` cap-law baseline vs pressure-correction follower:

Baseline:
- `logs/case20_hydraulic_240s_level_pressure_caplaw_chemsep_warmer_20260324/column_profile_20260324_103221.csv`

Pressure-correction follower:
- `logs/case20_hydraulic_240s_level_pressure_pcfollow_tau02_slope15_chemsep_warmer_20260324/column_profile_20260324_180907.csv`

At about `216 s`:
1. baseline stage-10 `T ~= 180.00 F`, `x(C4) ~= 0.6945`
2. follower stage-10 `T ~= 175.69 F`, `x(C4) ~= 0.6663`
3. `L_out_used` is unchanged
4. `V_out` and local composition shift noticeably

Interpretation:
1. the follower is altering the thermal/compositional profile in the upper-middle section
2. this is enough to poison the later `240 s` trajectory
3. a single global positive slope is not a robust physical approximation across the full column

## Stagewise `dT/dP` Audit

To test whether a single global pressure slope was physically reasonable, the apparent baseline `dT/dP` from the plain cap-law `120 s` run was examined between about `60 s` and `120 s`.

Examples from:
- `logs/case20_hydraulic_120s_level_pressure_caplaw_chemsep_warmer_20260324/column_profile_20260324_102428.csv`

Observed effective slopes:
1. stage `1`: `~1.29 F/psi`
2. stage `10`: `~-0.34 F/psi`
3. stage `19`: `~0.24 F/psi`

Interpretation:
1. a single column-wide `dT/dP` is not truly physical
2. local composition changes are large enough to dominate the apparent thermal-pressure sensitivity on some trays
3. this confirms that more global slope tuning is not a good production direction

## Production Guidance

### Recommended current default reference

Use the plain cap-law hydraulic branch as the reference for longer-horizon behavior:
- `logs/case20_hydraulic_240s_level_pressure_caplaw_chemsep_warmer_20260324/column_summary_20260324_103221.csv`

### Recommended status for `pressure-correction-follower`

Keep the pressure-correction follower in the codebase as an experimental mode because it has real diagnostic value:
1. it proves the tray temperature path is over-participating in hydraulic-energy mode
2. it is the best short-horizon stabilizer tested so far
3. it should not be treated as the production default

### Not recommended

The following are not recommended as production directions for a general-use model:
1. further tuning of one global `dT/dP` slope
2. stage-specific or section-specific slope hacks tuned to this ChemSep case
3. increasingly elaborate follower heuristics that are not derived from a more consistent thermodynamic closure

## Recommended Architectural Directions

The next general-purpose fix should address the thermal closure itself rather than continue follower tuning.

### Option A: quasi-steady / algebraic temperature closure in hydraulic-energy mode

Concept:
1. let `vapor_flow_model="energy"` own the tray energy closure
2. stop treating `dT = dE / C` as an equally strong competing mechanism
3. replace it with a more algebraic or quasi-steady thermal relation

Why it is attractive:
1. it directly addresses the dual-closure problem
2. it aligns with the successful diagnostic evidence from `pcfollow`

### Option B: enthalpy-state reformulation

Concept:
1. integrate tray enthalpy or total energy as the state
2. recover `T` and phase split from a thermo flash

Why it is attractive:
1. mathematically cleaner
2. avoids asking tray temperature to solve the energy balance separately

Why it is expensive:
1. more intrusive refactor
2. likely higher computational cost

## Current Recommendation

Short version:
1. treat `pressure-correction-follower` as a successful diagnostic mode, not the final model
2. retain the cap-law `240 s` branch as the current general reference
3. stop global-slope tuning
4. pursue a deeper hydraulic-energy temperature-closure refactor

## Relevant Code

- `src/dynamic_distillation/column_rhs_v1.py`
- `src/dynamic_distillation/dynamic_run_scaffold_v1.py`
- `tests/test_dynamic_run_scaffold_v1.py`

