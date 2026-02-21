**CLI Reference**

This document covers:
- `python -m dynamic_distillation.dynamic_run_scaffold_v1`

The runner performs Excel preflight validation before integration starts.
For tabular thermo details, see `docs/thermo_surrogate_tables.md`.

**Parameters**

| Flag(s) | Type | Default | Explanation |
|---|---|---|---|
| `--excel` | path | `distillation_column_template.xlsx` | Excel case file to load. |
| `--runtime-mode` | `legacy` \| `parity` \| `hydraulic` | `parity` | Runtime behavior mode: `parity` forces pressure/spec + vapor/profile + liquid hydraulics off; `hydraulic` forces pressure/hydraulic + vapor/energy + liquid hydraulics on; `legacy` keeps spec/CLI-driven behavior. |
| `--n-steps` | int | `600` | Number of integration steps. |
| `--steps` | int | `None` | Alias for `--n-steps`. If provided, overrides `--n-steps`. |
| `--dt` | float | `None` | Time step in seconds; if omitted uses `col.sim.dt_sec` from the case. |
| `--log-every` | int | `None` | Log cadence (steps); if omitted uses `col.sim.log_every_n_steps` from the case. |
| `--no-temperature` | flag | `False` | Disables temperature states (default is enabled). |
| `--no-temp` | flag | `False` | Alias for `--no-temperature`. |
| `--include-energy` | flag | `False` | Enables energy holdup states (Option B1). |
| `--energy` | flag | `False` | Alias for `--include-energy`. |
| `--no-equilibrium` | flag | `False` | Disables equilibrium relaxation (default is enabled). |
| `--no-eq` | flag | `False` | Alias for `--no-equilibrium`. |
| `--thermo` | `stub` \| `dwsim` \| `table` \| `table-pool` | `stub` | Thermo backend selection. |
| `--thermo-every` | int | `1` | Compute thermo every N steps; intermediate steps reuse cached thermo diagnostics. |
| `--thermo-refresh-dt` | float | `None` | Optional per-stage thermo refresh threshold `dT` (F). |
| `--thermo-refresh-dp` | float | `None` | Optional per-stage thermo refresh threshold `dP` (psia). |
| `--thermo-refresh-dx` | float | `None` | Optional per-stage thermo refresh threshold `max(abs(dz_k))`. |
| `--thermo-table` | path | `None` | Tabular thermo JSON path (required for `--thermo table` and `--thermo table-pool`). |
| `--thermo-pool-workers` | int | `None` | Worker count for `table-pool`; `None` maps to `max(cpu_count-1, 1)`. |
| `--thermo-pool-chunk-size` | int | `4` | Batch chunk size submitted per pool task in `table-pool`. |
| `--thermo-pool-timeout-sec` | float | `None` | Per-task timeout for `table-pool`; timed-out/failed chunks fall back to local evaluation. |
| `--thermo-cache` | path | `None` | Load thermo cache JSON at startup. |
| `--disable-startup-thermo-conditioning` | flag | `False` | Disables startup thermo-consistent conditioning pass (enabled by default). |
| `--startup-thermo-conditioning-iters` | int | `2` | Max startup thermo-conditioning iterations. |
| `--startup-thermo-conditioning-relax` | float | `1.0` | Relaxation factor (`0..1`) for startup thermo conditioning. |
| `--enable-liquid-hydraulic-override` | flag | `None` | Force-enable internal liquid hydraulic downflow override. |
| `--disable-liquid-hydraulic-override` | flag | `None` | Disable internal liquid hydraulic downflow override (profile-only internal `L_out`). |
| `--liquid-hydraulic-override-alpha` | float | `None` | Blend for liquid hydraulics override (`0=profile`, `1=full hydraulic`). |
| `--enable-startup-hydraulic-sequence` | flag | `False` | Enable startup sequence: pressure first, then energy vapor closure, then residual-gated liquid hydraulics (`legacy` mode only; ignored by `parity`/`hydraulic`). |
| `--startup-sequence-energy-on-sec` | float | `30.0` | Sequence time (`s`) to allow `vapor_flow_model="energy"`. |
| `--startup-sequence-liquid-on-sec` | float | `120.0` | Sequence time (`s`) to begin liquid-hydraulics ramp. |
| `--startup-sequence-liquid-ramp-sec` | float | `180.0` | Ramp timescale (`s`) for liquid-hydraulics blend. |
| `--startup-sequence-mass-resid-gate-lbmolph` | float | `250.0` | Max tray mass-residual gate; above this, liquid-hydraulic blend is paused/backed off. |
| `--startup-sequence-liquid-backoff-sec` | float | `None` | Optional timescale (`s`) for blend backoff while residual gate is exceeded. |
| `--reb-neighbor-vflow-hi-ratio` | float | `None` | Override stage `N-1` vapor-flow upper guard as ratio of boilup in energy mode (default case value or runner fallback `1.20`). |
| `--reb-neighbor-vflow-lo-ratio` | float | `None` | Override stage `N-1` vapor-flow lower guard as ratio of boilup in energy mode (default case value or runner fallback `0.80`). |
| `--use-excel-vapor-holdup` | flag | `False` | Use tray vapor holdup values from Excel `Initial Conditions` instead of clearing them before pressure-based vapor-holdup initialization. |
| `--vapor-holdup-relaxation-sec` | float | `None` | Override vapor-holdup relaxation time constant; `<= 0` disables the source term. |
| `--hydraulic-pressure-relaxation-sec` | float | `None` | Override hydraulic tray-pressure relaxation time constant; `<= 0` disables hydraulic pressure low-pass. |
| `--top-drum-pressure-temperature-relaxation-sec` | float | `None` | Override top-drum pressure temperature lag time constant; `<= 0` disables this lag, `None` uses case/default behavior. |
| `--vapor-flow-relaxation-sec` | float | `None` | Override vapor-flow relaxation time constant; `<= 0` disables relaxation. |
| `--reflux` | float | `None` | Override reflux (`lbmol/h`); if omitted uses case value. |
| `--boilup` | float | `None` | Override boilup (`lbmol/h`); if omitted uses case value. |
| `--condenser-duty-mode` | `total-condense` \| `specified` | `total-condense` | Condenser duty model. |
| `--condenser-duty-btuph` | float | `None` | Override condenser duty (`Btu/h`), used in `specified` mode. |
| `--condenser-duty-trim-btuph` | float | `None` | Additive condenser duty trim (`Btu/h`); in `total-condense` this is added to computed duty. |
| `--enable-level-control` | flag | `False` | Enable inventory PI loops: top holdup -> distillate draw, bottom holdup -> bottoms draw. |
| `--top-level-sp` | float | `None` | Top inventory setpoint (`sum(top_L)`, `lbmol`); defaults to initial top holdup. |
| `--bottom-level-sp` | float | `None` | Bottom inventory setpoint (`sum(bottom_L)`, `lbmol`); defaults to initial bottom holdup. |
| `--top-level-kc` | float | `None` | Top level PI proportional gain (default `8.0`). |
| `--top-level-ti` | float | `None` | Top level PI integral time (sec, default `120`). |
| `--bottom-level-kc` | float | `None` | Bottom level PI proportional gain (default `8.0`). |
| `--bottom-level-ti` | float | `None` | Bottom level PI integral time (sec, default `120`). |
| `--enable-pressure-control` | flag | `False` | Enable top-pressure PI loop. |
| `--pressure-control-mv` | `auto` \| `condenser-duty` \| `top-anchor` | `auto` | Pressure-control manipulated variable selection. |
| `--allow-coupled-pressure-duty` | flag | `False` | Keep `condenser-duty` MV coupled with `total-condense` mode; default behavior auto-switches to `top-anchor`. |
| `--top-pressure-sp` | float | `None` | Top pressure setpoint (`psia`), defaults to stage-1 pressure spec. |
| `--top-pressure-kc` | float | `None` | Top pressure PI gain (defaults by MV mode). |
| `--top-pressure-ti` | float | `None` | Top pressure PI integral time (sec, default `120`). |
| `--top-pressure-pv-filter-tau-sec` | float | `None` | First-order filter time constant for pressure PV used by controller. |
| `--top-pressure-mv-slew-limit-per-s` | float | `None` | Slew-rate limit for pressure-controller MV command. |
| `--top-pressure-resid-ref-btups` | float | `None` | Reference energy residual (BTU/s) used to attenuate pressure PI gain. |
| `--top-pressure-resid-min-gain` | float | `0.25` | Minimum gain scale used with residual attenuation (`0..1`). |
| `--top-pressure-anchor-min` | float | `None` | Lower clamp for top-anchor command (`psia`). |
| `--top-pressure-anchor-max` | float | `None` | Upper clamp for top-anchor command (`psia`). |
| `--condenser-duty-min-btuph` | float | `None` | Lower clamp for commanded condenser duty (`Btu/h`). |
| `--condenser-duty-max-btuph` | float | `None` | Upper clamp for commanded condenser duty (`Btu/h`). |
| `--condenser-pressure-drop-psi` | float | `None` | Fixed condenser pressure drop from stage 2 to stage 1 in hydraulic mode. |
| `--top-drum-vapor-volume-ft3` | float | `None` | Reflux-drum vapor volume used for top pressure state. |
| `--top-drum-total-volume-ft3` | float | `None` | Reflux-drum total volume; enables dynamic vapor-space updates from liquid holdup. |
| `--enable-top-psv` | flag | `False` | Enable top-drum PSV relief model. |
| `--top-psv-sp` | float | `None` | Top PSV setpoint (`psia`). |
| `--top-psv-gain-lbmolps-psi` | float | `None` | Top PSV vent gain (`lbmol/s/psi`) on pressure above setpoint. |
| `--top-psv-max-lbmolps` | float | `None` | Top PSV max vent rate (`lbmol/s`). |
| `--enable-distillate-composition-control` | flag | `False` | Enable distillate-composition PI control (MV = reflux flow). |
| `--distillate-comp-component` | string | `C4` | Controlled distillate component alias/name. |
| `--distillate-comp-sp` | float | `None` | Distillate liquid mole-fraction setpoint. |
| `--distillate-comp-kc` | float | `None` | Distillate composition PI gain (default `10000`). |
| `--distillate-comp-ti` | float | `None` | Distillate composition PI integral time (sec, default `240`). |
| `--reflux-cmd-min` | float | `None` | Lower clamp for reflux command (`lbmol/h`, default `0`). |
| `--reflux-cmd-max` | float | `None` | Upper clamp for reflux command (`lbmol/h`, default `max(2.5*bias, bias+5000)`). |
| `--disable-reflux-feasibility-cap` | flag | `False` | Disable dynamic reflux feasibility cap during distillate composition control. |
| `--enable-bottoms-composition-control` | flag | `False` | Enable bottoms-composition PI control. |
| `--bottoms-comp-component` | string | `C5` | Controlled bottoms component alias/name. |
| `--bottoms-comp-sp` | float | `None` | Bottoms liquid mole-fraction setpoint. |
| `--bottoms-comp-kc` | float | `None` | Bottoms composition PI gain (units depend on MV choice). |
| `--bottoms-comp-ti` | float | `None` | Bottoms composition PI integral time (sec, default `240`). |
| `--bottoms-comp-mv` | `boilup` \| `reboiler-duty` | `boilup` | Bottoms composition controller manipulated variable. |
| `--boilup-cmd-min` | float | `None` | Lower clamp for boilup command (`lbmol/h`, default `0`). |
| `--boilup-cmd-max` | float | `None` | Upper clamp for boilup command (`lbmol/h`, default `max(2.5*bias, bias+5000)`). |
| `--reboiler-duty-cmd-min-btuph` | float | `None` | Lower clamp for reboiler-duty command (`Btu/h`). |
| `--reboiler-duty-cmd-max-btuph` | float | `None` | Upper clamp for reboiler-duty command (`Btu/h`). |
| `--reboiler-duty-btuph` | float | `None` | Reboiler-duty bias (`Btu/h`) for duty-mode bottoms control and RHS. |
| `--reflux-ratio-min` | float | `None` | Backward-compatible alias converted to reflux-flow minimum. |
| `--reflux-ratio-max` | float | `None` | Backward-compatible alias converted to reflux-flow maximum. |
| `--logs-dir` | path | `logs` | Directory for CSV outputs. |
| `--no-write-logs` | flag | `False` | Disable CSV outputs. |
| `--no-logs` | flag | `False` | Alias for `--no-write-logs`. |
| `--allow-repeat-command` | flag | `False` | Bypass exact-command duplicate guard against `docs/experiment_ledger.csv`. |

