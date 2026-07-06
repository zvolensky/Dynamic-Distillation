**CLI Reference**

This document covers:
- `python -m dynamic_distillation.dynamic_run_scaffold_v1`

For project terminology used below, see `docs/glossary.md`.

The runner performs Excel preflight validation before integration starts.
For tabular thermo details, see `docs/thermo_surrogate_tables.md`.

Current CLI default thermo execution is the pooled table path:
- `--thermo table-pool`
- `--thermo-table cache/thermo_table.json`
- `--thermo-pool-workers 2`
- `--thermo-pool-chunk-size 4`

Use explicit CLI flags to override that per run when needed.

Note: older `logs/` output is periodically archived to `logs/archive/old_logs_<date>.zip` to keep the repository tidy while preserving historical run data.

Current recommended validation order:
1. Use `relative-volatility` first for fast, dependency-free model/regression checks.
2. Use `clapeyron` PR for fast rigorous-thermo hydrocarbon parity experiments.
3. Use `dwsim` when checking DWSIM-specific property-package behavior or DLL integration.

**Install And Thermo Setup**

Base install:

```powershell
python -m pip install -e .
```

Optional UI install:

```powershell
python -m pip install -e ".[ui]"
```

Thermo backend dependencies:

| Backend | Install/setup | Notes |
|---|---|---|
| `stub` | Base install only. | Deterministic test/simple backend. |
| `relative-volatility` | Base install only. | Constant relative-volatility VLE with simple Cp/latent-heat enthalpies. Useful for validation cases where thermo should not dominate runtime or behavior. |
| `table`, `table-pool` | Base install plus a table JSON such as `cache/thermo_table.json`. | Default practical path; no live external thermo engine is required. |
| `dwsim` and `dwsim-*` aliases | `python -m pip install -e ".[dwsim]"`; install DWSIM; set `DWSIM_DTL_PATH`; add the DWSIM install folder to `PATH`. | Required DLLs include `DWSIM.Thermodynamics.dll` and `DWSIM.Interfaces.dll`; putting the DWSIM folder on `PATH` also lets native DLLs such as IpOpt load cleanly. |
| Python `thermo` fallback/helpers | `python -m pip install -e ".[thermo]"` | Used only by fallback/helper paths; not required for normal table runs or a working DWSIM path. |
| `clapeyron` | `python -m pip install -e ".[clapeyron]"` | Installs `pyclapeyron`; first import may download/install Julia and Clapeyron.jl under the user profile. |
| All optional thermo packages | `python -m pip install -e ".[all-thermo]"` | Installs Python packages for DWSIM bridge, Python `thermo`, and Clapeyron bridge. DWSIM itself is still installed separately. |

Windows DWSIM environment example:

```powershell
$dwsim = "C:\Users\Thoma\AppData\Local\DWSIM"
setx DWSIM_DTL_PATH $dwsim

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (($userPath -split ";") -notcontains $dwsim) {
  [Environment]::SetEnvironmentVariable("Path", "$userPath;$dwsim", "User")
}
```

Open a new terminal after changing user environment variables.

Backend smoke tests:

```powershell
python -c "import clr; print('pythonnet OK')"
python -c "import thermo; print('thermo OK')"
python -c "import pyclapeyron; print('pyclapeyron OK')"
```

Dependency-free validation case with energy states:

```powershell
python tools/create_relative_volatility_validation_case.py
python -m dynamic_distillation.dynamic_run_scaffold_v1 `
  --excel validation_relative_volatility_energy_30stage.xlsx `
  --runtime-mode parity `
  --thermo relative-volatility `
  --include-energy `
  --use-excel-vapor-holdup `
  --n-steps 3000 `
  --dt 0.2 `
  --log-every 300 `
  --allow-repeat-command
```

The current accepted baseline for this case is
`logs/validation_relative_volatility_energy_30stage_preserve_mv_fixed_600s/column_summary_20260524_160208.csv`,
with `steady_state_flag=1`, `steady_state_score` about `0.21`, and
`ss_max_rel_state_rate_per_s` about `6.3e-4`.

Source-topology validation against Skogestad Column A:

```powershell
python tools/create_skogestad_column_a_validation_case.py
python -m dynamic_distillation.dynamic_run_scaffold_v1 `
  --excel validation_skogestad_column_a_relative_volatility.xlsx `
  --runtime-mode parity `
  --thermo relative-volatility `
  --disable-boundary-states `
  --disable-vapor-states `
  --no-equilibrium `
  --n-steps 1500 `
  --dt 0.2 `
  --log-every 300 `
  --logs-dir logs/validation_skogestad_column_a_rv_source_topology_productdraw_300s `
  --allow-repeat-command
python tools/compare_skogestad_column_a_profile.py `
  logs/validation_skogestad_column_a_rv_source_topology_productdraw_300s/column_profile_20260524_214800.csv `
  --tol-x 0.001 `
  --tol-y 0.001
