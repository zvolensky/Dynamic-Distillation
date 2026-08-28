# Streamlit UI

This repo includes a Streamlit UI for the latest Core V3 continuation runner and the legacy runner.

Launch:

```powershell
streamlit run ui/streamlit_app.py
```

More reliable on Windows from this repo:

```powershell
powershell -ExecutionPolicy Bypass -File tools/run_ui.ps1
```

Background launch with repo-local logs:

```powershell
powershell -ExecutionPolicy Bypass -File tools/run_ui.ps1 -Detached
```

Recommended install:

```powershell
pip install -e ".[ui]"
```

## Current UI Scope

- Choose one of two initial-state modes:
  - **Fresh Start from Excel**: the workbook supplies the case definition and initial seed
  - **Restart from Stored State**: the workbook supplies the case definition while a reusable `.npz` checkpoint supplies the dynamic state and controller memory
- Select an existing Excel input workbook or upload a new `.xlsx`
- For restart mode, enter a local checkpoint path or upload a native `.npz` checkpoint
- Validate the checkpoint schema, workbook identity, and stage/component counts before launching the runner
- Route `dynamic_distillation.core_v3_checkpoint.v1` checkpoints to `tools/run_core_v3_dynamic.py`
- Set Core V3 simulated duration while retaining the accepted implicit timestep of `0.25 s`
- Enter `Run Name` and `Run Description`
- Start the existing runner as a subprocess
- Stop the active subprocess
- Launch either from a form or by pasting a runner CLI command:
  - CLI mode accepts legacy flags, a full legacy command, or a `python tools/run_core_v3_dynamic.py ...` command
  - if `--excel` is omitted in CLI mode, the selected/uploaded workbook is used
  - the Fresh Start / Restart selector remains available in CLI mode
  - in Restart mode, the selected native checkpoint is injected when `--init-from-checkpoint` is omitted
  - the action is labeled `Run CLI Command`, and any disabled state reports its blocking reason beside the control
  - UI-managed logs stay enabled so the dashboard can keep following the run
- Optionally apply CLI-style execution overrides from the form UI:
  - runtime mode
  - thermo mode
  - thermo table path
  - thermo table anchor blend count
  - thermo pool workers/chunk size
  - thermo refresh cadence
  - fast startup
  - equilibrium-relaxation live PR
  - integrator
  - positive energy-mode override
- Watch live progress from the generated summary/profile CSV files
- For Core V3, report prescribed reflux and a rate-based steady-state score derived from conserved liquid/vapor inventories, temperature, terminal-composition trends, terminal-controller output trends, and whole-column accumulation
- Extend an active Core V3 run through `Add Time`; the runner polls the UI runtime-control file and increases its endpoint target
- View:
  - run progress/status
  - trend charts
  - latest stage profile table
  - a simple column schematic
  - warning lines from runner logs

## Design Notes

- The UI does not implement its own solver logic.
- A Core V3 checkpoint launches `tools/run_core_v3_dynamic.py`; a legacy checkpoint or fresh Excel start launches `dynamic_run_scaffold_v1`.
- Core V3 uses the accepted dynamic-pressure, vapor-holdup, live-DWSIM Peng-Robinson model with its implicit trust-region endpoint solve.
- Core V3 uses the established steady-state tolerances: relative inventory rate `3e-3 1/s`, temperature rate `0.15 F/s`, terminal-composition slope `1e-4 1/s`, controller-output rate `20 lbmol/h/s`, and whole-column accumulation `1%` of feed. The displayed score is the largest criterion-to-tolerance ratio, so `<= 1` is dynamically quiet by this detector.
- Core V3 summary rows record each implicit root's wall time, objective/Jacobian work, color count, and exact-state thermo memoization hit rate. Run metadata also records aggregate endpoint timing, memoization totals, and provider-family call counters so performance changes can be judged without altering the governing model.
- Core V3 UI/CLI launches use eight persistent worker processes for the 16-color Jacobian by default. A four-step serial/parallel proof produced identical solver decisions and bit-exact endpoints while reducing post-startup trajectory wall time by about 36%. Worker startup costs about nine seconds, so use `--parallel-workers 1` for very short probes.
- `tools/run_ui.ps1` launches Streamlit via `python -m streamlit` with `PYTHONPATH=src`.
- The UI passes workbook-derived `n_steps`, `dt`, and `log_every` explicitly.
- The UI emits an explicit `--thermo` mode in the command by default.
- `Include Energy` defaults to `On` in the UI because that matches the successful hydraulic-energy runs more closely.
- Precedence is:
  - UI advanced override
  - workbook-supported Excel setting
  - runner default
- Run metadata is persisted through:
  - `logs/**/run_metadata_<run_id>.json`
  - `logs/**/run_registry.csv`

## UI State Files

- The UI keeps its own lightweight working state under `.ui_state/`.
- Active run record:
  - `.ui_state/active_run.json`
  - this stores the current/most-recent run metadata the dashboard uses while a run is active or has just completed
  - it can include fields such as:
    - `pid`
    - `status`
    - `run_name`
    - `run_description`
    - `excel_path`
    - `logs_dir`
    - `command`
- Uploaded workbook cache:
  - `.ui_state/uploads/`
  - uploaded `.xlsx` and `.npz` files are copied here so the launched runner can use stable local paths
- These UI state files are distinct from the runner’s own per-run artifacts in `logs/**`.

## Current Limits

- The UI is aimed at local desktop use.
- Restart accepts `dynamic_distillation.core_v3_checkpoint.v1` and the legacy `dynamic_distillation.native_checkpoint.v1`.
- Core V3 DD evidence packages (for example DD-271/DD-274 trajectory `.npz` files) are identified and rejected with a clear message because they are audit evidence, not reusable native checkpoints.
- Single-use Core V3 DD research scripts remain rejected. The reusable Core V3 production entry point is `tools/run_core_v3_dynamic.py`.
- Core V3 fresh initialization from Excel is not yet exposed; Core V3 currently starts from an accepted reusable checkpoint.
- Views are implemented as tabs rather than true desktop pop-up windows.
- Live refresh is polling-based.
- The schematic is intentionally simple in this first version.
- Startup status is shown once near the top of the dashboard, with compact
  milestone detail in the `Progress` tab.

## Latest Core V3 Run

Use these Form-mode inputs:

- `Launch Mode`: `Form`
- `Initial State`: `Restart from Stored State`
- `Excel`: `distillation_column_template_20stage_chemsep_warmer_feed_seed_20260323.xlsx`
- `Stored State`: `logs/core_v3_checkpoints/dd274_endpoint_core_v3_checkpoint.npz`
- `Simulation Duration (sec)`: `30`
- `Log Every N Steps`: `4`

The equivalent command is:

```powershell
python tools/run_core_v3_dynamic.py `
  --excel distillation_column_template_20stage_chemsep_warmer_feed_seed_20260323.xlsx `
  --init-from-checkpoint logs/core_v3_checkpoints/dd274_endpoint_core_v3_checkpoint.npz `
  --duration-sec 30 `
  --dt 0.25 `
  --log-every 4 `
  --logs-dir logs/core_v3_ui_runs `
  --run-name core_v3_restart `
  --parallel-workers 8
```
