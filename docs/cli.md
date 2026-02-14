**CLI Reference**

This covers `python -m dynamic_distillation.dynamic_run_scaffold_v1`.
`src/dynamic_run_scaffold_v1.py` supports the same flags except `--thermo-cache`.
Both runners now perform a preflight Excel validation and print a summary before the timestep loop starts.
For detailed surrogate table workflow, see `docs/thermo_surrogate_tables.md`.

**Parameters**

| Flag(s) | Type | Default | Explanation |
|---|---|---|---|
| `--excel` | path | `distillation_column_template.xlsx` | Excel case file to load. |
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
| `--thermo` | `stub` \| `dwsim` \| `table` | `stub` | Thermo backend selection. |
| `--thermo-every` | int | `1` | Compute full thermo every N steps; intermediate steps reuse cached values. |
| `--thermo-refresh-dt` | float | `None` | Override per-stage thermo refresh `dT` threshold (F). |
| `--thermo-refresh-dp` | float | `None` | Override per-stage thermo refresh `dP` threshold (psia). |
| `--thermo-refresh-dx` | float | `None` | Override per-stage thermo refresh composition threshold (`max(abs(dz_k))`). |
| `--thermo-table` | path | `None` | Path to a tabular thermo surrogate JSON (required for `--thermo table`). |
| `--thermo-cache` | path | `None` | Load a thermo cache JSON (only in `dynamic_distillation.dynamic_run_scaffold_v1`). |
| `--reb-neighbor-vflow-hi-ratio` | float | `None` | Override stage `N-1` vapor-flow upper guard as a ratio of boilup in energy mode (default from case or `1.02`). |
| `--reb-neighbor-vflow-lo-ratio` | float | `None` | Override stage `N-1` vapor-flow lower guard as a ratio of boilup in energy mode (default from case or `0.98`). |
| `--use-excel-vapor-holdup` | flag | `False` | Use tray vapor holdup values from Excel `Initial Conditions` instead of clearing them before pressure-based vapor-holdup initialization. |
| `--vapor-holdup-relaxation-sec` | float | `None` | Override vapor holdup relaxation time constant; `<= 0` disables the vapor-holdup relaxation source term. |
| `--vapor-flow-relaxation-sec` | float | `None` | Override vapor-flow relaxation time constant in energy-mode vapor traffic; `<= 0` disables relaxation. |
| `--reflux` | float | `None` | Override reflux (lbmol/h); if omitted uses case value. |
| `--boilup` | float | `None` | Override boilup (lbmol/h); if omitted uses case value. |
| `--condenser-duty-mode` | `total-condense` \| `specified` | `total-condense` | Condenser duty model. `total-condense` computes duty from stage-2 vapor condensation; `specified` uses fixed/commanded duty. |
| `--condenser-duty-btuph` | float | `None` | Override condenser duty (Btu/h). Used directly in `--condenser-duty-mode specified`. |
| `--condenser-duty-trim-btuph` | float | `None` | Additive condenser duty trim (Btu/h). In `total-condense` mode this is added to computed duty; in `specified` mode it is ignored. |
| `--enable-level-control` | flag | `False` | Enables inventory PI loops: top holdup -> distillate draw, bottom holdup -> bottoms draw. |
| `--top-level-sp` | float | `None` | Top inventory setpoint (`sum(top_L)`, lbmol). Defaults to initial top holdup when omitted. |
| `--bottom-level-sp` | float | `None` | Bottom inventory setpoint (`sum(bottom_L)`, lbmol). Defaults to initial bottom holdup when omitted. |
| `--top-level-kc` | float | `None` | Top level PI proportional gain. Default `8.0` when omitted. |
| `--top-level-ti` | float | `None` | Top level PI integral time (sec). Default `120` when omitted. |
| `--bottom-level-kc` | float | `None` | Bottom level PI proportional gain. Default `8.0` when omitted. |
| `--bottom-level-ti` | float | `None` | Bottom level PI integral time (sec). Default `120` when omitted. |
| `--enable-pressure-control` | flag | `False` | Enables top-pressure PI loop (MV chosen by `--pressure-control-mv`). |
| `--pressure-control-mv` | `auto` \| `condenser-duty` \| `top-anchor` | `auto` | Pressure-control manipulated variable. `auto` selects `top-anchor` for `total-condense`, else `condenser-duty`. In `total-condense`, choosing `condenser-duty` applies PI trim to condenser mass-split/condensation capacity (not only energy logging). |
| `--top-pressure-sp` | float | `None` | Top pressure setpoint (psia) for pressure PI loop. Defaults to stage-1 pressure spec. |
| `--top-pressure-kc` | float | `None` | Top pressure PI gain (Btu/h per psia). |
| `--top-pressure-ti` | float | `None` | Top pressure PI integral time (sec). |
| `--condenser-pressure-drop-psi` | float | `None` | Fixed condenser pressure drop applied from stage 2 to stage 1 in hydraulic mode. If omitted, runner reads `Condenser Pressure Drop (psi)` from Excel `Specifications` when present. |
| `--top-drum-vapor-volume-ft3` | float | `None` | Reflux-drum vapor-space volume used to convert top vapor holdup to pressure (`P_top_drum_psia`). If omitted, runner tries Excel drum geometry/volume keys first, then falls back to stage-1 vapor volume. |
| `--top-drum-total-volume-ft3` | float | `None` | Reflux-drum total vessel volume. When provided (or inferred from Excel geometry), top vapor volume updates dynamically from current top liquid holdup. |
| `--top-pressure-anchor-min` | float | `None` | Lower clamp for top-anchor command (psia) when `--pressure-control-mv top-anchor`. |
| `--top-pressure-anchor-max` | float | `None` | Upper clamp for top-anchor command (psia) when `--pressure-control-mv top-anchor`. |
| `--condenser-duty-min-btuph` | float | `None` | Lower clamp for commanded condenser duty. |
| `--condenser-duty-max-btuph` | float | `None` | Upper clamp for commanded condenser duty. |
| `--enable-distillate-composition-control` | flag | `False` | Enables distillate-composition PI control (MV = reflux flow, `lbmol/h`). |
| `--distillate-comp-component` | string | `C4` | Controlled distillate component name/alias (`C4`, `C4H10`, `n-Butane`, etc.). |
| `--distillate-comp-sp` | float | `None` | Distillate liquid mole-fraction setpoint for the selected component (e.g., `0.05`). |
| `--distillate-comp-kc` | float | `None` | Distillate composition PI gain (default `10000`, units `lbmol/h per mole-fraction`). |
| `--distillate-comp-ti` | float | `None` | Distillate composition PI integral time in seconds (default `240`). |
| `--reflux-cmd-min` | float | `None` | Lower clamp for reflux-flow command (`lbmol/h`, default `0`). |
| `--reflux-cmd-max` | float | `None` | Upper clamp for reflux-flow command (`lbmol/h`, default `max(2.5*bias, bias+5000)`). |
| `--enable-bottoms-composition-control` | flag | `False` | Enables bottoms-composition PI control (MV selectable: boilup flow or reboiler duty). |
| `--bottoms-comp-component` | string | `C5` | Controlled bottoms component name/alias (`C5`, `C5H12`, `n-Pentane`, etc.). |
| `--bottoms-comp-sp` | float | `None` | Bottoms liquid mole-fraction setpoint for selected component. |
| `--bottoms-comp-kc` | float | `None` | Bottoms composition PI gain (units depend on MV: `lbmol/h per mole-fraction` for boilup MV, `Btu/h per mole-fraction` for duty MV). |
| `--bottoms-comp-ti` | float | `None` | Bottoms composition PI integral time in seconds (default `240`). |
| `--bottoms-comp-mv` | `boilup` \| `reboiler-duty` | `boilup` | Bottoms composition controller manipulated variable. |
| `--boilup-cmd-min` | float | `None` | Lower clamp for boilup-flow command (`lbmol/h`, default `0`). |
| `--boilup-cmd-max` | float | `None` | Upper clamp for boilup-flow command (`lbmol/h`, default `max(2.5*bias, bias+5000)`). |
| `--reboiler-duty-cmd-min-btuph` | float | `None` | Lower clamp for reboiler-duty command (`Btu/h`) when `--bottoms-comp-mv reboiler-duty`. |
| `--reboiler-duty-cmd-max-btuph` | float | `None` | Upper clamp for reboiler-duty command (`Btu/h`) when `--bottoms-comp-mv reboiler-duty`. |
| `--reboiler-duty-btuph` | float | `None` | Reboiler-duty bias (`Btu/h`) used by duty-mode bottoms control and passed into RHS. |
| `--reflux-ratio-min` | float | `None` | Backward-compatible alias. Converted to reflux-flow min using current distillate flow. |
| `--reflux-ratio-max` | float | `None` | Backward-compatible alias. Converted to reflux-flow max using current distillate flow. |
| `--logs-dir` | path | `logs` | Directory for CSV outputs. |
| `--no-write-logs` | flag | `False` | Disables CSV output (default is enabled). |
| `--no-logs` | flag | `False` | Alias for `--no-write-logs`. |