**Current Behavior Notes**

- Runtime simplification:
  - `--runtime-mode parity` (default): forces `Pressure=spec`, `VaporFlow=profile`, liquid-hydraulic override disabled.
  - `--runtime-mode hydraulic`: forces `Pressure=hydraulic`, `VaporFlow=energy`, liquid-hydraulic override enabled.
  - `--runtime-mode legacy`: uses existing spec/CLI behavior (backward-compatible path).
- In `parity` and `hydraulic` modes, startup hydraulic sequencing flags are ignored (sequence disabled by design).
- In `vapor_flow_model="energy"`, feed-stage vapor outflow is solved dynamically.
- There is no CLI flag to pin feed-stage vapor flow to the input profile.
- Current "level control" is inventory control in `lbmol` (top/bottom holdup states), not geometric vessel `% level`.
- Controller action is held at initialization row (`step=0`); PI updates begin at `step=1`.
- Distillate and bottoms flow rates in logs (`D_lbmolph`, `B_lbmolph`) are dynamic when level control is enabled.
- `column_profile_*.csv` includes `node_type`:
  - `stage` rows for trays (`stage=1..N`)
  - `distillate_drum` row (`stage=0`) with top-drum/condenser inventory+PSV fields
  - `bottoms_sump` row (`stage=N+1`) with sump/reboiler inventory fields