```

This validation uses Skogestad's public `cola.dat` steady profile for Column A
(`alpha=1.5`, 41 stages including total condenser and reboiler). The accepted
2026-05-24 run matched the source profile with `max_abs_x_error=8.03e-13` and
`max_abs_y_error=7.86e-13`. The source has algebraic vapor composition and no
separate reflux-drum or bottoms-sump dynamic states, so the source-equivalent
run must use `--disable-boundary-states --disable-vapor-states --no-equilibrium`.
The generated workbook leaves distillate and bottoms component mole-flow cells
blank so product draws follow the current terminal compositions, matching
`D*xD` and `B*xB` in the source model.

Dynamic +1% feed-rate source-response check:

```powershell
python -m dynamic_distillation.dynamic_run_scaffold_v1 `
  --excel logs/validation_skogestad_column_a_feed_F101_productdraw_step_restart.xlsx `
  --runtime-mode parity `
  --thermo relative-volatility `
  --disable-boundary-states `
  --disable-vapor-states `
  --no-equilibrium `
  --enable-liquid-hydraulic-override `
  --liquid-hydraulic-model linear-holdup `
  --liquid-hydraulic-override-alpha 1.0 `
  --liquid-hydraulic-htc-sec 3.78 `
  --n-steps 15000 `
  --dt 2.0 `
  --log-every 30 `
  --logs-dir logs/validation_skogestad_column_a_rv_feed_F101_500min_linearL_productdraw `
  --allow-repeat-command
python tools/compare_skogestad_dynamic_response.py `
  logs/validation_skogestad_column_a_rv_feed_F101_500min_linearL_productdraw/column_profile_20260524_215349.csv `
  --tol-x 0.001 `
  --tol-m 0.001
python tools/plot_skogestad_dynamic_comparison.py `
  logs/validation_skogestad_column_a_rv_feed_F101_500min_linearL_productdraw/skogestad_dynamic_reference_comparison.csv
```

The accepted +1% feed-rate run matched a direct Python translation of Skogestad
`colamod.m` with endpoint errors `endpoint_max_abs_x_error=1.04e-05` and
`endpoint_max_abs_m_error=1.72e-04`. The plot command writes comparative
composition and reboiler-holdup SVGs beside the comparison CSV; if
`matplotlib` is installed, the same tool can also write PNGs through its normal
plotting path.
This is a Tier 1 material-balance/topology validation only; it does not validate
real-component density, level geometry, energy/enthalpy, hydraulic pressure, or
rigorous thermo backends.

One-step runner checks:

```powershell
python -m dynamic_distillation.dynamic_run_scaffold_v1 `
  --excel distillation_column_template_20stage_chemsep_warmer_feed_seed_20260323.xlsx `
  --runtime-mode parity `
  --thermo dwsim `
  --dwsim-property-package pr `
  --n-steps 1 `
  --dt 0.2 `
  --no-write-logs `
  --allow-repeat-command

python -m dynamic_distillation.dynamic_run_scaffold_v1 `
  --excel distillation_column_template_20stage_chemsep_warmer_feed_seed_20260323.xlsx `
  --runtime-mode parity `
  --thermo clapeyron `
  --clapeyron-model PR `
  --n-steps 1 `
  --dt 0.2 `
  --no-write-logs `
  --allow-repeat-command
```

Aligned Clapeyron PR check using DWSIM PR parameters:

```powershell
python -m dynamic_distillation.dynamic_run_scaffold_v1 `
  --excel distillation_column_template_20stage_chemsep_warmer_feed_seed_20260323.xlsx `
  --runtime-mode parity `
  --thermo clapeyron `
  --clapeyron-model PR `
  --clapeyron-pr-parameter-source dwsim `
  --n-steps 1 `
  --dt 0.2 `
  --no-write-logs `
  --allow-repeat-command