**Current Behavior Notes**

- In `vapor_flow_model="energy"`, feed-stage vapor outflow is solved dynamically.
- There is no CLI flag to pin feed-stage vapor flow to the input profile.
- Current "level control" is inventory control in `lbmol` (top/bottom holdup states), not geometric vessel `% level`.
- Controller action is held at initialization row (`step=0`); PI updates begin at `step=1`.
- Distillate and bottoms flow rates in logs (`D_lbmolph`, `B_lbmolph`) are dynamic when level control is enabled.
- Pressure control uses top pressure PV in this order: `P_top_drum_psia` (if available), then `P_psia_hyd` at stage 1, then `P_psia_diag` at stage 1.
- `--pressure-control-mv top-anchor` manipulates the hydraulic top-pressure anchor directly (`P_top_anchor_cmd_psia`).
- `--pressure-control-mv condenser-duty` manipulates condenser duty command (`Q_cond_cmd_BTUph`).
- Distillate composition control writes:
  - `xD_comp_pv`: measured distillate liquid composition (selected component)
  - `xD_comp_sp`: composition setpoint
  - `Reflux_cmd_lbmolph`: commanded reflux flow
  - `RR_comp_cmd`: equivalent reflux ratio (`Reflux_cmd_lbmolph / D_lbmolph`) for diagnostics
  - Reflux command is additionally constrained by a dynamic feasibility cap tied to condenser inflow and reflux-drum inventory drawdown.