- Pressure-control PV source depends on MV mode:
  - `top-anchor` mode: `P_psia_hyd(stage1)` -> `P_psia_diag(stage1)` -> `P_top_drum_psia`.
  - `condenser-duty` mode: `P_top_drum_psia` -> `P_psia_hyd(stage1)` -> `P_psia_diag(stage1)`.
- `--pressure-control-mv top-anchor` manipulates hydraulic top-pressure anchor (`P_top_anchor_cmd_psia`).
- `--pressure-control-mv condenser-duty` manipulates condenser duty command (`Q_cond_cmd_BTUph`).
- With `--condenser-duty-mode total-condense`, duty-MV pressure control auto-switches to `top-anchor` unless `--allow-coupled-pressure-duty` is set.
- Startup behavior:
  - Vapor holdup is initialized to align with specified startup pressure.
  - Thermo-consistent startup conditioning is enabled by default (disable with `--disable-startup-thermo-conditioning`).
  - Top-drum startup steadying is always attempted when top states are active.
  - Optional startup hydraulic sequencing (`--enable-startup-hydraulic-sequence`) applies pressure-first startup and delays liquid-hydraulic override with residual gating in `--runtime-mode legacy` only.
- When thermo is skipped on a step (cadence/threshold gating), cached thermo is reused and that step forces `vapor_flow_model="profile"` for robustness.
- `--thermo table-pool` uses process-pool batch flashes when available. Failed/timed-out chunks fall back to local tabular evaluation.