```

**Parameters**

| Flag(s) | Type | Default | Explanation |
|---|---|---|---|
| `--excel` | path | `distillation_column_template.xlsx` | Excel case file to load. |
| `--runtime-mode` | `legacy` \| `parity` \| `calibration` \| `hydraulic` | `parity` | Runtime behavior mode: `parity` forces pressure/spec + vapor/profile + liquid hydraulics off; `calibration` uses the same closures as `parity` with explicit parity-check intent; `hydraulic` forces pressure/hydraulic + vapor/energy while leaving liquid hydraulics and vapor-holdup relaxation off unless explicitly enabled; `legacy` keeps spec/CLI-driven behavior. |
| `--n-steps` | int | `600` | Number of integration steps. |
| `--steps` | int | `None` | Alias for `--n-steps`. If provided, overrides `--n-steps`. |
| `--dt` | float | `None` | Time step in seconds; if omitted uses `col.sim.dt_sec` from the case. |
| `--log-every` | int | `None` | Log cadence (steps); if omitted uses `col.sim.log_every_n_steps` from the case. |
| `--integrator` | `explicit-euler` \| `bdf` \| `radau` \| `ida` | `explicit-euler` | Time integration mode. `bdf`/`radau` use SciPy stiff solvers; `ida` uses the pilot implicit DAE fixed-point stepper. |
| `--integrator-rtol` | float | `1e-3` | Relative tolerance for stiff integrators and IDA fixed-point convergence scaling. |
| `--integrator-atol` | float | `1e-6` | Absolute tolerance for stiff integrators and IDA fixed-point convergence scaling. |
| `--integrator-max-step-sec` | float | `None` | Optional cap on internal substep size used by stiff integrators. |
| `--integrator-substep-sec` | float | `None` | Split each outer `dt` into fixed stiff substeps of this size (seconds). |
| `--integrator-max-rhs-evals-per-step` | int | `24` | Cap on RHS calls per stiff step; if exceeded, the step falls back to explicit Euler. |
| `--integrator-step-wall-limit-sec` | float | `15.0` | Per-step wall-time cap for stiff integrators; if exceeded, the step falls back to explicit Euler. |
| `--ida-max-iter` | int | `8` | Maximum fixed-point iterations per IDA substep. |
| `--ida-relax` | float | `1.0` | Relaxation factor for IDA fixed-point updates (`0 < relax <= 1`). |
| `--no-temperature` | flag | `False` | Disables temperature states (default is enabled). |
| `--no-temp` | flag | `False` | Alias for `--no-temperature`. |
| `--include-energy` | flag | `False` | Enables energy holdup states (Option B1). |
| `--energy` | flag | `False` | Alias for `--include-energy`. |
| `--disable-boundary-states` | flag | `False` | Do not add separate reflux-drum/top and bottoms-sump states. Use only for source-topology validation cases where the source stage set already includes the condenser and reboiler. |
| `--disable-vapor-states` | flag | `False` | Do not integrate tray vapor holdup/composition states. Vapor composition is treated algebraically from liquid equilibrium; use only for validation sources with no vapor-holdup ODE. |
| `--no-equilibrium` | flag | `False` | Disables equilibrium relaxation (default is enabled). |
| `--no-eq` | flag | `False` | Alias for `--no-equilibrium`. |
| `--equilibrium-relaxation-mode`, `--eq-mode` | `auto` \| `phase-holdup` \| `composition-only` | `auto` | Equilibrium transfer target. `phase-holdup` keeps legacy flash phase-split transfer, `composition-only` relaxes vapor composition at fixed vapor holdup. `auto` selects mode by runtime context (hydraulic mode defaults to `composition-only`). |
| `--thermo` | `stub` \| `relative-volatility` \| `simple-rv` \| `constant-alpha` \| `clapeyron` \| `dwsim` \| `dwsim-unifac` \| `dwsim-nrtl` \| `dwsim-uniquac` \| `dwsim-raoult` \| `dwsim-srk` \| `table` \| `table-pool` | `table-pool` | Thermo backend selection. `relative-volatility` aliases use the workbook `Relative Volatility` spec when present, otherwise alpha defaults to `1.6`. |
| `--clapeyron-model` | string | `PR` | Clapeyron.jl model constructor name used when `--thermo clapeyron`, e.g. `PR`, `SRK`, `PCSAFT`. |
| `--clapeyron-ideal-model` | string | `None` | Optional Clapeyron ideal-model constructor name, e.g. `BasicIdeal` or `WalkerIdeal`. |
| `--clapeyron-pr-parameter-source` | `default` \| `dwsim` | `default` | For `--thermo clapeyron --clapeyron-model PR`, choose Clapeyron's native database or inject DWSIM PR `Tc/Pc/MW/acentric-factor/kij` values. `dwsim` requires DWSIM/pythonnet setup. |
| `--dwsim-property-package` | `pr` \| `srk` \| `unifac` \| `nrtl` \| `uniquac` \| `raoult` | `pr` | DWSIM property package used by `--thermo dwsim`; `dwsim-*` thermo aliases also select this package. |
| `--thermo-every` | int | `1` | Compute thermo every N steps; intermediate steps reuse cached thermo diagnostics. |
| `--thermo-refresh-dt` | float | `None` | Optional per-stage thermo refresh threshold `dT` (F). |
| `--thermo-refresh-dp` | float | `None` | Optional per-stage thermo refresh threshold `dP` (psia). |
| `--thermo-refresh-dx` | float | `None` | Optional per-stage thermo refresh threshold `max(abs(dz_k))`. |
| `--flash-feed-at-stage-conditions` | flag | `None` | Force TP-flash feed splitting at the feed-stage pressure instead of using the workbook feed vapor fraction directly. |
| `--no-flash-feed-at-stage-conditions` | flag | `None` | Force startup to use the workbook feed split directly without re-flashing at feed-stage pressure. |
| `--thermo-table` | path | `cache/thermo_table.json` | Tabular thermo JSON path used by default table/table-pool runs. |
| `--thermo-pool-workers` | int | `2` | Worker count for `table-pool`; CLI can still override per run. |
| `--thermo-pool-chunk-size` | int | `4` | Batch chunk size submitted per pool task in `table-pool`. |
| `--thermo-pool-timeout-sec` | float | `None` | Per-task timeout for `table-pool`; timed-out/failed chunks fall back to local evaluation. |
| `--fast-startup` | flag | `False` | Reduce expensive pre-integration startup work by skipping startup thermo conditioning, skipping hydraulic-energy startup consistency, and skipping top-drum startup steadying. |
| `--disable-startup-thermo-conditioning` | flag | `False` | Disables startup thermo-consistent conditioning pass (enabled by default). |
| `--startup-thermo-conditioning-iters` | int | `2` | Max startup thermo-conditioning iterations. |
| `--startup-thermo-conditioning-relax` | float | `1.0` | Relaxation factor (`0..1`) for startup thermo conditioning. |
| `--disable-restart-reentry-settling` | flag | `False` | For explicit restart/boundary-state workbooks, skip hidden re-entry conditioning so a deliberately reconciled initial state is preserved. |
| `--enable-liquid-hydraulic-override` | flag | `None` | Force-enable internal liquid hydraulic downflow override. |
| `--disable-liquid-hydraulic-override` | flag | `None` | Disable internal liquid hydraulic downflow override (profile-only internal `L_out`). |
| `--liquid-hydraulic-override-alpha` | float | `None` | Blend for liquid hydraulics override (`0=profile`, `1=full hydraulic`). |
| `--liquid-hydraulic-model` | `francis` | `None` | Internal liquid hydraulic closure model. |
| `--liquid-hydraulic-htc-sec` | float | `None` | Reserved hydraulic time constant for non-Francis liquid closures. |
| `--enable-startup-hydraulic-sequence` | flag | `False` | Enable startup sequence: pressure/profile-flow first, then residual-gated liquid hydraulics; supported in `legacy` and `hydraulic` runtime modes and ignored by source-topology modes. |
| `--startup-sequence-energy-on-sec` | float | `30.0` | Sequence time (`s`) to allow `vapor_flow_model="energy"`. |
| `--startup-sequence-liquid-on-sec` | float | `120.0` | Sequence time (`s`) to begin liquid-hydraulics ramp. |
| `--startup-sequence-liquid-ramp-sec` | float | `180.0` | Ramp timescale (`s`) for liquid-hydraulics blend. |
| `--startup-sequence-mass-resid-gate-lbmolph` | float | `250.0` | Max tray mass-residual gate; above this, liquid-hydraulic blend is paused/backed off. |
| `--startup-sequence-liquid-backoff-sec` | float | `None` | Optional timescale (`s`) for blend backoff while residual gate is exceeded. |
| `--enable-startup-vapor-homotopy` | flag | `False` | Enable the third startup phase: blend dynamic vapor traffic from profile flow to the configured dynamic vapor closure. |
| `--startup-sequence-profile-hold-sec` | float | `0.0` | Minimum initial hold time (`s`) with profile liquid and profile vapor traffic. |
| `--startup-sequence-vapor-on-sec` | float | `None` | Time (`s`) to begin vapor-flow homotopy; defaults to `liquid_on + liquid_ramp`. |
| `--startup-sequence-vapor-ramp-sec` | float | `60.0` | Cosine-ramp duration (`s`) for vapor homotopy beta. |
| `--startup-sequence-vapor-rel-rate-gate-per-s` | float | `1.0e-2` | Pause vapor beta ramp when the previous max relative inventory rate exceeds this value. |
| `--startup-sequence-vapor-backoff-sec` | float | `None` | Optional beta backoff timescale (`s`) when the vapor residual gate is exceeded. |
| `--disable-steady-state-detection` | flag | `False` | Disable runtime steady-state detector diagnostics. |
| `--steady-state-window-sec` | float | `30.0` | Time window (`s`) used for KPI/MV slope estimation. |
| `--steady-state-min-time-sec` | float | `60.0` | Earliest simulation time (`s`) when SS flag can become `1`. |
| `--steady-state-rel-rate-tol-per-s` | float | `3e-3` | Tolerance on max relative inventory rate `|dM/dt|/(|M|+floor)` (`1/s`). |
| `--steady-state-kpi-slope-tol-per-s` | float | `1e-4` | Tolerance on KPI slope magnitude (`1/s`) using distillate/bottoms composition trends. |
| `--steady-state-mv-rate-tol-per-s` | float | `20.0` | Tolerance on MV trend rate (`lbmol/h/s`) for reflux/boilup commands. |
| `--steady-state-temp-rate-tol-fps` | float | `0.15` | Tolerance on maximum tray temperature derivative (`F/s`). |
| `--steady-state-sp-error-tol` | float | `0.02` | Tolerance on max composition setpoint error (mole fraction). |
| `--steady-state-require-sp` | flag | `False` | Require setpoint-error criterion for `steady_state_flag=1`. |
| `--steady-state-rate-denom-floor-lbmol` | float | `1.0` | Denominator floor (`lbmol`) used in relative inventory-rate metric. |
| `--reb-neighbor-vflow-hi-ratio` | float | `None` | Override stage `N-1` vapor-flow upper guard as ratio of boilup in energy mode (default case value or runner fallback `1.20`). |
| `--reb-neighbor-vflow-lo-ratio` | float | `None` | Override stage `N-1` vapor-flow lower guard as ratio of boilup in energy mode (default case value or runner fallback `0.80`). |
| `--use-excel-vapor-holdup` | flag | `False` | Preserve tray vapor holdup values from Excel `Initial Conditions` through startup pressure initialization and thermo conditioning. Top-drum vapor seeding still runs. |
| `--vapor-holdup-relaxation-sec` | float | `None` | Override vapor-holdup relaxation time constant; `<= 0` disables the source term. |
| `--hydraulic-pressure-relaxation-sec` | float | `None` | Override hydraulic tray-pressure relaxation time constant; `<= 0` disables hydraulic pressure low-pass. |
| `--top-drum-pressure-temperature-relaxation-sec` | float | `None` | Override top-drum pressure temperature lag time constant; `<= 0` disables this lag, `None` uses case/default behavior. |
| `--vapor-flow-relaxation-sec` | float | `None` | Override vapor-flow relaxation time constant; `<= 0` disables relaxation. |
| `--conductance-vflow-nominal-hi-ratio` | float | `None` | Conductance-mode ceiling as ratio of nominal profile vapor flow (e.g., `1.5`). |
| `--stiff-vflow-smooth-clamp-lbmolph` | float | `None` | Smooth clamp width for hydraulic vapor-flow limits during stiff RHS evaluation (`lbmol/h`). `None` enables a small automatic value in stiff hydraulic mode; `<=0` disables smoothing. |
| `--pv-inner-max-iter` | int | `1` | Inner fixed-point iterations per timestep for pressure-vapor coupling; active only when `pressure=hydraulic` and `vapor-flow=energy/conductance`. |
| `--pv-inner-p-tol-psia` | float | `0.05` | Convergence tolerance for inner pressure iteration (`psia`). |
| `--pv-inner-v-tol-lbmolph` | float | `25.0` | Convergence tolerance for inner vapor-flow iteration (`lbmol/h`). |
| `--enable-dae-pilot-algebraic-solve` | flag | `False` | Enable pilot algebraic Newton solve for `z=[P_tray, V_out]` each step when `pressure=hydraulic` and `vapor-flow=energy/conductance`. |
| `--dae-pilot-max-iter` | int | `3` | Maximum Newton iterations for pilot algebraic solve. |
| `--dae-pilot-p-tol-psia` | float | `0.05` | Pressure algebraic residual tolerance (`psia`). |
| `--dae-pilot-v-tol-lbmolph` | float | `25.0` | Vapor-flow algebraic residual tolerance (`lbmol/h`). |
| `--dae-pilot-jac-rel-step` | float | `1e-6` | Relative finite-difference step used for pilot Jacobian construction. |
| `--dae-pilot-line-search-max` | int | `4` | Maximum backtracking line-search trials per Newton update. |
| `--reflux` | float | `None` | Override reflux (`lbmol/h`); if omitted uses case value. |
| `--boilup` | float | `None` | Override boilup (`lbmol/h`); if omitted uses case value. |
| `--condenser-duty-mode` | `total-condense` \| `specified` | `total-condense` | Condenser duty model. |
| `--condenser-duty-btuph` | float | `None` | Override condenser duty (`Btu/h`), used in `specified` mode. |
| `--condenser-duty-trim-btuph` | float | `None` | Additive condenser duty trim (`Btu/h`); in `total-condense` this is added to computed duty. |
| `--init-pack-top-drum-vapor-to-pressure` | flag | `False` | Initialization diagnostic: scale explicit top-drum vapor inventory so raw drum pressure starts at the target pressure. |
| `--init-top-drum-vapor-pressure-psia` | float | `None` | Pressure target for top-drum vapor packing; defaults to `--top-pressure-sp`, then workbook stage-1 pressure. |
| `--init-match-condenser-duty` | flag | `False` | Initialization diagnostic: evaluate the live total-condenser duty requirement at `t=0` and use it as the initial condenser-duty bias. |
| `--init-align-top-liquid-to-condensate` | flag | `False` | Preserve reflux-drum liquid holdup but initialize its component split from the live condenser condensate composition. Diagnostic for top_L/reflux-drum composition closure. |
| `--startup-total-reflux-washout-sec` | float | `None` | Temporarily evaluate startup steps in total-reflux mode so the reflux drum is washed by live condenser condensate before feed/product boundaries resume. |
| `--enable-level-control` | flag | `False` | Enable inventory PI loops: top drum PV -> distillate draw, bottom sump PV -> bottoms draw. |
| `--top-level-pv-mode` | `molar-holdup` \| `true-level` | `molar-holdup` | Top controller PV mode. |
| `--ignore-workbook-level-pv-mode` | flag | `False` | Use CLI level-controller PV modes instead of workbook `Top/Bottom Level PV Mode` entries. Useful for diagnostics where a workbook defaults to geometry-based level but molar holdup closure is being tested. |
| `--top-level-sp` | float | `None` | Top inventory setpoint (`sum(top_L)`, `lbmol`) when top PV mode is `molar-holdup`. |
| `--top-level-sp-frac` | float | `None` | Top drum level setpoint as fraction of drum diameter when top PV mode is `true-level`. |
| `--bottom-level-pv-mode` | `molar-holdup` \| `true-level` | `molar-holdup` | Bottom controller PV mode. `true-level` treats the sump as a vertical cylindrical vessel when sump volume is available. |
| `--bottom-level-sp` | float | `None` | Bottom inventory setpoint (`sum(bottom_L)`, `lbmol`) when bottom PV mode is `molar-holdup`. |
| `--bottom-level-sp-frac` | float | `None` | Bottom sump level setpoint as fraction of sump diameter when bottom PV mode is `true-level`. |
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
| `--bottom-sump-total-volume-ft3` | float | `None` | Bottom-sump total volume; enables bottom `true-level` control calculations. |
| `--enable-top-psv` | flag | `False` | Enable top-drum PSV relief model. |
| `--top-psv-sp` | float | `None` | Top PSV setpoint (`psia`). |
| `--top-psv-gain-lbmolps-psi` | float | `None` | Top PSV vent gain (`lbmol/s/psi`) on pressure above setpoint. |
| `--top-psv-max-lbmolps` | float | `None` | Top PSV max vent rate (`lbmol/s`). |
| `--enable-distillate-composition-control` | flag | `False` | Enable distillate-composition PI control (MV = reflux flow). |
| `--distillate-comp-component` | string | `C4` | Controlled distillate component alias/name. |
| `--distillate-comp-sp` | float | `None` | Distillate liquid mole-fraction setpoint. If omitted, runner can fall back to Excel specs (`Distillate Composition SP` / aliases) when available. |
| `--distillate-comp-kc` | float | `None` | Distillate composition PI gain (default `10000`). |
| `--distillate-comp-ti` | float | `None` | Distillate composition PI integral time (sec, default `240`). |
| `--reflux-cmd-min` | float | `None` | Lower clamp for reflux command (`lbmol/h`, default `0`). |
| `--reflux-cmd-max` | float | `None` | Upper clamp for reflux command (`lbmol/h`, default `max(2.5*bias, bias+5000)`). |
| `--disable-reflux-feasibility-cap` | flag | `False` | Disable dynamic reflux feasibility cap during distillate composition control. |
| `--enable-bottoms-composition-control` | flag | `False` | Enable bottoms-composition PI control. |
| `--bottoms-comp-component` | string | `C5` | Controlled bottoms component alias/name. |
| `--bottoms-comp-sp` | float | `None` | Bottoms liquid mole-fraction setpoint. If omitted, runner can fall back to Excel specs (`Bottoms Composition SP` / aliases) when available. |
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
  - `--runtime-mode calibration`: same closure set as `parity`, intended for parity/calibration checks.
  - `--runtime-mode hydraulic`: forces `Pressure=hydraulic`, `VaporFlow=energy`, keeps liquid-hydraulic override plus vapor-holdup relaxation off unless explicitly enabled, and defaults feed flashing at stage conditions off unless explicitly requested.
  - `--runtime-mode legacy`: uses existing spec/CLI behavior (backward-compatible path).
  - `--disable-boundary-states` and `--disable-vapor-states` are special validation switches, not normal plant-model defaults. They are intended to reproduce sources whose condenser/reboiler are already part of the listed stages and whose vapor phase is algebraic.
- Integrator:
  - `--integrator explicit-euler` keeps legacy explicit stepping (`y += dt*dydt`).
  - `--integrator bdf|radau` uses SciPy stiff stepping per outer timestep, with automatic per-step fallback to explicit Euler if a solve fails.
  - `--integrator ida` uses implicit-Euler fixed-point stepping with RHS-coupled DAE algebraic closure; when DAE pilot algebraic residuals are available, convergence requires both `dy` and weighted algebraic residual checks.
  - In `--runtime-mode hydraulic` with `--integrator ida`, runner applies tuned defaults when legacy defaults are still present: auto-enable DAE pilot algebraic solve, `ida_max_iter=12`, and `dae_pilot_v_tol_lbmolph=100` (explicit CLI overrides still win).
  - In stiff mode, hydraulic vapor-flow clamp regularization can be tuned via `--stiff-vflow-smooth-clamp-lbmolph`.
  - When `--enable-dae-pilot-algebraic-solve` is active with `bdf|radau`, the pilot DAE Newton solve runs once per outer step; implicit substeps reuse the solved algebraic seed via the PV-coupled RHS path.
- In `parity`, `calibration`, and `hydraulic` modes, startup hydraulic sequencing flags are ignored (sequence disabled by design).
- In `vapor_flow_model="energy"`, feed-stage vapor outflow is solved dynamically.
- `--no-flash-feed-at-stage-conditions` keeps the workbook feed split instead of re-flashing the feed at stage pressure.
- Current "level control" is inventory control in `lbmol` (top/bottom holdup states), not geometric vessel `% level`.
- Controller action is held at initialization row (`step=0`); PI updates begin at `step=1`.
- Distillate and bottoms flow rates in logs (`D_lbmolph`, `B_lbmolph`) are dynamic when level control is enabled.
- In the standard explicit-sump configuration, the reboiler is sump-fed:
  liquid drains from the bottom tray to the sump, bottoms is drawn from the
  sump, and boilup is withdrawn from the sump and returned as vapor to the
  bottom tray.
- `column_summary_*.csv` includes integrator diagnostics (`integrator_*`, `ida_*`) so fallback/convergence behavior is directly traceable in time-series logs.
- Runtime steady-state detector:
  - Progress lines include `SS=...` and active metric magnitudes when enabled.
  - `column_summary_*.csv` includes `steady_state_*` and `ss_*` fields for thresholded pass/fail auditing.
- `column_profile_*.csv` includes `node_type`:
  - `stage` rows for trays (`stage=1..N`)
  - `distillate_drum` row (`stage=0`) with top-drum/condenser inventory+PSV fields
  - `bottoms_sump` row (`stage=N+1`) with explicit sump inventory/state fields
    used for bottoms draw and, in the standard model, reboiler liquid feed
- Pressure-control PV source depends on MV mode:
  - `top-anchor` mode: `P_psia_hyd(stage1)` -> `P_psia_diag(stage1)` -> `P_top_drum_psia`.
  - `condenser-duty` mode: `P_top_drum_psia` -> `P_psia_hyd(stage1)` -> `P_psia_diag(stage1)`.
- `--pressure-control-mv top-anchor` manipulates hydraulic top-pressure anchor (`P_top_anchor_cmd_psia`).
- `--pressure-control-mv condenser-duty` manipulates condenser duty command (`Q_cond_cmd_BTUph`).
- With `--condenser-duty-mode total-condense`, duty-MV pressure control auto-switches to `top-anchor` unless `--allow-coupled-pressure-duty` is set.
- Startup behavior:
  - A "fresh" simulation (base workbook with no explicit runtime restart sheets) currently spends substantial wall-clock time in startup before the first logged integration row appears. On this column, a full fresh startup has recently taken about `10-12 minutes` before integration begins.
  - Vapor holdup is initialized to align with specified startup pressure.
  - Thermo-consistent startup conditioning is enabled by default (disable with `--disable-startup-thermo-conditioning`).
  - Top-drum startup steadying is attempted only when startup thermo conditioning is enabled.
  - These startup passes are important because they align vapor holdup, top-drum inventory, pressure state, and thermo state before the first timestep. Skipping or weakening them can reduce wall-clock time, but often degrades startup parity and can move the early trajectory onto a different path.
  - `--fast-startup` is a shortcut mode that skips startup thermo conditioning, skips hydraulic-energy startup consistency, and skips top-drum startup steadying to minimize pre-integration overhead.
  - If both explicit top holdup and top-drum liquid fraction are provided by the workbook, explicit top holdup wins for startup reflux-drum liquid inventory; the liquid fraction remains a secondary geometry/level hint.
  - Optional startup hydraulic sequencing (`--enable-startup-hydraulic-sequence`) applies pressure/profile-flow startup and delays liquid-hydraulic override with residual gating in `legacy` and `hydraulic` runtime modes.
  - Optional vapor homotopy (`--enable-startup-vapor-homotopy`) keeps vapor traffic on the profile while liquid hydraulics transition, then blends dynamic vapor flow in with a guarded beta ramp.
  - Every completed run now writes a companion restart workbook and native `.npz` checkpoint into the run folder. The restart workbook contains the updated `Initial Conditions` plus the `Boundary State`, `Energy State`, `Controller State`, and `Dynamic Memory` sheets. The native checkpoint preserves the packed dynamic state vector, selected numeric diagnostics/memory arrays, controller state, and metadata without Excel cell round-tripping.
  - Explicit restart runs now apply a short hidden re-entry settling pass before normal logging begins. This is much lighter than a fresh startup and is intended to reduce the restart bump at the first resumed timestep.
  - Use `--disable-restart-reentry-settling` for workbooks that already contain a deliberately reconciled initial state and should not be altered before the first logged timestep.
- Equilibrium-relaxation transfer mode:
  - `--eq-mode phase-holdup`: legacy behavior, relaxes toward flash phase split.
  - `--eq-mode composition-only`: relaxes vapor composition at fixed `MV_tot` (reduces conflict with vapor-holdup pressure closure).
  - `--eq-mode auto`: uses `composition-only` in `--runtime-mode hydraulic`, otherwise `phase-holdup`.
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
- Steady-state diagnostics:
  - `steady_state_enabled`, `steady_state_flag`, `steady_state_score`, `steady_state_active_criteria`
  - `ss_max_rel_state_rate_per_s`, `ss_max_kpi_slope_per_s`, `ss_max_mv_rate_per_s`, `ss_max_temp_rate_F_per_s`
  - `ss_max_sp_error`, `ss_window_samples`, `ss_window_sec`, `ss_min_time_sec`

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