- Bottoms composition control writes:
  - `xB_comp_pv`: measured bottoms liquid composition (selected component)
  - `xB_comp_sp`: composition setpoint
  - `Boilup_cmd_lbmolph`: commanded boilup flow (when `--bottoms-comp-mv boilup`)
  - `Q_reb_cmd_BTUph`: commanded reboiler duty (when `--bottoms-comp-mv reboiler-duty`)
- New condenser-duty logging columns:
  - `Q_cond_used_BTUph`: duty actually applied in RHS
  - `Q_reb_used_BTUph`: reboiler duty applied in RHS
  - `Q_cond_cmd_BTUph`: controller command (if pressure control enabled)
  - `Q_reb_cmd_BTUph`: bottoms-composition reboiler-duty command (if duty MV is selected)
  - `Q_cond_calc_BTUph`: computed duty from total-condense closure (only in `total-condense` mode)
  - `P_top_ctrl_pv_psia`: top pressure PV used by controller
  - `P_top_drum_psia`: top-drum pressure from vapor holdup state
  - `V_condensed_in_lbmolph`: stage-2 vapor condensed in condenser from incoming vapor
  - `V_to_top_drum_lbmolph`: stage-2 vapor not condensed and routed to top vapor holdup
  - `V_condensed_top_lbmolph`: top-vapor holdup condensed into top liquid holdup
  - `V_top_drum_vapor_ft3`: dynamic top-drum vapor-space volume
  - `V_top_drum_liquid_ft3`: inferred top-drum liquid volume
  - `rho_top_drum_liq_lbmol_ft3`: inferred top-drum liquid density used in holdup-to-volume conversion
- Composition logging semantics at column top:
  - `x_Distillate_<comp>` / `y_Distillate_<comp>`: stage-1 condenser tray liquid/vapor compositions.
  - `Distillate_x_<comp>`: reflux-drum liquid composition (`top_L` holdup state).
  - These are intentionally different states in the current model.