**Selected Logging Columns**

- Composition control:
  - `xD_comp_pv`, `xD_comp_sp`, `Reflux_cmd_lbmolph`, `RR_comp_cmd`
  - `xB_comp_pv`, `xB_comp_sp`, `Boilup_cmd_lbmolph`, `Q_reb_cmd_BTUph`
- Pressure-control diagnostics:
  - `P_top_ctrl_pv_psia`, `P_top_ctrl_pv_raw_psia`, `P_top_ctrl_pv_filt_psia`
  - `P_top_ctrl_gain_scale`, `P_top_ctrl_energy_resid_abs_BTUps`
  - `P_top_anchor_cmd_psia`, `Q_cond_cmd_BTUph`
- Condenser/top-drum diagnostics:
  - `Q_cond_calc_BTUph`, `Q_cond_used_BTUph`, `Q_reb_used_BTUph`
  - `P_top_drum_psia`, `V_condensed_in_lbmolph`, `V_to_top_drum_lbmolph`, `V_condensed_top_lbmolph`
  - `V_top_drum_vapor_ft3`, `V_top_drum_liquid_ft3`, `rho_top_drum_liq_lbmol_ft3`
- PSV diagnostics:
  - `V_psv_top_lbmolph`, `PSV_open_flag`, `PSV_setpoint_psia`, `PSV_pv_psia`