- Global mass-closure diagnostic columns:
  - `M_total_lbmol`: total column inventory (trays + top/bottom holdups)
  - `dM_total_dt_lbmolph`: model-predicted inventory derivative from state ODEs
  - `net_F_minus_D_minus_B_lbmolph`: external net molar accumulation (`F - D - B`)
  - `global_mass_closure_error_lbmolph`: `dM_total_dt_lbmolph - net_F_minus_D_minus_B_lbmolph`
  - `global_mass_closure_cum_lbmol`: time-integral of closure error (diagnostic drift monitor)
  - `stage_mass_resid_sum_lbmolps`: sum of per-stage mass residual diagnostics from RHS
  - These are diagnostics only; no runtime mass-balance correction is applied from these signals.

**Preflight Validation Console Output**

- `"[Validation] PASS ..."` means checks completed with no blocking errors.
- `"[Validation][Warn] ..."` lines indicate non-blocking issues or defaulted behavior.
- For model defaults, warnings now include the resolved value, for example:
- `"[Validation][Warn] Pressure Model not specified; runner default is 'hydraulic'."`
- `"[Validation][Warn] Vapor Flow Model not specified; runner default is 'energy'."`
- `"[Validation] FAIL ..."` plus `"[Validation][Error] ..."` lines stop the run before integration.

**Examples**

```powershell
.\.venv\Scripts\python.exe -m dynamic_distillation.dynamic_run_scaffold_v1 `
  --excel distillation_column_template.xlsx
```

```powershell
.\.venv\Scripts\python.exe -m dynamic_distillation.dynamic_run_scaffold_v1 `
  --excel distillation_column_template.xlsx `
  --n-steps 1200 `
  --dt 0.5 `
  --log-every 10
```

```powershell
.\.venv\Scripts\python.exe -m dynamic_distillation.dynamic_run_scaffold_v1 `
  --thermo dwsim `
  --thermo-every 5 `
  --reflux 2400 `
  --boilup 4800
```

```powershell
.\.venv\Scripts\python.exe -m dynamic_distillation.dynamic_run_scaffold_v1 `
  --thermo-cache cache\thermo_cache.json
```

```powershell
.\.venv\Scripts\python.exe -m dynamic_distillation.dynamic_run_scaffold_v1 `
  --thermo table `
  --thermo-table cache\thermo_table.json
```

```powershell
.\.venv\Scripts\python.exe -m dynamic_distillation.dynamic_run_scaffold_v1 `
  --thermo table `
  --thermo-table cache\thermo_table.json `
  --include-energy `
  --enable-level-control
```

```powershell
.\.venv\Scripts\python.exe -m dynamic_distillation.dynamic_run_scaffold_v1 `
  --thermo table `
  --thermo-table cache\thermo_table.json `
  --include-energy `
  --enable-pressure-control `
  --top-pressure-sp 219.44 `
  --top-pressure-kc -500000 `
  --top-pressure-ti 120
```

```powershell
.\.venv\Scripts\python.exe -m dynamic_distillation.dynamic_run_scaffold_v1 `
  --thermo table `
  --thermo-table cache\thermo_table.json `
  --include-energy `
  --enable-level-control `
  --top-level-sp 397 `
  --bottom-level-sp 794 `
  --enable-pressure-control `
  --pressure-control-mv top-anchor `
  --top-pressure-sp 220.44 `
  --top-pressure-kc -1.0 `
  --top-pressure-ti 60 `
  --enable-distillate-composition-control `
  --distillate-comp-component C4 `
  --distillate-comp-sp 0.05 `
  --distillate-comp-kc 20 `
  --distillate-comp-ti 60 `
  --reflux-cmd-min 2000 `
  --reflux-cmd-max 9000
```

```powershell
.\.venv\Scripts\python.exe -m dynamic_distillation.dynamic_run_scaffold_v1 `
  --thermo table `
  --thermo-table cache\thermo_table.json `
  --include-energy `
  --enable-level-control `
  --enable-pressure-control `
  --pressure-control-mv top-anchor `
  --top-pressure-sp 220.44 `
  --enable-distillate-composition-control `
  --distillate-comp-component C4 `
  --distillate-comp-sp 0.05 `
  --reflux-cmd-min 2000 `
  --reflux-cmd-max 9000 `
  --enable-bottoms-composition-control `
  --bottoms-comp-component C5 `
  --bottoms-comp-sp 0.18 `
  --boilup-cmd-min 3000 `
  --boilup-cmd-max 9000
```