- Global mass-closure diagnostics:
  - `M_total_lbmol`, `dM_total_dt_lbmolph`, `net_F_minus_D_minus_B_lbmolph`
  - `global_mass_closure_error_lbmolph`, `global_mass_closure_cum_lbmol`, `stage_mass_resid_sum_lbmolps`

**Preflight Validation Console Output**

- `"[Validation] PASS ..."` means checks completed with no blocking errors.
- `"[Validation][Warn] ..."` lines indicate non-blocking issues or defaulted behavior.
- `"[Validation] FAIL ..."` plus `"[Validation][Error] ..."` lines stop the run before integration.

**Examples**

```powershell
$env:PYTHONPATH='src'
python -m dynamic_distillation.dynamic_run_scaffold_v1 `
  --runtime-mode parity `
  --excel distillation_column_template.xlsx
```

```powershell
$env:PYTHONPATH='src'
python -m dynamic_distillation.dynamic_run_scaffold_v1 `
  --runtime-mode hydraulic `
  --thermo table `
  --thermo-table cache\thermo_table.json `
  --include-energy `
  --enable-level-control
```

```powershell
$env:PYTHONPATH='src'
python -m dynamic_distillation.dynamic_run_scaffold_v1 `
  --thermo table-pool `
  --thermo-table cache\thermo_table.json `
  --thermo-pool-workers 6 `
  --thermo-pool-chunk-size 8 `
  --thermo-pool-timeout-sec 5
```

```powershell
$env:PYTHONPATH='src'
python -m dynamic_distillation.dynamic_run_scaffold_v1 `
  --thermo table `
  --thermo-table cache\thermo_table.json `
  --include-energy `
  --enable-pressure-control `
  --pressure-control-mv top-anchor `
  --top-pressure-sp 220.44 `
  --top-pressure-kc -1.0 `
  --top-pressure-ti 60 `
  --top-pressure-pv-filter-tau-sec 3 `
  --top-pressure-mv-slew-limit-per-s 0.2 `
  --top-pressure-resid-ref-btups 2.0e5 `
  --top-pressure-resid-min-gain 0.3
```

```powershell
$env:PYTHONPATH='src'
python -m dynamic_distillation.dynamic_run_scaffold_v1 `
  --thermo table `
  --thermo-table cache\thermo_table.json `
  --include-energy `
  --enable-top-psv `
  --top-psv-sp 245 `
  --top-psv-gain-lbmolps-psi 0.05 `
  --top-psv-max-lbmolps 0.6
```

**Feasibility Trim Search**

Use this when you need to check whether the current equations can hit
`xD/xB` targets without PI-loop interactions:

```powershell
$env:PYTHONPATH='src'
python tools/feasibility_trim_search.py `
  --excel distillation_column_template.xlsx `
  --thermo table `
  --thermo-table cache/thermo_table.json `
  --include-energy `
  --n-steps 1200 `
  --dt 0.2 `
  --n-random 24 `
  --distillate-comp-component C4 `
  --bottoms-comp-component C5 `
  --tol-xd 0.002 `
  --tol-xb 0.002
```

The script writes ranked results to `logs/feasibility_trim_search_*.csv`.
